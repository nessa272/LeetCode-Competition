from flask import (Flask, render_template, make_response, url_for, request,
                   redirect, flash, session, send_from_directory, jsonify)
from werkzeug.utils import secure_filename
app = Flask(__name__)

import secrets
import cs304dbi as dbi
import db_search
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

@app.route('/profile/<username>')
def get_user_profile(username):
    '''loads a user's profile'''
    conn=dbi.connect()
    profile = db_search.get_profile(conn, username)
    return render_template('profile.html', profile)


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
        curs.execute('''
            INSERT INTO person (username, lc_username, current_streak, longest_streak,
                                total_problems, num_coins)
            VALUES (%s, %s, NULL, NULL, NULL, NULL)
        ''', [username, lc_username])
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

@app.route('/profile')
def profile():
    if 'pid' not in session:
        return redirect(url_for('login'))

    conn = dbi.connect()
    curs = dbi.dict_cursor(conn)

    curs.execute("SELECT * FROM person WHERE pid=%s", [session['pid']])
    person = curs.fetchone()

    curs.close()
    conn.close()

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
    curs = dbi.dict_cursor(conn)

    # Fetch connections
    curs.execute('''
        SELECT p.*, 
               CASE WHEN p.gid IS NULL THEN 0 ELSE 1 END AS in_group
        FROM person p
        JOIN connection c ON (c.p1=%s AND c.p2=p.pid) OR (c.p2=%s AND c.p1=p.pid)
    ''', [session['pid'], session['pid']])
    connections = curs.fetchall()

    if request.method == "POST":
        group_goal = request.form.get("group_goal")
        comp_start = request.form.get("comp_start")
        comp_end = request.form.get("comp_end")
        invitees = request.form.getlist("invitees")  # array of pid as strings

        try:
            # Create group
            curs.execute('''
                INSERT INTO groups (group_goal, comp_start, comp_end)
                VALUES (%s, %s, %s)
            ''', [group_goal, comp_start, comp_end])
            gid = curs.lastrowid

            # Assign current user
            curs.execute("UPDATE person SET gid=%s WHERE pid=%s", [gid, session['pid']])

            # Assign invitees -- IN FUTURE, THIS WILL BE THEY NEED TO ACCEPT FIRST, NOT AUTOMATICALLY ASSIGN
            if invitees:
                # Convert pid strings to integers
                invitee_ids = [int(pid) for pid in invitees]
                curs.execute(f'''
                    UPDATE person
                    SET gid=%s
                    WHERE pid IN ({','.join(['%s']*len(invitee_ids))})
                ''', [gid]+invitee_ids)

            conn.commit()
            flash("Group created successfully!")
            return redirect(url_for("view_group", gid=gid))
        except Exception as e:
            conn.rollback()
            flash(f"Error creating group: {e}")
        finally:
            curs.close()
            conn.close()

    curs.close()
    conn.close()
    return render_template("create_group.html", connections=connections)


@app.route("/group/<int:gid>")
def view_group(gid):
    if 'pid' not in session:
        return redirect(url_for('login'))

    conn = dbi.connect()
    curs = dbi.dict_cursor(conn)

    # Get group info
    curs.execute("SELECT * FROM groups WHERE gid=%s", [gid])
    group = curs.fetchone()

    # Get current members
    curs.execute("SELECT * FROM person WHERE gid=%s", [gid])
    members = curs.fetchall()

    # Get connections that are not in a group
    curs.execute('''
        SELECT p.*, CASE WHEN p.gid IS NULL THEN 0 ELSE 1 END AS in_group
        FROM person p
        JOIN connection c ON (c.p1=%s AND c.p2=p.pid) OR (c.p2=%s AND c.p1=p.pid)
        WHERE p.pid != %s
    ''', [session['pid'], session['pid'], session['pid']])
    connections = curs.fetchall()

    curs.close()
    conn.close()

    return render_template("view_group.html",
                           group=group,
                           members=members,
                           connections=connections)


@app.route("/group/<int:gid>/remove_member", methods=["POST"])
def remove_member(gid):
    if 'pid' not in session:
        return redirect(url_for('login'))

    remove_pid = request.form.get("pid")
    conn = dbi.connect()
    curs = dbi.dict_cursor(conn)

    try:
        # Remove member from group (set gid to NULL)
        curs.execute("UPDATE person SET gid=NULL WHERE pid=%s AND gid=%s", [remove_pid, gid])
        conn.commit()
        flash("Member removed!")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {e}")
    finally:
        curs.close()
        conn.close()

    return redirect(url_for("view_group", gid=gid))



# --------------------GROUP ROUTES------------------
@app.route("/create_group", methods=["GET", "POST"])
def create_group():
    if 'pid' not in session:
        flash("You must be logged in to create a group")
        return redirect(url_for("login"))

    conn = dbi.connect()
    curs = dbi.dict_cursor(conn)

    # Fetch connections
    curs.execute('''
        SELECT p.*, 
               CASE WHEN p.gid IS NULL THEN 0 ELSE 1 END AS in_group
        FROM person p
        JOIN connection c ON (c.p1=%s AND c.p2=p.pid) OR (c.p2=%s AND c.p1=p.pid)
    ''', [session['pid'], session['pid']])
    connections = curs.fetchall()

    if request.method == "POST":
        group_goal = request.form.get("group_goal")
        comp_start = request.form.get("comp_start")
        comp_end = request.form.get("comp_end")
        invitees = request.form.getlist("invitees")  # array of pid as strings

        try:
            # Create group
            curs.execute('''
                INSERT INTO groups (group_goal, comp_start, comp_end)
                VALUES (%s, %s, %s)
            ''', [group_goal, comp_start, comp_end])
            gid = curs.lastrowid

            # Assign current user
            curs.execute("UPDATE person SET gid=%s WHERE pid=%s", [gid, session['pid']])

            # Assign invitees -- IN FUTURE, THIS WILL BE THEY NEED TO ACCEPT FIRST, NOT AUTOMATICALLY ASSIGN
            if invitees:
                # Convert pid strings to integers
                invitee_ids = [int(pid) for pid in invitees]
                curs.execute(f'''
                    UPDATE person
                    SET gid=%s
                    WHERE pid IN ({','.join(['%s']*len(invitee_ids))})
                ''', [gid]+invitee_ids)

            conn.commit()
            flash("Group created successfully!")
            return redirect(url_for("view_group", gid=gid))
        except Exception as e:
            conn.rollback()
            flash(f"Error creating group: {e}")
        finally:
            curs.close()
            conn.close()

    curs.close()
    conn.close()
    return render_template("create_group.html", connections=connections)


@app.route("/group/<int:gid>")
def view_group(gid):
    if 'pid' not in session:
        return redirect(url_for('login'))

    conn = dbi.connect()
    curs = dbi.dict_cursor(conn)

    # Get group info
    curs.execute("SELECT * FROM groups WHERE gid=%s", [gid])
    group = curs.fetchone()

    # Get current members
    curs.execute("SELECT * FROM person WHERE gid=%s", [gid])
    members = curs.fetchall()

    # Get connections that are not in a group
    curs.execute('''
        SELECT p.*, CASE WHEN p.gid IS NULL THEN 0 ELSE 1 END AS in_group
        FROM person p
        JOIN connection c ON (c.p1=%s AND c.p2=p.pid) OR (c.p2=%s AND c.p1=p.pid)
        WHERE p.pid != %s
    ''', [session['pid'], session['pid'], session['pid']])
    connections = curs.fetchall()

    curs.close()
    conn.close()

    return render_template("view_group.html",
                           group=group,
                           members=members,
                           connections=connections)


@app.route("/group/<int:gid>/remove_member", methods=["POST"])
def remove_member(gid):
    if 'pid' not in session:
        return redirect(url_for('login'))

    remove_pid = request.form.get("pid")
    conn = dbi.connect()
    curs = dbi.dict_cursor(conn)

    try:
        # Remove member from group (set gid to NULL)
        curs.execute("UPDATE person SET gid=NULL WHERE pid=%s AND gid=%s", [remove_pid, gid])
        conn.commit()
        flash("Member removed!")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {e}")
    finally:
        curs.close()
        conn.close()

    return redirect(url_for("view_group", gid=gid))


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

