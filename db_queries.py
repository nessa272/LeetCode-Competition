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
    return curs.fetchone()

def get_username(conn, pid):
    curs = dbi.dict_cursor(conn)
    curs.execute('''
    select lc_username from person
    where pid = %s;
    ''', 
    [pid])
    return curs.fetchone()

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
    return curs.fetchall()

def connect(conn, pid1, pid2):
    curs = dbi.dict_cursor(conn)
    curs.execute('''
    insert into connection (p1, p2)
    values (%s, %s)
    ''', [pid1, pid2])
    conn.commit()

if __name__ == '__main__':
    dbi.conf("wmdb")
    conn=dbi.connect()
    #movie = find_friends(conn)
    #print('{title} born on {release} '
    #        .format(title=movie['title'],
    #                release=movie['release']))