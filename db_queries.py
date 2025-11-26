# By Sophie Lin, Ashley Yang, Nessa Tong, Jessica Dai

import cs304dbi as dbi
print(dbi.conf('leetcode_db'))

def get_profile(conn, pid):
    curs = dbi.dict_cursor(conn)
    curs.execute('''
    select * from person
    where pid = %s;
    ''', 
    [pid])
    result = curs.fetchone()
    curs.close()
    return result

def get_username(conn, pid):
    curs = dbi.dict_cursor(conn)
    curs.execute('''
    select lc_username from person
    where pid = %s;
    ''', 
    [pid])
    result = curs.fetchone()
    curs.close()
    return result

def get_friends(conn, pid):
    ''' Get current friends '''
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
    '''find ppl who you aren't connected to '''
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


def create_userpass(conn, username, hashed, person_id):
    """Insert into userpass table."""
    curs = dbi.dict_cursor(conn)
    curs.execute('''
        INSERT INTO userpass (username, hashed, person_id)
        VALUES (%s, %s, %s)
    ''', [username, hashed, person_id])
    conn.commit()


def get_userpass_by_username(conn, username):
    """Return row from userpass for login."""
    curs = dbi.dict_cursor(conn)
    curs.execute('''
        SELECT username, hashed, person_id
        FROM userpass
        WHERE username = %s
    ''', [username])
    return curs.fetchone()


def get_person_by_pid(conn, pid):
    """Return profile for profile page."""
    curs = dbi.dict_cursor(conn)
    curs.execute('SELECT * FROM person WHERE pid=%s', [pid])
    return curs.fetchone()

# Group queries

def get_connections_with_group_status(conn, pid):
    """
    Returns all friends of pid, including the group ID they belong to.
    If gid is NULL, the friend is not in a group.
    """
    curs = dbi.dict_cursor(conn)
    curs.execute('''
        SELECT p.pid, p.name, p.lc_username, p.gid
        FROM person p
        JOIN connection c
          ON (c.p1=%s AND c.p2=p.pid)
          OR (c.p2=%s AND c.p1=p.pid)
    ''', [pid, pid])
    return curs.fetchall()

def create_group(conn, group_goal, comp_start, comp_end):
    """
    Creates a new group and returns its gid.
    """
    curs = dbi.dict_cursor(conn)
    curs.execute('''
        INSERT INTO groups (group_goal, comp_start, comp_end)
        VALUES (%s, %s, %s)
    ''', [group_goal, comp_start, comp_end])
    conn.commit()
    return curs.lastrowid


def assign_user_to_group(conn, pid, gid):
    """
    Assign a user to a group.
    """
    curs = dbi.dict_cursor(conn)
    curs.execute('''
        UPDATE person
        SET gid = %s
        WHERE pid = %s
    ''', [gid, pid])
    conn.commit()


def assign_multiple_users_to_group(conn, gid, pid_list):
    """
    Assigns multiple users to a given group.
    """
    if not pid_list:
        return gid

    curs = dbi.dict_cursor(conn)
    placeholders = ",".join(["%s"] * len(pid_list))
    query = f'''
        UPDATE person
        SET gid = %s
        WHERE pid IN ({placeholders})
    '''
    curs.execute(query, [gid] + pid_list)
    conn.commit()
    return gid


def get_group_info(conn, gid):
    """
    Returns data for a group.
    """
    curs = dbi.dict_cursor(conn)
    curs.execute("SELECT * FROM groups WHERE gid=%s", [gid])
    return curs.fetchone()


def get_group_members(conn, gid):
    """
    Returns all users assigned to a given group.
    """
    curs = dbi.dict_cursor(conn)
    curs.execute("SELECT * FROM person WHERE gid=%s", [gid])
    return curs.fetchall()

def remove_user_from_group(conn, pid, gid):
    """Remove a user from a group by clearing gid."""
    curs = dbi.dict_cursor(conn)
    curs.execute('''
        UPDATE person
        SET gid=NULL
        WHERE pid=%s AND gid=%s
    ''', [pid, gid])
    conn.commit()
    
if __name__ == '__main__':
    dbi.conf("wmdb")
    conn=dbi.connect()