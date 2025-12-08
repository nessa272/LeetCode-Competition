# Written by Jessica Dai, Sophie Lin, Nessa Tong, Ashley Yang (Olin)
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
    '''Main page of the website'''
    if "pid" in session:
        conn=dbi.connect()
        pid = session['pid']
        username = db_queries.get_profile(conn, pid)
        return render_template('main.html', page_title='Main Page', username = username['lc_username'])
    return render_template("login.html") #prompt to login
    

@app.route('/about/')
def about():
    '''our about page'''
    #flash('this is a flashed message')
    return render_template('about.html', page_title='About Us')

@app.route('/profile/<pid>', methods = ['GET', 'POST'])
def profile(pid):
    '''
    Loads a user's profile based on input pid.
    '''

    if request.method == "GET":
        conn=dbi.connect()
        # query profile info
        profile = db_queries.get_profile(conn, pid) 
        conn.close()
        # get friends list
        conn=dbi.connect()
        followers = db_queries.get_followers(conn, pid)
        follows = db_queries.get_follows(conn, pid)
        conn.close()
        # show profile
        return render_template('profile.html', profile=profile, followers=followers,follows=follows, loggedin= (str(pid) == str(session.get('pid'))))
    elif request.method =="POST":
        conn=dbi.connect()
        profile = db_queries.get_profile(conn, pid) 
        followers = db_queries.get_followers(conn, pid)
        follows = db_queries.get_follows(conn, pid)

        action = request.form.get('action')
        #print('pid' not in session)
        if action == "Unfollow":
            pid2 = request.form.get('unfollow_friend')
            friend_name = db_queries.get_profile(conn, pid2)
            print(pid2)
            flash('Unfollowing %s' % (friend_name['lc_username']))
            db_queries.unfollow(conn, pid, pid2)
            return redirect(url_for('profile', pid=pid))
            #return render_template('profile.html', profile=profile, followers=followers,follows=follows, loggedin= (str(pid) == str(session['pid'])))
               


@app.route('/refresh-profile/<pid>/<lc_username>')
def refresh_profile(pid: int, lc_username: str):
    """
    Fetch a user's recent accepted submissions from LeetCode and insert
    new (pid, lc_problem) rows into 'submission'.

    Also updates the person's:
      - current_streak
      - longest_streak
      - total_problems
      - last_submission

    All of this happens in a single transaction:
      - If anything fails, everything is rolled back.
      - If it succeeds, everything is committed together.

    Returns: number of NEW rows inserted into submission.
"""
    conn = dbi.connect()
    num_submissions = refresh_user_submissions(conn, pid, lc_username)
    print(f"{num_submissions} submissions added to database for username {lc_username}")
    conn.close()
    return redirect(url_for('profile', pid=pid))

def refresh_all():
    '''Refresh all profiles to updated info'''
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
# --------------------LOGIN/AUTHENTICATION ROUTES------------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    '''Loads signup page (create new account for new members)'''
    if request.method == 'GET':
        return render_template('signup.html')

    # else: POST request
    name = request.form.get('name')
    username = request.form.get('username')
    password = request.form.get('password1')
    lc_username = request.form.get('lc_username')

    if not username or not password or not lc_username:
        flash("All fields are required.")
        return redirect(url_for('signup'))

    conn = dbi.connect()
    #before we create person make sure their fields are valid, specifically username and lc_username
    if db_queries.username_exists(conn, username):
        flash("That username is already taken. Please log in instead.")
        return redirect(url_for('signup'))

    if db_queries.lc_username_exists(conn, lc_username):
        flash("An account already exists with that LeetCode username. Please log in.")
        return redirect(url_for('signup'))

    # Create new person in database
    try:
        pid = db_queries.create_person(conn, name, username, lc_username)
    except Exception as err:
        flash(f"Error creating person record: {err}")
        return redirect(url_for('signup'))

    hashed = bc.signup_hash(password) # Hash password

    # Put in database
    try:
        db_queries.create_userpass(conn, pid, hashed)
    except Exception as err:
        flash(f"Username already taken.")
        return redirect(url_for('signup'))

    # successfully added, sign them in and bring back to main page
    session['pid'] = pid
    session['username'] = username

    flash("Account created successfully!")
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    '''Login page to login to existing account'''
    if request.method == 'GET':
        return render_template('login.html')

    # else: POST
    username = request.form.get('username')
    password = request.form.get('password')

    conn = dbi.connect()

    user = db_queries.get_login_info(conn, username)

    if user is None:
        flash("Invalid username or password")
        return redirect(url_for('login'))

    stored_hash = user['hashed']

    if not bc.verify_password(password, stored_hash):
        flash("Invalid username or password")
        return redirect(url_for('login'))

    # login success
    session['pid'] = user['pid']
    session['username'] = user['username']

    flash("Logged in!")
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for('login'))

# --------------------PARTY ROUTES------------------
@app.route("/create_party", methods=["GET", "POST"])
def create_party():
    '''Loads page for users to create friend party'''
    if 'pid' not in session:
        flash("You must be logged in to create a party")
        return redirect(url_for("login"))

    conn = dbi.connect()

    # Fetch connections/potential people to invite
    connections = db_queries.get_party_invite_options(conn, session['pid'])

    if request.method == "POST":
        party_name = request.form.get("party_name")
        party_goal = request.form.get("party_goal")
        party_start = request.form.get("party_start")
        party_end = request.form.get("party_end")
        invitees = request.form.getlist("invitees")  # array of pid as strings

        try:
            # Create group
            cpid = db_queries.create_code_party(conn, party_name, party_goal, party_start, party_end)

            # Add party creator to the party
            db_queries.assign_user_to_party(conn, session['pid'], cpid)

            # Assign invitees -- IN FUTURE, THIS WILL BE THEY NEED TO ACCEPT FIRST, NOT AUTOMATICALLY ASSIGN
            if invitees:
                db_queries.assign_invitees_to_party(conn, cpid, invitees)

            flash("Party created successfully!")
            return redirect(url_for("view_party", cpid=cpid))
        except Exception as e:
            conn.rollback()
            flash(f"Error creating party: {e}")
    return render_template("create_party.html", connections=connections)



@app.route("/party/<int:cpid>")
def view_party(cpid):
    """
    Loads page to view existing code party
    
    :param cpid: the code party id
    """
    if 'pid' not in session:
        return redirect(url_for('login'))

    conn = dbi.connect()
    party = db_queries.get_party_info(conn, cpid)
    members = db_queries.get_party_members(conn, cpid)
    connections = db_queries.get_party_invite_options(conn, session['pid'], cpid)

    return render_template(
        "view_party.html",
        party=party,
        members=members,
        connections=connections
    )


@app.route("/party/<int:cpid>/remove_member", methods=["POST"])
def remove_member(cpid):
    '''Loads page to remove a member from a code party'''
    if 'pid' not in session:
        return redirect(url_for('login'))

    remove_pid = request.form.get("pid")
    conn = dbi.connect()
    try:
        db_queries.remove_user_from_party(conn, remove_pid, cpid)
        flash("Member removed!")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {e}")

    return redirect(url_for("view_party", cpid=cpid))

@app.route("/party/<int:cpid>/add_member", methods=["POST"])
def add_member(cpid):
    if 'pid' not in session:
        return redirect(url_for('login'))

    new_pid = request.form.get("pid")
    conn = dbi.connect()
    try:
        db_queries.assign_user_to_party(conn, new_pid, cpid)
        flash("Member added!")
    except Exception as e:
        flash(f"Error adding member: {e}")

    return redirect(url_for("view_party", cpid=cpid))

@app.route("/my_parties")
def my_parties():
    """Shows a list of all parties the user belongs to."""
    if 'pid' not in session:
        flash("You must be logged in to view your parties.")
        return redirect(url_for('login'))

    conn = dbi.connect()
    all_parties = db_queries.get_parties_for_user(conn, session['pid'])

    current = [p for p in all_parties if p['status'] == 'in_progress']
    upcoming = [p for p in all_parties if p['status'] == 'upcoming']
    completed = [p for p in all_parties if p['status'] == 'completed']

    #SORT differently depending on section
    # Current parties: earliest competition end deadline
    current.sort(key=lambda p: p['party_end'])
    # Upcoming parties: soonest start date
    upcoming.sort(key=lambda p: p['party_start'])
    # Completed parties: most recently ended
    completed.sort(key=lambda p: p['party_end'], reverse=True)


    return render_template(
        "my_parties.html",
        current_parties=current,
        upcoming_parties=upcoming,
        completed_parties=completed
    )


@app.route('/find_friends/', methods=['GET', 'POST'])
def find_friends():
    '''Loads page to find people (who are the user is not currently connected to) to friend'''
    conn = dbi.connect()

    if 'pid' not in session:
        return redirect(url_for('login'))
    pid = session['pid']
    
    username = db_queries.get_profile(conn, pid)
    if request.method == 'GET':
        friends = db_queries.find_friends(conn, pid)
        return render_template('find_friends.html', pid= pid, username = username['username'], friends = friends)
    else:
        action = request.form.get('action')
        if action == "Go Back To Profile":
            return redirect(url_for('profile', pid=pid))
        elif action == "Follow":
            pid2 = request.form.get('follow_friend')
            friend_name = db_queries.get_profile(conn, pid2)

            flash('Following %s' % (friend_name['lc_username']))
            db_queries.follow(conn, pid, pid2)
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

