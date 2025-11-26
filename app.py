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
    flash('this is a flashed message')
    return render_template('about.html', page_title='About Us')

@app.route('/profile/<pid>')
def get_user_profile(pid):
    '''loads a user's profile'''
    conn=dbi.connect()
    profile = db_search.get_profile(conn, pid)
    print(profile)
    return render_template('profile.html', profile=profile)

# --------------------LOGIN/AUTHENTICATION ROUTES------------------
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
        person_id = db_queries.create_person(conn, username, lc_username)
    except Exception as err:
        flash(f"Error creating person record: {err}")
        return redirect(url_for('signup'))

    hashed = bc.signup_hash(password) # Hash password

    # Put in database
    try:
        db_queries.create_userpass(conn, username, hashed, person_id)
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

    row = db_queries.get_userpass_by_username(conn, username)

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

@app.route('/profile')
def profile():
    if 'pid' not in session:
        return redirect(url_for('login'))

    conn = dbi.connect()
    person = db_queries.get_person_by_pid(conn, session['pid'])

    return render_template("profile.html", person=person)

def refresh_profile(pid: int, username: str):
    conn = dbi.connect()
    refresh_user_submissions(conn, pid, username)


# --------------------GROUP ROUTES------------------
@app.route("/create_group", methods=["GET", "POST"])
def create_group():
    if 'pid' not in session:
        flash("You must be logged in to create a group")
        return redirect(url_for("login"))

    conn = dbi.connect()

    # Fetch connections
    connections = db_queries.get_connections_with_group_status(conn, session['pid'])

    if request.method == "POST":
        group_goal = request.form.get("group_goal")
        comp_start = request.form.get("comp_start")
        comp_end = request.form.get("comp_end")
        invitees = request.form.getlist("invitees")  # array of pid as strings

        try:
            # Create group
            gid = db_queries.create_group(conn, group_goal, comp_start, comp_end)

            # Assign current user
            db_queries.assign_user_to_group(conn, session['pid'], gid)

            # Assign invitees -- IN FUTURE, THIS WILL BE THEY NEED TO ACCEPT FIRST, NOT AUTOMATICALLY ASSIGN
            if invitees:
                invitee_ids = [int(pid) for pid in invitees]
                db_queries.assign_multiple_users_to_group(conn, gid, invitee_ids)

            flash("Group created successfully!")
            return redirect(url_for("view_group", gid=gid))
        
        except Exception as e:
            conn.rollback()
            flash(f"Error creating group: {e}")
    return render_template("create_group.html", connections=connections)


@app.route("/group/<int:gid>")
def view_group(gid):
    if 'pid' not in session:
        return redirect(url_for('login'))

    conn = dbi.connect()
    group = db_queries.get_group_info(conn, gid)
    members = db_queries.get_group_members(conn, gid)
    
    # Connections for invite form (friends not in a group)
    connections = db_queries.get_connections_with_group_status(conn, session['pid'])

    return render_template(
        "view_group.html", 
        group=group,
        members=members,
        connections=connections
    )



@app.route("/group/<int:gid>/remove_member", methods=["POST"])
def remove_member(gid):
    if 'pid' not in session:
        return redirect(url_for('login'))

    remove_pid = request.form.get("pid")
    conn = dbi.connect()
    curs = dbi.dict_cursor(conn)

    try:
        # Remove member from group (set gid to NULL)
        db_queries.remove_user_from_group(conn, remove_pid, gid)
        flash("Member removed!")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {e}")

    return redirect(url_for("view_group", gid=gid))

@app.route("/group/<int:gid>/add_member", methods=["POST"])
def add_member(gid):
    if 'pid' not in session:
        return redirect(url_for("login"))

    new_pid = request.form.get("pid")
    conn = dbi.connect()

    try:
        db_queries.assign_user_to_group(conn, new_pid, gid)
        flash("Member added!")
    except Exception as e:
        flash(f"Error adding member: {e}")

    return redirect(url_for("view_group", gid=gid))

@app.route("/my_group")
def my_group():
    if 'pid' not in session:
        flash("You must be logged in to view your group.")
        return redirect(url_for('login'))

    conn = dbi.connect()
    person = db_queries.get_person_by_pid(conn, session['pid'])

    if person['gid']:
        # User in group
        group = db_queries.get_group_info(conn, person['gid'])
        members = db_queries.get_group_members(conn, person['gid'])
        # Connections for invite form (friends not in a group)
        connections = db_queries.get_connections_with_group_status(conn, session['pid'])
    else:
        # User not in  group
        group = None
        members = None
        connections = None

    return render_template(
        "view_group.html",
        group=group,
        members=members,
        connections=connections
    )

@app.route('/find_friends/<pid>', methods=['GET', 'POST'])
def find_friends(pid):
    conn = dbi.connect()
    username = db_queries.get_username(conn, pid)
    if request.method == 'GET':
        friends = db_queries.find_friends(conn, pid)
        return render_template('find_friends.html', pid= pid, username = username['lc_username'], friends = friends)
    else:
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

