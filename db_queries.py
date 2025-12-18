# By Sophie Lin, Ashley Yang, Nessa Tong, Jessica Dai
# SQL queries to search the database
import cs304dbi as dbi
print(dbi.conf('leetcode_db'))

def get_profile(conn, pid):
    """ Retrieve all information from a user's profile based on pid"""
    curs = dbi.dict_cursor(conn)
    curs.execute('''
                 SELECT person.pid, name, username, lc_username, latest_submission, current_streak, longest_streak, total_problems, num_coins, personal_goal, last_refreshed, filename
                 FROM person left join picfile
                 ON person.pid = picfile.pid
                 WHERE person.pid = %s;
                 ''', [pid])
    result = curs.fetchone()
    curs.close()
    return result

def get_followers(conn, pid):
    """Get the users that the user's (with the pid) follows """
    curs = dbi.dict_cursor(conn)
    curs.execute('''
                SELECT p.pid, p.name, p.lc_username, p.username
                FROM person p
                JOIN `connection` c 
                ON p.pid = c.p1   -- p1 are the people that follow you
                WHERE c.p2 = %s -- you're p2
                AND p.pid <> %s; -- exclude yourself
    ''', [pid, pid])
    result = curs.fetchall()
    curs.close()
    return result

def get_follows(conn, pid):
    """ Get the users that the user's (with the pid) follows """

    curs = dbi.dict_cursor(conn)
    curs.execute('''
                SELECT p.pid, p.name, p.lc_username, p.username
                FROM person p
                JOIN `connection` c 
                    ON p.pid = c.p2  -- p2 are the people you follow
                WHERE c.p1 = %s -- p1 is you
                AND p.pid <> %s; -- exclude yourself
    ''', [pid, pid])
    result = curs.fetchall()
    curs.close()
    return result


def is_following(conn, follower_id, followed_id):
    """
    Returns 1 (in dictionary) if follower_id is following followed_id, returns None otherwise.
    """
    curs = dbi.dict_cursor(conn)
    curs.execute('''
    SELECT 1
    FROM connection
    WHERE p1 = %s AND p2 = %s''', 
    [follower_id, followed_id])
    result = curs.fetchone()
    curs.close()
    return result



def is_following(conn, follower_id, followed_id):
    """
    Returns 1 (in dictionary) if follower_id is following followed_id, returns None otherwise.
    """
    curs = dbi.dict_cursor(conn)
    curs.execute('''
    SELECT 1
    FROM connection
    WHERE p1 = %s AND p2 = %s''', 
    [follower_id, followed_id])
    result = curs.fetchone()
    curs.close()
    return result


def find_friends(conn, pid):
    """Find people who the user (pid) is NOT connected to"""
    curs = dbi.dict_cursor(conn)
    curs.execute('''
    select p.pid, p.name, p.lc_username  from person p where p.pid <> %s
    and p.pid not in (
      select c.p2 from connection c where c.p1 = %s
    )
    limit 30;
    ''', [pid, pid])
    result = curs.fetchall()
    curs.close()
    return result

def search_friends(conn, pid, search_term):
    """Find people who the user (pid) is NOT connected to based on a search term """
    search_term = f"%{search_term.lower()}%"
    curs = dbi.dict_cursor(conn)
    curs.execute('''
    select p.pid, p.name, p.lc_username 
    from person p 
    where p.pid <> %s
    and p.pid not in (
                 select c.p2 
                 from connection c 
                 where c.p1 = %s
    )
    AND (p.lc_username LIKE %s OR p.name LIKE %s)
    limit 30;
    ''', [pid, pid, search_term, search_term])
    result = curs.fetchall()
    curs.close()
    return result

def follow(conn, pid1, pid2):
    """ Create connection where user pid1 follows user pid2"""
    curs = dbi.dict_cursor(conn)
    curs.execute('''
    insert into `connection` (p1, p2)
    values (%s, %s)
    ''', [pid1, pid2])
    conn.commit()
    curs.close()

def unfollow(conn, pid1, pid2):
    """ Delete connection where user pid1 follows user pid2"""
    curs = dbi.dict_cursor(conn)
    curs.execute('''
    delete from `connection` 
    where p1 = %s and p2 = %s
    ''', [pid1, pid2])
    conn.commit()
    curs.close()

def edit_profile(conn, pid, name, username):
    """ updates profile with new name and username   """
    curs = dbi.dict_cursor(conn)
    curs.execute('''
    update person
    set name = %s, username = %s
    where pid = %s;
    ''', [name, username, pid])
    conn.commit()
    curs.close()

def upload_profile_pic(conn, pid, filename):
    """
    Inserts or updates filename of the uploaded profile picture of the user
    """
    curs = dbi.dict_cursor(conn)
    curs.execute('''insert into picfile(pid, filename)
                    values (%s, %s)
                    on duplicate key update 
                    filename=%s''', [pid, filename, filename])
    conn.commit()
    curs.close()

# Login/auth queries

def username_exists(conn, username):
    """checks if username exists"""
    curs = dbi.dict_cursor(conn)
    curs.execute('SELECT 1 FROM person WHERE username=%s', [username])
    return curs.fetchone() is not None

def lc_username_exists(conn, lc_username):
    """checks if leetcode username exists """
    curs = dbi.dict_cursor(conn)
    curs.execute('SELECT 1 FROM person WHERE lc_username=%s', [lc_username])
    return curs.fetchone() is not None

def create_person(conn, name, username, lc_username):
    """Create a new person and return the new pid (no commit here)."""
    curs = dbi.dict_cursor(conn)
    curs.execute(
        '''
        INSERT INTO person (name, username, lc_username, current_streak, longest_streak,
                            total_problems, num_coins)
        VALUES (%s, %s, %s, NULL, NULL, NULL, 0)
        ''',
        [name, username, lc_username]
    )
    new_row = curs.lastrowid
    curs.close()
    return new_row

def create_userpass(conn, pid, hashed):
    """Insert password for the user (no commit here)."""
    curs = dbi.dict_cursor(conn)
    try:
        curs.execute(
            '''
            INSERT INTO userpass (pid, hashed)
            VALUES (%s, %s)
            ''',
            [pid, hashed]
        )
    except Exception:
        raise
    finally:
        curs.close()

def get_login_info(conn, username):
    """Return person info + password hash for login."""
    curs = dbi.dict_cursor(conn)
    curs.execute('''
        SELECT p.pid, p.username, u.hashed
        FROM person AS p
        JOIN userpass AS u ON p.pid = u.pid
        WHERE p.username = %s
    ''', [username])
    return curs.fetchone()

# Group queries

def get_party_invite_options(conn, pid, cpid=None, limit=50):
    """
    Returns all friends/followers/following of pid.
    If cpid is provided, skip users who are already in the party.
    """
    curs = dbi.dict_cursor(conn)
    
    # This case is: fetching friend list(potential invitees) for a PRE EXISTING PARTY
    if cpid:
        # queries for friends pid, name
        # gets all the people who either followed this person or who this person followed
        # that are NOT in the party
        curs.execute('''
            SELECT DISTINCT
                p.pid,
                p.name,
                p.username
            FROM person p
            JOIN connection c
            ON (c.p1 = %s AND c.p2 = p.pid)
            OR (c.p2 = %s AND c.p1 = p.pid)
            LEFT JOIN party_membership pm
            ON pm.pid = p.pid
            AND pm.cpid = %s
            WHERE pm.cpid IS NULL
            LIMIT %s;
        ''', [pid, pid, cpid, limit])

    # This case is: fetching friend list(potential invitees) for a NEW PARTY IN CREATION
    else:
        curs.execute('''
            SELECT DISTINCT p.pid, p.name, p.lc_username
            FROM person p
            JOIN connection c
              ON (c.p1=%s AND c.p2=p.pid) OR (c.p2=%s AND c.p1=p.pid)
            LIMIT %s
        ''', [pid, pid, limit])
    
    return curs.fetchall()
 

def create_code_party(conn, party_name, party_goal, party_start, party_end):
    """Create a new code party and return its cpid"""
    curs = dbi.dict_cursor(conn)
    curs.execute('''
        INSERT INTO code_party (name, party_goal, party_start, party_end)
        VALUES (%s, %s, %s, %s)
    ''', [party_name, party_goal, party_start, party_end])
    return curs.lastrowid

def assign_user_to_party(conn, pid, cpid):
    """Add a user to a party"""
    curs = dbi.dict_cursor(conn)
    #look into how to handle an error of in case someone tries to insert a duplicate!! / read about insert ignore?
    curs.execute('''
        INSERT INTO party_membership (pid, cpid)
        VALUES (%s, %s)
    ''', [pid, cpid])


def assign_invitees_to_party(conn, cpid, pid_list):
    """
    Assigns multiple users(invitee list) to a party. 
    Returns the cpid of the party.
    """
    if not pid_list:
        return cpid

    curs = dbi.dict_cursor(conn)
    # setup prepared query for (pid, cpid) pairs to add to membership table
    rows = [(pid, cpid) for pid in pid_list]
    #executes a bunch of these inserts given our (pid, cpid) tuples
    curs.executemany(
        '''INSERT INTO party_membership (pid, cpid)
           VALUES (%s, %s)''',
        rows
    )
    return cpid


def get_party_info(conn, cpid):
    """
    Returns data for a code party.
    """
    curs = dbi.dict_cursor(conn)
    curs.execute('''
                 SELECT cpid, name, party_goal, party_start, party_end, winner, last_bulk_refresh 
                 FROM code_party 
                 WHERE cpid=%s;
                 ''', [cpid])
    result = curs.fetchone()
    curs.close()
    return result

def get_party_members(conn, cpid):
    """
    Returns all users assigned to a given party.
    """
    curs = dbi.dict_cursor(conn)
    curs.execute('''
        SELECT p.pid, p.username, p.lc_username, p.name
        FROM person p
        JOIN party_membership pm ON pm.pid = p.pid
        WHERE pm.cpid = %s
    ''', [cpid])
    return curs.fetchall()

def get_party_submissions(conn, cpid):
    """
    Returns all submissions made by members in the party with cpid
    """
    curs = dbi.dict_cursor(conn)
    curs.execute(
        '''
        SELECT 
            p.name, 
            p.username, 
            prob.difficulty,
            sub.submission_date
        FROM person p
        INNER JOIN submission sub ON sub.pid = p.pid
        INNER JOIN problem prob ON prob.lc_problem = sub.lc_problem
        INNER JOIN party_membership mem ON mem.pid = p.pid
        INNER JOIN code_party party ON party.cpid = mem.cpid
        WHERE mem.cpid = %s
        AND sub.submission_date >= party.party_start
        AND sub.submission_date < party.party_end;
        ''', [cpid]
    )
    result = curs.fetchall()
    curs.close()
    return result


def get_party_submissions(conn, cpid):
    """
    Returns all submissions made by members in the party with cpid
    """
    curs = dbi.dict_cursor(conn)
    curs.execute(
        '''
        SELECT 
            p.name, 
            p.username, 
            prob.difficulty,
            sub.submission_date
        FROM person p
        INNER JOIN submission sub ON sub.pid = p.pid
        INNER JOIN problem prob ON prob.lc_problem = sub.lc_problem
        INNER JOIN party_membership mem ON mem.pid = p.pid
        INNER JOIN code_party party ON party.cpid = mem.cpid
        WHERE mem.cpid = %s
        AND sub.submission_date >= party.party_start
        AND sub.submission_date < party.party_end;
        ''', [cpid]
    )
    result = curs.fetchall()
    curs.close()
    return result


def remove_user_from_party(conn, pid, cpid):
    """Remove a user from a party"""
    curs = dbi.dict_cursor(conn)
    curs.execute('''
        DELETE FROM party_membership
        WHERE pid=%s AND cpid=%s
    ''', [pid, cpid])

def get_parties_for_user(conn, pid):
    """
    Returns all code parties that a user is a member of 
    AND dynamically computes the status.
    """
    curs = dbi.dict_cursor(conn)
    curs.execute('''
        SELECT cp.cpid, cp.name, cp.party_start, cp.party_end,
            CASE 
                WHEN CURDATE() < cp.party_start then 'upcoming'
                WHEN CURDATE() > cp.party_end then 'completed'
                ELSE 'in_progress'
            END AS status
        FROM code_party cp
        JOIN party_membership pm ON cp.cpid = pm.cpid
        WHERE pm.pid = %s
        ORDER BY cp.party_start DESC
    ''', [pid])
    return curs.fetchall()


def get_parties_for_user(conn, pid):
    """
    Returns all code parties (name + status) that a user is a member of.
    """
    curs = dbi.dict_cursor(conn)
    curs.execute('''
        SELECT cp.cpid, cp.name, cp.party_start, cp.party_end,
            CASE 
                WHEN CURDATE() < cp.party_start then 'upcoming'
                WHEN CURDATE() > cp.party_end then 'completed'
                ELSE 'in_progress'
            END AS status
        FROM code_party cp
        JOIN party_membership pm ON cp.cpid = pm.cpid
        WHERE pm.pid = %s
        ORDER BY cp.party_start DESC
    ''', [pid])
    return curs.fetchall()


def update_party_last_refreshed(conn, cpid):
    """Updates the timestamp that the whole party's leetcode database stats were last 
    refreshed - it happens on button press on party page only
    """
    curs = dbi.dict_cursor(conn)
    curs.execute('UPDATE code_party SET last_bulk_refresh = NOW() WHERE cpid=%s', [cpid])

#HOMEPAGE leaderboard
def get_leaderboard(conn, limit=10):
    curs = dbi.dict_cursor(conn)
    curs.execute("""
        SELECT person.pid, username, lc_username, num_coins, filename
        FROM person left join picfile
        ON person.pid = picfile.pid
        ORDER BY num_coins DESC
        LIMIT %s
    """, [limit])
    return curs.fetchall()

def get_problems_solved_today(conn, pid: int) -> int:
    curs = dbi.dict_cursor(conn)
    curs.execute(
        """
        SELECT COUNT(*) AS problems_today
        FROM submission
        WHERE pid = %s
          AND DATE(submission_date) = CURRENT_DATE
        """,
        (pid,)
    )
    row = curs.fetchone()
    return row["problems_today"] if row else 0


def get_profile_pic(conn, pid):
    curs = dbi.dict_cursor(conn)
    curs.execute("""
                select filename
                from picfile
                where pid=%s""", [pid])
    return curs.fetchone()

def get_upcoming_mutual_parties(conn, pid, limit=5):
    """
    Return upcoming parties where your friends are part of but u arent, max 5 parties
    """
    curs = dbi.dict_cursor(conn)

    curs.execute("""
    SELECT DISTINCT cp.cpid, cp.name, cp.party_start, cp.party_end
    FROM code_party cp
    JOIN party_membership pm ON pm.cpid = cp.cpid
    JOIN connection c ON c.p2 = pm.pid
    WHERE cp.party_start > CURDATE()          -- upcoming
      AND c.p1 = %s                           -- you
      AND pm.pid != %s                         -- exclude yourself
      AND cp.cpid NOT IN (
          SELECT cpid FROM party_membership WHERE pid = %s
      )
    ORDER BY cp.party_start ASC
    LIMIT %s
    """, [pid, pid, pid, limit])

    result = curs.fetchall()
    curs.close()
    return result

    result = curs.fetchall()
    curs.close()
    return result
