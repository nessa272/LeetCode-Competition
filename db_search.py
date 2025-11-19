# By Sophie Lin, Ashley Yang, Nessa Tong, Jessica Dai

import cs304dbi as dbi
print(dbi.conf('leetcode_db'))

def get_profile(conn, username):
    curs = dbi.dict_cursor(conn)
    curs.execute('''
    select * from person
    where username = %s";
    ''', 
    [username])
    return curs.fetchone()
