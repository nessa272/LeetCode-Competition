# By Sophie Lin, Ashley Yang, Nessa Tong, Jessica Dai
# SQL queries to search the database
import cs304dbi as dbi
print(dbi.conf('leetcode_db'))

def get_profile(conn, pid):
    '''
    Retrieve all information from a user's profile based on pid
    '''
    curs = dbi.dict_cursor(conn)
    curs.execute('''
    select * from person
    where pid = %s;
    ''', 
    [pid])
    result = curs.fetchone()
    curs.close()
    return result


def get_friends(conn, pid):
    '''
    Get the friends of the personw ith the pid
    '''
    curs = dbi.dict_cursor(conn)
    curs.execute('''
    select p.pid, p.name, p.lc_username from person p
    inner join connection c 
        on p.pid = c.p1 or p.pid = c.p2
    where %s in (c.p1, c.p2)
        and p.pid <> %s;
    ''', [pid, pid])
    result = curs.fetchall()
    curs.close()
    return result

def find_friends(conn, pid):
    '''
    Find people who the user (pid) is NOT connected to
    '''
    curs = dbi.dict_cursor(conn)
    curs.execute('''
    select p.pid, p.name, p.lc_username  from person p where p.pid <> %s
    and p.pid not in (
      select c.p2 from connection c where c.p1 = %s
      union
      select c.p1 from connection c where c.p2 = %s
    )
    limit 10;
    ''', [pid, pid, pid])
    result = curs.fetchall()
    curs.close()
    return result

def connect(conn, pid1, pid2):
    '''
    Add a connection between two users
    '''
    curs = dbi.dict_cursor(conn)
    curs.execute('''
    insert into connection (p1, p2)
    values (%s, %s)
    ''', [pid1, pid2])
    conn.commit()
    curs.close()

# Login/auth queries

def create_person(conn, username, lc_username):
    """Create a new person and return the new pid."""
    curs = dbi.dict_cursor(conn)
    curs.execute('''
        INSERT INTO person (username, lc_username, current_streak, longest_streak,
                            total_problems, num_coins)
        VALUES (%s, %s, NULL, NULL, NULL, NULL)
    ''', [username, lc_username])
    conn.commit()
    return curs.lastrowid

def create_userpass(conn, pid, hashed):
    """Insert into userpass table."""
    curs = dbi.dict_cursor(conn)
    curs.execute('''
        INSERT INTO userpass (pid, hashed)
        VALUES (%s, %s)
    ''', [pid, hashed])
    conn.commit()

def get_login_info(conn, username):
    """Return person info + password hash for login."""
    curs = dbi.dict_cursor(conn)
    curs.execute('''
        SELECT p.*, u.hashed
        FROM person AS p
        JOIN userpass AS u ON p.pid = u.pid
        WHERE p.username = %s
    ''', [username])
    return curs.fetchone()


def get_person_by_pid(conn, pid):
    """Return profile for profile page."""
    curs = dbi.dict_cursor(conn)
    curs.execute('SELECT * FROM person WHERE pid=%s', [pid])
    return curs.fetchone()

# Group queries

def get_party_invite_options(conn, pid, cpid=None):
    """
    Returns all friends/followers/following of pid.
    If cpid is provided, include whether they are already in that party.
    """
    curs = dbi.dict_cursor(conn)
    
    # This case is: fetching friend list(potential invitees) for a PRE EXISTING PARTY
    if cpid:
        # queries for friends pid, name, and in_party status (if they are already in this party or not)
        # gets all the people who either followed this person or who this person followed
        curs.execute('''
            SELECT p.pid, p.name, p.lc_username,
                   CASE WHEN pm.cpid IS NOT NULL THEN 1 ELSE 0 END AS in_party
            FROM person p
            JOIN connection c
              ON (c.p1=%s AND c.p2=p.pid) OR (c.p2=%s AND c.p1=p.pid)
            LEFT JOIN party_membership pm
              ON pm.pid = p.pid AND pm.cpid = %s
        ''', [pid, pid, cpid])

    # This case is: fetching friend list(potential invitees) for a NEW PARTY IN CREATION
    else:
        curs.execute('''
            SELECT p.pid, p.name, p.lc_username
            FROM person p
            JOIN connection c
              ON (c.p1=%s AND c.p2=p.pid) OR (c.p2=%s AND c.p1=p.pid)
        ''', [pid, pid])
    
    return curs.fetchall()
 

def create_code_party(conn, party_name, party_goal, party_start, party_end):
    """Create a new code party and return its cpid"""
    curs = dbi.dict_cursor(conn)
    curs.execute('''
        INSERT INTO code_party (name, party_goal, party_start, party_end)
        VALUES (%s, %s, %s, %s)
    ''', [party_name, party_goal, party_start, party_end])
    conn.commit()
    return curs.lastrowid

def assign_user_to_party(conn, pid, cpid):
    """Add a user to a party"""
    curs = dbi.dict_cursor(conn)
    #look into how to handle an error of in case someone tries to insert a duplicate!! / read about insert ignore?
    curs.execute('''
        INSERT INTO party_membership (pid, cpid)
        VALUES (%s, %s)
    ''', [pid, cpid])
    conn.commit()


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
    conn.commit()
    return cpid


def get_party_info(conn, cpid):
    """
    Returns data for a code party.
    """
    curs = dbi.dict_cursor(conn)
    curs.execute("SELECT * FROM code_party WHERE cpid=%s", [cpid])
    return curs.fetchone()


def get_party_members(conn, cpid):
    """
    Returns all users assigned to a given party.
    """
    curs = dbi.dict_cursor(conn)
    curs.execute('''
        SELECT p.*
        FROM person p
        JOIN party_membership pm ON pm.pid = p.pid
        WHERE pm.cpid = %s
    ''', [cpid])
    return curs.fetchall()

def remove_user_from_party(conn, pid, cpid):
    """Remove a user from a party"""
    curs = dbi.dict_cursor(conn)
    curs.execute('''
        DELETE FROM party_membership
        WHERE pid=%s AND cpid=%s
    ''', [pid, cpid])
    conn.commit()

def get_parties_for_user(conn, pid):
    """
    Returns all code parties (name + status) that a user is a member of.
    """
    curs = dbi.dict_cursor(conn)
    curs.execute('''
        SELECT cp.cpid, cp.name, cp.status, cp.party_start, cp.party_end
        FROM code_party cp
        JOIN party_membership pm ON cp.cpid = pm.cpid
        WHERE pm.pid = %s
        ORDER BY cp.party_start DESC
    ''', [pid])
    return curs.fetchall()

    
if __name__ == '__main__':
    dbi.conf("leetcode_db")
    conn=dbi.connect()