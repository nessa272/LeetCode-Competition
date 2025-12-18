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
from party_charts import build_chart_data
from party_utils import compute_party_dates, nth
import datetime

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
        leaderboard = db_queries.get_leaderboard(conn, limit=10)
        problems_today = db_queries.get_problems_solved_today(conn, pid)
        conn.close()

        return render_template(
            'main.html',
            page_title='Main Page',
            username=username['username'],
            leaderboard=leaderboard,
            problems_today=problems_today
        )
    
    return render_template("login.html", page_title='Login Page')
    

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
        #check if this is your profile or someone elses
        if "pid" in session:
            loggedin = (str(pid) == str(session.get('pid')))
        else:
            loggedin = None
                                   
        # query profile info
        conn=dbi.connect()
        profile = db_queries.get_profile(conn, pid) 
        # get friends list
        followers = db_queries.get_followers(conn, pid)
        follows = db_queries.get_follows(conn, pid)

        #check if the session_pid is following this profile user
        isfollowing = db_queries.is_following(conn, session.get('pid'), pid)

        conn.close()

        
        # show profile
        return render_template('profile.html', page_title='Profile Page', 
                               profile=profile, followers=followers, follows=follows, 
                               loggedin= loggedin, 
                               session_pid = session.get('pid'),
                               is_following = isfollowing)
    # else POST
    
    conn=dbi.connect()
    profile = db_queries.get_profile(conn, pid) 
    followers = db_queries.get_followers(conn, pid)
    follows = db_queries.get_follows(conn, pid)
    action = request.form.get('action')
    #print('pid' not in session)

    #unfollows someone from your friends list (on your page)
    # TO DO: Will add edit_profile and refresh_stats as other actions
    if action == "Unfollow":
        pid2 = request.form.get('unfollow_friend')
        friend_name = db_queries.get_profile(conn, pid2)
        print(pid2)
        flash('Unfollowing %s' % (friend_name['username']))
        try:
            db_queries.unfollow(conn, pid, pid2)
            conn.commit()
            return redirect(url_for('profile', pid=pid))
        except Exception:
            conn.rollback()
        finally:
            conn.close()
        #return render_template('profile.html', profile=profile, followers=followers,follows=follows, loggedin= (str(pid) == str(session['pid'])))
    
    #unfollow looking from a diff page
    elif action == "Unfollow_out":
        #double check session
        if 'pid' not in session:
            flash("You must be logged in to unfollow")
            return redirect(url_for("login"))
        
        #flash message
        friend_name = db_queries.get_profile(conn, pid)
        flash('Unfollowing %s' % (friend_name['username']))

        try:
            db_queries.unfollow(conn, session.get('pid'), pid)
            conn.commit()
            return redirect(url_for('profile', pid=pid))
        except Exception:
            conn.rollback()
        finally:
            conn.close()
    
    elif action == "Follow_out":
        if 'pid' not in session:
            flash("You must be logged in to follow")
            return redirect(url_for("login"))
        
        #flash message
        friend_name = db_queries.get_profile(conn, pid)
        flash('Following %s' % (friend_name['username']))

        try:
            db_queries.follow(conn, session.get('pid'), pid)
            conn.commit()
            return redirect(url_for('profile', pid=pid))
        except Exception:
            conn.rollback()
        finally:
            conn.close()
    
    conn.close()
               
# TO DO: TEMPORARY SOLUTION
# Will be incorporated into POST action in profile (not separate url)
@app.route('/profile/edit/<pid>', methods = ['GET', 'POST'])
def edit_profile(pid):
    '''
    Loads a user's profile based on input pid.
    '''
    if request.method == "GET":
        if 'pid' not in session or str(pid) != str(session.get('pid')):
            return redirect(url_for('profile', pid = pid))

        # query profile info
        conn=dbi.connect()
        profile = db_queries.get_profile(conn, pid) 
        # get friends list
        followers = db_queries.get_followers(conn, pid)
        follows = db_queries.get_follows(conn, pid)
        conn.close()

        # show profile
        return render_template('profile_edit.html', 
                               page_title='Profile Edit Page', 
                               profile=profile, 
                               followers=followers,
                               follows=follows, 
                               loggedin= (str(pid) == str(session['pid'])))
    elif request.method =="POST":
        action = request.form.get('action')
        #print(action)
        if action == "update":
            #print("update")
            #get form info
            name = request.form.get('name')
            username = request.form.get('username')
            conn = dbi.connect()
            try:
                db_queries.edit_profile(conn, pid, name, username)
                conn.commit()
            except Exception:
                conn.rollback()
            finally:
                conn.close()
            return redirect(url_for('profile', pid=pid))
        
        #cancel button
        else:
            return redirect(url_for('profile', pid=pid))

@app.route('/refresh-stats', methods=['POST'])
def refresh_my_stats():
    """Refreshes ONLY the signed in user stats. This allows for a post button
    to work for any page this button needs to be implemented on. """
    # Get current user from session
    if 'pid' not in session:
        return redirect(url_for('login'))

    conn = dbi.connect()
    try:
        #get lc username for this SIGNED IN person
        profile = db_queries.get_profile(conn, session['pid'])
        lc_username = profile['lc_username']
        #refresh their submissions
        num_submissions = refresh_user_submissions(conn, session['pid'], lc_username)
        conn.commit()
        print(f"{num_submissions} submissions added to database for username {lc_username}")
    except Exception as e:
        conn.rollback()
    finally:
        conn.close()

    # Redirect back to wherever the request came from, passed in by the html
    # TEMPORARY solution whilst not pursuing ajax for the sake of time.
    next_url = request.args.get("next")
    return redirect(next_url or url_for('index'))

@app.route('/refresh-profile/<pid>/<lc_username>')
def refresh_profile(pid: int, lc_username: str):
    """
    NOTE: this route alolows you to refresh anyone's profile with its unique link, 
    currently deprecated use for preferred refresh_my_stats. 
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
    try:
        num_submissions = refresh_user_submissions(conn, pid, lc_username)
        print(f"{num_submissions} submissions added to database for username {lc_username}")
        conn.commit()
        return redirect(url_for('profile', pid=pid))
    except Exception:
        conn.rollback()
    finally:
        conn.close()

# --------------------LOGIN/AUTHENTICATION ROUTES------------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    '''Loads signup page (create new account for new members)'''
    if request.method == 'GET':
        return render_template('signup.html', page_title='Signup Page')

    # else: POST request
    name = request.form.get('name')
    username = request.form.get('username')
    password = request.form.get('password1')
    lc_username = request.form.get('lc_username')

    if not username or not password or not lc_username:
        flash("All fields are required.")
        return render_template('signup.html', page_title='Signup Page')

    conn = dbi.connect()
    try:
        #before we create person make sure their fields are valid, specifically username and lc_username
        if db_queries.username_exists(conn, username):
            flash("That username is already taken. Please log in instead.")
            return render_template('signup.html', page_title='Signup Page')
        if db_queries.lc_username_exists(conn, lc_username):
            flash("An account already exists with that LeetCode username. Please log in.")
            return render_template('signup.html', page_title='Signup Page')

        # create new person in database
        try:
            pid = db_queries.create_person(conn, name, username, lc_username)
        except Exception as err:
            flash(f"Error creating person record: {err}")
            conn.rollback()
            return render_template('signup.html', page_title='Signup Page')

        hashed = bc.signup_hash(password) # Hash password
        # Put in database
        try:
            db_queries.create_userpass(conn, pid, hashed)
            conn.commit()
        except Exception as err:
            conn.rollback()
            flash(f"Username already taken.")
            return render_template('signup.html', page_title='Signup Page')

        # successfully added, sign them in and bring back to main page
        session['pid'] = pid
        session['username'] = username
    finally:
        conn.close()

    flash("Account created successfully!")
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    '''Login page to login to existing account'''
    if request.method == 'GET':
        return render_template('login.html', page_title='Login Page')

    # else: POST
    username = request.form.get('username')
    password = request.form.get('password')
    conn = dbi.connect()
    try:
        user = db_queries.get_login_info(conn, username)

        if user is None:
            flash("Invalid username or password")
            return render_template('login.html', page_title='Login Page')

        stored_hash = user['hashed']

        if not bc.verify_password(password, stored_hash):
            flash("Invalid username or password")
            return render_template('login.html', page_title='Login Page')
    finally:
        conn.close()

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
    try:
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

                conn.commit()
                flash("Party created successfully!")
                return redirect(url_for("view_party", cpid=cpid))
            except Exception as e:
                conn.rollback()
                flash(f"Error creating party: {e}")
    finally:
        conn.close()
    
    return render_template("create_party.html", 
                           page_title='Party Creation Page', 
                           connections=connections)

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
    conn.close()

    return render_template(
        "view_party.html",
        page_title='View Party Page',
        party=party,
        members=members,
        connections=connections
    )

@app.route("/api/party/<int:cpid>/charts")
def party_charts(cpid):
    if 'pid' not in session:
        return jsonify({"error": "not logged in"}), 401

    conn = dbi.connect()
    submissions = db_queries.get_party_submissions(conn, cpid)
    party_info = db_queries.get_party_info(conn, cpid)
    conn.close()

    data = build_chart_data(submissions, party_info['party_goal'])

    if party_info and "progress" in data:
        data["progress"]["goal"] = int(party_info["party_goal"])  # or party.party_goal depending on row type

    return jsonify(data)

# TO DO: Change to POST action in view_party
@app.route("/party/<int:cpid>/remove_member", methods=["POST"])
def remove_member(cpid):
    '''Loads page to remove a member from a code party'''
    if 'pid' not in session:
        return redirect(url_for('login'))

    remove_pid = request.form.get("pid")
    conn = dbi.connect()
    try:
        db_queries.remove_user_from_party(conn, remove_pid, cpid)
        conn.commit()
        flash("Member removed!")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {e}")
    finally:
        conn.close()

    return redirect(url_for("view_party", cpid=cpid))

@app.route("/party/<int:cpid>/add_member", methods=["POST"])
def add_member(cpid):
    if 'pid' not in session:
        return redirect(url_for('login'))

    new_pid = request.form.get("pid")
    conn = dbi.connect()
    try:
        db_queries.assign_user_to_party(conn, new_pid, cpid)
        conn.commit()
        flash("Member added!")
    except Exception as e:
        conn.rollback()
        flash(f"Error adding member: {e}")
    finally:
        conn.close()

    return redirect(url_for("view_party", cpid=cpid))

@app.route("/my_parties")
def my_parties():
    """Shows a list of all parties the user belongs to."""
    if 'pid' not in session:
        flash("You must be logged in to view your parties.")
        return redirect(url_for('login'))

    conn = dbi.connect()
    all_parties = db_queries.get_parties_for_user(conn, session['pid'])
    conn.close()

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

    now = datetime.datetime.now()

    # get num days relative to current date for each party
    current = compute_party_dates(current)
    upcoming = compute_party_dates(upcoming)
    completed = compute_party_dates(completed)

    #add ucer's rank for each party
    for p in all_parties:
        print(p['name'], p.get('rank'), p.get('word_rank'))
        if p.get('rank') is not None:
            p['word_rank'] = nth(p['rank'])
        else:
            p['word_rank'] = None


    return render_template(
        "my_parties.html",
        page_title='My Parties Page',
        current_parties=current,
        upcoming_parties=upcoming,
        completed_parties=completed
    )

@app.route('/party/<int:cpid>/refresh')
def refresh_party(cpid):
    """Refreshes the party stats, specifically refetching leetcode 
    information for each party member"""
    conn = dbi.connect()

    members = db_queries.get_party_members(conn, cpid)
    failed_refreshes = []

    for m in members:
        try:
            refresh_user_submissions(conn, m['pid'], m['lc_username'])
            conn.commit()
        except Exception:
            failed_refreshes.append(m['username'])
            conn.rollback()
    
    if failed_refreshes:
        flash("Failed to refresh: " + ", ".join(failed_refreshes))
    # Only refresh party if EVERYONE'S stats updated
    else:
        try:
            db_queries.update_party_last_refreshed(conn, cpid)
            conn.commit()
            flash("Party refreshed")
        except Exception:
            conn.rollback()
            flash(f"Error refreshing party")

    conn.close()
    return redirect(url_for('view_party', cpid=cpid))

#------------ Find Friends ----------------
@app.route('/find_friends/', methods=['GET', 'POST'])
def find_friends():
    """Loads page to find people (who are the user is not currently connected to) to friend"""

    if 'pid' not in session:
        return redirect(url_for('login'))
    pid = session['pid']
    conn = dbi.connect()
    
    try:
        username = db_queries.get_profile(conn, pid)
        if request.method == 'GET':
            friends = db_queries.find_friends(conn, pid)
            return render_template('find_friends.html', 
                                page_title='Find Friends Page', 
                                pid= pid, 
                                username = username['username'], 
                                friends = friends, 
                                search = False)
        else:
            action = request.form.get('action')

            #back to profile
            if action == "Go Back To Profile":
                return redirect(url_for('profile', pid=pid))
            
            #user decides to follow someone
            elif action == "Follow":
                pid2 = request.form.get('follow_friend')

                friend_name = db_queries.get_profile(conn, pid2)

                flash('Following %s' % (friend_name['username']))

                #make connection 
                try:
                    db_queries.follow(conn, pid, pid2)
                    conn.commit()
                except Exception:
                    conn.rollback()

                #refresh friends list
                friends = db_queries.find_friends(conn, pid)
                return render_template('find_friends.html', 
                                    page_title='Find Friends Page',
                                    pid= pid, 
                                    username = username['lc_username'], 
                                    friends = friends, 
                                    search = False)

            elif action == 'Search':
                search_term= request.form.get('search_query')
                searched_friends = db_queries.search_friends(conn, pid, search_term)
                return render_template('find_friends.html', 
                                    page_title='Find Friends Page',
                                    pid= pid, 
                                    username = username['lc_username'], 
                                    friends = searched_friends, 
                                    search_term = search_term, 
                                    search = True)
    finally:
        conn.close()

               

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

