from flask import (Flask, render_template, make_response, url_for, request,
                   redirect, flash, session, send_from_directory, jsonify)
from werkzeug.utils import secure_filename
app = Flask(__name__)

import secrets
import cs304dbi as dbi
import db_queries
import bcrypt_utils as bc
from leetcode_client import refresh_user_submissions

# we need a secret_key to use flash() and sessions
app.secret_key = secrets.token_hex()

# configure DBI
print(dbi.conf('leetcode_db'))

# This gets us better error messages for certain common request errors
app.config['TRAP_BAD_REQUEST_ERRORS'] = True

@app.route('/')
def index():
    if "pid" in session:
        return render_template('main.html', page_title='Main Page')
    return render_template("login.html") #prompt to login
    

@app.route('/about/')
def about():
    #flash('this is a flashed message')
    return render_template('about.html', page_title='About Us')

@app.route('/profile/<pid>')
def profile(pid):
    '''
    Loads a user's profile based on input pid.
    '''
    conn=dbi.connect()
    profile = db_queries.get_profile(conn, pid) # query
    print(profile)
    conn.close()
    # show profile
    return render_template('profile.html', profile=profile)

def refresh_profile(pid: int, username: str):
    conn = dbi.connect()
    num_submissions = refresh_user_submissions(conn, pid, username)
    print(f"{num_submissions} submissions added to database for username {username}")
    conn.close()

def refresh_all():
    conn = dbi.connect()
    curs = dbi.dict_cursor(conn)
    curs.execute('''
                 SELECT pid, lc_username
                 FROM person
                 ''')
    people = curs.fetchall()
    for person in people:
        refresh_profile(person['pid'], person['lc_username'])
    conn.close()

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        return render_template('signup.html')

    # else: POST request
    username = request.form.get('username')
    password = request.form.get('password1')
    lc_username = request.form.get('lc_username')

    if not username or not password or not lc_username:
        flash("All fields are required.")
        return redirect(url_for('signup'))

    conn = dbi.connect()
    curs = dbi.dict_cursor(conn)

    # Create new person in database
    try:
        curs.execute('''
            INSERT INTO person (lc_username, current_streak, longest_streak,
                                total_problems, num_coins)
            VALUES (%s, 0, 0, 0, 0)
        ''', [lc_username])
        person_id = curs.lastrowid
    except Exception as err:
        flash(f"Error creating person record: {err}")
        return redirect(url_for('signup'))

    hashed = bc.signup_hash(password) # Hash password

    # Put in database
    try:
        curs.execute('''
            INSERT INTO userpass (username, hashed, person_id)
            VALUES (%s, %s, %s)
        ''', [username, hashed, person_id])
        conn.commit()
    except Exception as err:
        flash(f"Username already taken.")
        return redirect(url_for('signup'))

    # successfully added, sign them in and bring back to main page
    session['pid'] = person_id
    session['username'] = username

    flash("Account created successfully!")
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    # else: POST
    username = request.form.get('username')
    password = request.form.get('password')

    conn = dbi.connect()
    curs = dbi.dict_cursor(conn)

    curs.execute('''
        SELECT username, hashed, person_id
        FROM userpass
        WHERE username = %s
    ''', [username])
    row = curs.fetchone()

    if row is None:
        flash("Invalid username or password")
        return redirect(url_for('login'))

    stored_hash = row['hashed']

    if not bc.verify_password(password, stored_hash):
        flash("Invalid username or password")
        return redirect(url_for('login'))

    # login success
    session['pid'] = row['person_id']
    session['username'] = row['username']

    flash("Logged in!")
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for('login'))

@app.route('/find_friends/', methods=['GET', 'POST'])
def find_friends():
    conn = dbi.connect()

    if 'pid' not in session:
        return redirect(url_for('login'))
    pid = session['pid']

    username = db_queries.get_username(conn, pid)
    if request.method == 'GET':
        friends = db_queries.find_friends(conn, pid)
        return render_template('find_friends.html', pid= pid, username = username['lc_username'], friends = friends)
    else:
        action = request.form.get('action')
        if action == "Go Back To Profile":
            return redirect(url_for('profile', pid=pid))
        elif action == "Connect":
            pid2 = request.form.get('connect_friend')
            friend_name = db_queries.get_username(conn, pid2)
            flash('connecting with %s' % (friend_name['lc_username']))
            db_queries.connect(conn, pid, pid2)
            friends = db_queries.find_friends(conn, pid)
            return render_template('find_friends.html', pid= pid, username = username['lc_username'], friends = friends)
            

if __name__ == '__main__':
    import sys, os
    if len(sys.argv) > 1:
        # arg, if any, is the desired port number
        port = int(sys.argv[1])
        assert(port>1024)
    else:
        port = os.getuid()
    app.debug = True
    app.run('0.0.0.0',port)    

