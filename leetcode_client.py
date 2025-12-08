# Written by Jessica Dai, Sophie Lin, Nessa Tong, Ashley Yang (Olin)
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

def _recompute_person_stats(cursor, pid: int) -> None:
    """
    Recompute current_streak, longest_streak, total_problems, and latest_submission
    for the given pid *purely from the submission table*.

    Assumes:
      - cursor is a dict-style cursor inside an open transaction.
      - submission has columns: pid, lc_problem, submission_date.
    """

    # 1) total_problems = number of distinct problems solved by this user
    cursor.execute(
        """
        SELECT COUNT(DISTINCT lc_problem) AS total_problems
        FROM submission
        WHERE pid = %s
        """,
        (pid,),
    )
    row = cursor.fetchone()
    total_problems = row["total_problems"] if row and row["total_problems"] is not None else 0

    # 2) get all distinct submission dates in order for streak computation
    cursor.execute(
        """
        SELECT DISTINCT submission_date
        FROM submission
        WHERE pid = %s
        ORDER BY submission_date
        """,
        (pid,),
    )
    rows = cursor.fetchall()

    if not rows:
        # No submissions at all: zero out stats
        current_streak = 0
        longest_streak = 0
        latest_submission = None
    else:
        dates = [r["submission_date"] for r in rows]
        latest_submission = dates[-1]

        today = date.today()
        longest_streak = 0
        run = 0
        prev = None

        # Scan forward to find longest streak; track run ending at latest date in `run`
        for d in dates:
            if prev is None or (d - prev).days > 1:
                run = 1
            else:
                run += 1

            if run > longest_streak:
                longest_streak = run

            prev = d

        # `run` is the streak length ending at the last date we saw.
        if latest_submission == today:
            current_streak = run
        else:
            current_streak = 0

    # 3) write back to person
    cursor.execute(
        """
        UPDATE person
        SET current_streak   = %s,
            longest_streak   = %s,
            total_problems   = %s,
            latest_submission = %s
        WHERE pid = %s
        """,
        (
            current_streak,
            longest_streak,
            total_problems,
            latest_submission,
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

    Also assigns coins based on difficulty:
    easy=1, medium=2, hard=3.

    Then recompute the person's stats (current_streak, longest_streak,
    total_problems, latest_submission) *from the submission table*.

    Returns: number of NEW rows inserted into submission.
    """
    cursor = None
    new_count = 0
    coins_earned = 0

    try:
        cursor = dbi.dict_cursor(conn)

        submissions = fetch_recent_ac_submissions(username, limit=limit)

        for sub in submissions:
            title_slug = sub.get("titleSlug")
            ts = sub.get("timestamp")

            if not title_slug or ts is None:
                continue

            try:
                timestamp = int(ts)
            except (ValueError, TypeError):
                continue

            submission_date = datetime.fromtimestamp(
                timestamp, tz=timezone.utc
            ).date()

            meta = get_problem_meta(cursor, title_slug)
            lc_problem = meta["lc_problem"]
            difficulty = meta["difficulty"]

            if difficulty == "easy":
                coin_value = 1
            elif difficulty == "medium":
                coin_value = 2
            else:
                coin_value = 3

            cursor.execute(
                """
                INSERT IGNORE INTO submission (pid, lc_problem, submission_date, coins)
                VALUES (%s, %s, %s, %s)
                """,
                (pid, lc_problem, submission_date, coin_value),
            )

            if cursor.rowcount == 1:
                new_count += 1
                coins_earned += coin_value

        # recompute stats from the truth in `submission`
        _recompute_person_stats(cursor, pid)
        update_user_coins(cursor, pid, coins_earned)

        conn.commit()
        return new_count

    except Exception:
        conn.rollback()
        raise

    finally:
        if cursor is not None:
            cursor.close()

def update_user_coins(cursor, pid: int, coins_earned: int) -> None:
    """
    Increment a user's coins by coins_earned (if >0) and update last_refreshed.
    """
    if coins_earned > 0:
        cursor.execute(
            """
            UPDATE person
            SET num_coins = num_coins + %s,
                last_refreshed = NOW()
            WHERE pid = %s
            """,
            (coins_earned, pid),
        )
    else:
        cursor.execute(
            """
            UPDATE person
            SET last_refreshed = NOW()
            WHERE pid = %s
            """,
            (pid,),
        )

