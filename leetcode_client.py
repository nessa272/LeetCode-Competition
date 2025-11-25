import requests
from datetime import datetime, timezone, timedelta, date
from typing import Any, Dict, List, Optional
import cs304dbi as dbi

LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"


class LeetCodeClientError(Exception):
    """Custom error for LeetCode client issues."""
    pass


def _graphql_request(query: str, variables: Optional[dict] = None) -> dict:
    """
    Send a GraphQL request to LeetCode and return the 'data' field.

    Raises LeetCodeClientError if the HTTP status is not 200 or if GraphQL
    returns an error object.
    """
    payload = {"query": query, "variables": variables or {}}
    headers = {"Content-Type": "application/json"}

    try:
        resp = requests.post(LEETCODE_GRAPHQL_URL, json=payload, headers=headers)
    except requests.RequestException as e:
        raise LeetCodeClientError(f"Network error talking to LeetCode: {e}") from e

    if resp.status_code != 200:
        raise LeetCodeClientError(
            f"LeetCode GraphQL returned {resp.status_code}: {resp.text[:200]}"
        )

    data = resp.json()
    if "errors" in data:
        raise LeetCodeClientError(f"LeetCode GraphQL error: {data['errors']}")

    return data.get("data", {})


def fetch_recent_ac_submissions(username: str, limit: int = 20) -> List[dict]:
    """
    Fetch recent ACCEPTED submissions for a LeetCode username.

    Uses LeetCode's 'recentAcSubmissionList', which only returns AC submissions.

    Returns a list of dicts with keys at least:
      - id
      - title
      - titleSlug
      - timestamp (unix seconds)
    """
    query = """
    query recentAcSubmissions($username: String!, $limit: Int!) {
      recentAcSubmissionList(username: $username, limit: $limit) {
        id
        title
        titleSlug
        timestamp
      }
    }
    """
    data = _graphql_request(query, {"username": username, "limit": limit})
    subs = data.get("recentAcSubmissionList") or []
    return subs


def _fetch_problem_meta_from_leetcode(title_slug: str) -> Dict[str, Any]:
    """
    Hit LeetCode's question() GraphQL to get metadata for a problem slug.

    Returns a dict with keys:
      - lc_problem (int)
      - title (str)
      - difficulty (str, 'easy'/'medium'/'hard')
    """
    query = """
    query questionData($titleSlug: String!) {
      question(titleSlug: $titleSlug) {
        questionFrontendId
        title
        difficulty
      }
    }
    """
    data = _graphql_request(query, {"titleSlug": title_slug})
    q = data.get("question")
    if not q:
        raise LeetCodeClientError(f"No question data for slug={title_slug!r}")

    lc_problem = int(q["questionFrontendId"])
    title = q["title"]
    difficulty = q["difficulty"].lower()  # 'Easy' -> 'easy'

    return {
        "lc_problem": lc_problem,
        "title": title,
        "difficulty": difficulty,
    }


def _insert_problem_into_db(cursor, meta: Dict[str, Any], title_slug: str) -> None:
    """
    Insert or update a row in the 'problem' table from a metadata dict.

    Expects schema:

    CREATE TABLE problem (
      lc_problem  INT PRIMARY KEY,
      title_slug  VARCHAR(255) UNIQUE NOT NULL,
      title       VARCHAR(255) NOT NULL,
      difficulty  ENUM('easy','medium','hard') NOT NULL
    );
    """
    cursor.execute(
        """
        INSERT INTO problem (lc_problem, title_slug, title, difficulty)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
          title = VALUES(title),
          difficulty = VALUES(difficulty)
        """,
        (
            meta["lc_problem"],
            title_slug,
            meta["title"],
            meta["difficulty"],
        ),
    )


def get_problem_meta(cursor, title_slug: str) -> Dict[str, Any]:
    """
    Resolve a problem slug to (lc_problem, title, difficulty), using:

    1. MySQL 'problem' table
    2. LeetCode GraphQL (if not found in DB)

    NOTE: This helper assumes `cursor.fetchone()` returns a dict-like row
    with keys 'lc_problem', 'title', and 'difficulty'.
    It does NOT commit or close the cursor.
    """
    # Try DB first
    cursor.execute(
        """
        SELECT lc_problem, title, difficulty
        FROM problem
        WHERE title_slug = %s
        """,
        (title_slug,),
    )
    row = cursor.fetchone()
    if row:
        return {
            "lc_problem": int(row["lc_problem"]),
            "title": row["title"],
            "difficulty": row["difficulty"],
        }

    # Fallback to LeetCode and write to DB
    meta = _fetch_problem_meta_from_leetcode(title_slug)
    _insert_problem_into_db(cursor, meta, title_slug)
    return meta


def _update_person_stats(
    cursor,
    pid: int,
    new_submission_dates: List[date],
) -> None:
    """
    Incrementally update current_streak, longest_streak, total_problems,
    and last_submission for the given pid, using ONLY:

      - existing person stats
      - the dates of newly inserted submissions (one per new problem)

    Assumes:
      - `cursor` is part of an open transaction owned by the caller.
      - `cursor.fetchone()` returns dict-like rows.
      - Caller handles commit/rollback and closing the cursor.
    """
    if not new_submission_dates:
        # Nothing new; nothing to update.
        return

    # 1) Get existing stats for this person
    cursor.execute(
        """
        SELECT current_streak, longest_streak, total_problems, last_submission
        FROM person
        WHERE pid = %s
        """,
        (pid,),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValueError(f"No person found with pid={pid}")

    current_streak = row["current_streak"] or 0
    longest_streak = row["longest_streak"] or 0
    total_problems = row["total_problems"] or 0
    last_submission = row["last_submission"]  # may be None

    # 2) Basic increments
    new_count = len(new_submission_dates)  # one per new (pid, lc_problem)
    updated_total_problems = total_problems + new_count

    # Sort and dedupe dates for streak math
    unique_dates = sorted(set(new_submission_dates))
    newest_date_in_batch = unique_dates[-1]

    # Update last_submission incrementally
    if last_submission is None:
        updated_last_submission = newest_date_in_batch
    else:
        updated_last_submission = max(last_submission, newest_date_in_batch)

    # 3) Compute updated current_streak and longest_streak
    today = date.today()

    # Case A: first-ever submissions for this user
    if last_submission is None and total_problems == 0:
        # All history is in this batch
        unique_dates = sorted(set(new_submission_dates))

        # One pass: compute longest_streak and current_streak (ending at today)
        ls = 0          # longest streak
        run = 0         # current run length while scanning
        prev = None
        cs = 0          # current streak ending at today (will stay 0 if no submission today)

        for d in unique_dates:
            if prev is None or (d - prev).days > 1:
                run = 1
            else:
                run += 1

            if run > ls:
                ls = run

            # If this date is today, the streak ending today has length = run
            if d == today:
                cs = run

            prev = d

        new_current_streak = cs
        new_longest_streak = ls

    # Case B: we already have a history; extend/reset based on new dates
    else:
        unique_dates = sorted(set(new_submission_dates))

        new_current_streak = current_streak
        new_longest_streak = longest_streak
        last = last_submission

        for d in unique_dates:
            # Ignore dates that are not after the last known submission;
            # they don't affect streak length, only the problem count.
            if last is not None and d <= last:
                continue

            if last is None:
                # Weird inconsistent state; treat as a new streak.
                new_current_streak = 1
            else:
                delta = (d - last).days
                if delta == 1:
                    # extends the streak
                    new_current_streak += 1
                else:
                    # gap > 1 day: new streak starting at this date
                    new_current_streak = 1

            last = d
            if new_current_streak > new_longest_streak:
                new_longest_streak = new_current_streak

        if last is not None:
            updated_last_submission = max(updated_last_submission, last)

        # Make current_streak truly "based on today":
        # if the last submission (across old + new data) is not today,
        # then there is no streak ending today.
        if updated_last_submission != today:
            new_current_streak = 0


    # 4) Write stats back to person (still inside caller's transaction)
    cursor.execute(
        """
        UPDATE person
        SET current_streak = %s,
            longest_streak = %s,
            total_problems = %s,
            last_submission = %s
        WHERE pid = %s
        """,
        (
            new_current_streak,
            new_longest_streak,
            updated_total_problems,
            updated_last_submission,
            pid,
        ),
    )


def refresh_user_submissions(
    conn,
    pid: int,
    username: str,
    limit: int = 20,
) -> int:
    """
    Fetch a user's recent accepted submissions from LeetCode and insert
    new (pid, lc_problem) rows into 'submission'.

    Also updates the person's:
      - current_streak
      - longest_streak
      - total_problems
      - last_submission

    All of this happens in a single transaction:
      - If anything fails, everything is rolled back.
      - If it succeeds, everything is committed together.

    Returns: number of NEW rows inserted into submission.
    """
    cursor = None
    new_submission_dates: List[date] = []
    new_count = 0

    try:
        cursor = dbi.dict_cursor(conn)

        submissions = fetch_recent_ac_submissions(username, limit=limit)

        for sub in submissions:
            title_slug = sub.get("titleSlug")
            ts = sub.get("timestamp")

            if not title_slug or ts is None:
                # Skip malformed entries
                continue

            # Convert timestamp (seconds) -> date (UTC)
            try:
                timestamp = int(ts)
            except (ValueError, TypeError):
                continue

            submission_date = datetime.fromtimestamp(
                timestamp, tz=timezone.utc
            ).date()

            # Resolve problem metadata using the shared cursor
            meta = get_problem_meta(cursor, title_slug)
            lc_problem = meta["lc_problem"]

            # Insert row into submission.
            # uniq_user_problem(pid, lc_problem) prevents duplicates for same user/problem.
            # INSERT IGNORE: duplicates are silently skipped.
            cursor.execute(
                """
                INSERT IGNORE INTO submission (pid, lc_problem, submission_date, coins)
                VALUES (%s, %s, %s, %s)
                """,
                (pid, lc_problem, submission_date, 0),
            )

            # For MySQL, rowcount will be 1 if inserted, 0 if ignored.
            if cursor.rowcount == 1:
                new_count += 1
                new_submission_dates.append(submission_date)

        # Update stats inside the same transaction, using the same cursor
        _update_person_stats(cursor, pid, new_submission_dates)

        # If we got here, everything succeeded
        conn.commit()
        return new_count

    except Exception:
        # Roll back ANY partial inserts or stats updates
        conn.rollback()
        raise

    finally:
        if cursor is not None:
            cursor.close()
