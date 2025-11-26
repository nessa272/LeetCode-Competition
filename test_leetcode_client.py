# Written by Jessica Dai, Sophie Lin, Nessa Tong, Ashley Yang (Olin)
import cs304dbi as dbi
from leetcode_client import (
    fetch_recent_ac_submissions,
    get_problem_meta,
    refresh_user_submissions,
)

# --- 1. Connect to database ---
print(dbi.conf('leetcode_db'))
conn = dbi.connect()

# --- 2. Test username ---
pid = 2  # replace with your actual PID
username = "jessicajjdai"

print("Testing LeetCode client...\n")

# --- 3. Test fetch_recent_ac_submissions ---
print("Fetching recent 10 submissions from LeetCode...")
subs = fetch_recent_ac_submissions(username, limit=10)
print("Received:", len(subs))
if subs:
    print("First submission:", subs[0])
else:
    print("No AC submissions found. Try solving one problem first.")

# --- 4. Test refresh_user_submissions ---
print("\nRefreshing submissions into database...")
added = refresh_user_submissions(conn, pid, username, limit=10)
print(f"Inserted {added} new submission rows.")

print("\nSuccess!")
