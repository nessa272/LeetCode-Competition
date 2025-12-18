# Written by Jessica Dai, Sophie Lin, Nessa Tong, Ashley Yang (Olin)
import requests
from datetime import datetime, timezone, timedelta, date
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional
import cs304dbi as dbi

LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"
EASY_COIN_VALUE = 1
MED_COIN_VALUE = 5
HARD_COIN_VALUE = 7


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
    Recompute current_streak, longest_streak, total_problems, latest_submission,
    and num_coins for the given pid *purely from the submission + problem tables*.

    Assumes:
      - cursor is a dict-style cursor inside an open transaction.
      - submission has columns: pid, lc_problem, submission_date.
      - problem has columns: lc_problem, difficulty ('easy'/'medium'/'hard').
    """

    # 1) Get submission dates and distinct problems for this user
    cursor.execute(
        """
        SELECT lc_problem, submission_date
        FROM submission
        WHERE pid = %s
        ORDER BY submission_date
        """,
        (pid,),
    )
    rows = cursor.fetchall()

    if not rows:
        # No submissions at all: zero out stats
        total_problems = 0
        current_streak = 0
        longest_streak = 0
        latest_submission = None
        num_coins = 0
    else:
        # Distinct problems solved
        problems = {r["lc_problem"] for r in rows}
        total_problems = len(problems)

        # Streak + latest_submission
        dates = [r["submission_date"] for r in rows]
        latest_submission = dates[-1]

        today = date.today()
        longest_streak = 0
        run = 0
        prev = None

        for d in dates:
            if prev is None or (d - prev).days > 1:
                run = 1
            else:
                run += 1

            if run > longest_streak:
                longest_streak = run

            prev = d

        if latest_submission == today:
            current_streak = run
        else:
            current_streak = 0

        # 2) Compute num_coins in Python from difficulty
        #    (one row per submission; duplicates count as multiple coins)
        cursor.execute(
            """
            SELECT p.difficulty
            FROM submission s
            JOIN problem p ON s.lc_problem = p.lc_problem
            WHERE s.pid = %s
            """,
            (pid,),
        )
        diff_rows = cursor.fetchall()

        num_coins = 0
        for r in diff_rows:
            diff = r["difficulty"]
            if diff == "easy":
                num_coins += EASY_COIN_VALUE
            elif diff == "medium":
                num_coins += MED_COIN_VALUE
            elif diff == "hard":
                num_coins += HARD_COIN_VALUE
            # if difficulty is NULL/unknown, treat as 0 coins

    # 3) write back to person, including num_coins and last_refreshed
    cursor.execute(
        """
        UPDATE person
        SET current_streak    = %s,
            longest_streak    = %s,
            total_problems    = %s,
            latest_submission = %s,
            num_coins         = %s,
            last_refreshed    = NOW()
        WHERE pid = %s
        """,
        (
            current_streak,
            longest_streak,
            total_problems,
            latest_submission,
            num_coins,
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
    new (pid, lc_problem, submission_date) rows into 'submission'.

    Coins are derived from problem.difficulty via EASY/MED/HARD_COIN_VALUE inside
    _recompute_person_stats.

    After inserting new submissions, recompute the person's stats
    (current_streak, longest_streak, total_problems, latest_submission, num_coins)
    from the submission + problem tables.

    Returns: number of NEW rows inserted into submission.
    """
    cursor = None
    new_count = 0

    
    cursor = dbi.dict_cursor(conn)
    EST = ZoneInfo("America/New_York")

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
            timestamp, tz=EST
        ).date()

        meta = get_problem_meta(cursor, title_slug)
        lc_problem = meta["lc_problem"]

        cursor.execute(
            """
            INSERT IGNORE INTO submission (pid, lc_problem, submission_date)
            VALUES (%s, %s, %s)
            """,
            (pid, lc_problem, submission_date),
        )

        if cursor.rowcount == 1:
            new_count += 1

    # recompute stats (including num_coins) from the truth in DB
    _recompute_person_stats(cursor, pid)

    cursor.close()
    return new_count
