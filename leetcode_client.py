import requests
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


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


def _get_problem_from_db(cursor, title_slug: str) -> Optional[Dict[str, Any]]:
    """
    Try to load problem metadata from the MySQL 'problem' table by title_slug.

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
        SELECT lc_problem, title, difficulty
        FROM problem
        WHERE title_slug = %s
        """,
        (title_slug,),
    )
    row = cursor.fetchone()
    if not row:
        return None

    # Support both tuple cursors and dict cursors
    if isinstance(row, dict):
        lc_problem = int(row["lc_problem"])
        title = row["title"]
        difficulty = row["difficulty"]
    else:
        lc_problem = int(row[0])
        title = row[1]
        difficulty = row[2]

    return {
        "lc_problem": lc_problem,
        "title": title,
        "difficulty": difficulty,
    }


def _insert_problem_into_db(cursor, meta: Dict[str, Any], title_slug: str) -> None:
    """
    Insert or update a row in the 'problem' table from a metadata dict.
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


def get_problem_meta(conn, title_slug: str) -> Dict[str, Any]:
    """
    Resolve a problem slug to (lc_problem, title, difficulty), using:

    1. MySQL 'problem' table
    2. LeetCode GraphQL (if not found in DB)
    """
    cursor = conn.cursor()

    # Try DB
    meta = _get_problem_from_db(cursor, title_slug)
    if meta is not None:
        cursor.close()
        return meta

    # Fallback to LeetCode and write to DB
    meta = _fetch_problem_meta_from_leetcode(title_slug)
    _insert_problem_into_db(cursor, meta, title_slug)
    conn.commit()
    cursor.close()

    return meta


def refresh_user_submissions(
    conn,
    pid: int,
    username: str,
    limit: int = 20,
) -> int:
    """
    Fetch a user's recent accepted submissions from LeetCode and insert
    new (pid, lc_problem) rows into 'submission'.

    Expects 'submission' schema:

    CREATE TABLE submission (
      sid             INT AUTO_INCREMENT PRIMARY KEY,
      pid             INT NOT NULL,
      lc_problem      INT NOT NULL,
      submission_date DATE NOT NULL,
      coins           INT DEFAULT 0,
      UNIQUE KEY uniq_user_problem (pid, lc_problem),
      FOREIGN KEY (pid)        REFERENCES person(pid),
      FOREIGN KEY (lc_problem) REFERENCES problem(lc_problem)
    );

    Returns: number of NEW rows inserted into submission.
    """
    cursor = conn.cursor()

    submissions = fetch_recent_ac_submissions(username, limit=limit)
    new_count = 0

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

        submission_date = datetime.fromtimestamp(timestamp, tz=timezone.utc).date()

        # Resolve problem metadata (lc_problem etc. comes via the 'problem' table)
        meta = get_problem_meta(conn, title_slug)
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

    conn.commit()
    cursor.close()
    return new_count
