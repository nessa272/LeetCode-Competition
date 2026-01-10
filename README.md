# LeetParty
LeetParty is a website that tracks users’ LeetCode activity and displays progress through visual dashboards. The app manages a database of users, their groups, and submissions, allowing friends to collaborate and compete in a slightly gamified environment. By encouraging regular problem-solving, LeetParty helps users stay motivated and improve their performance, making it especially useful for tech recruiting preparation.

## Tech Stack
- **Flask** – Python web framework for routing, templates, and backend logic
- **NoSQL** – Database for storing users, parties, and stats
- **GraphQL** – API query language for fetching LeetCode data
- **Python** – Core programming language for backend logic
- **HTML / CSS / JavaScript** – Frontend structure, styling, and interactivity


## Features

- **Profile:** Manage your personal information and track your LeetCode progress. Users can view overall statistics, set personal goals, and customize their profile picture to personalize their account.

- **Main Page:** Serves as the central hub with a leaderboard, quick access to user profiles, and a summary of daily and cumulative problem-solving activity, helping users stay motivated.

- **Find Friends:** Discover and connect with other users. Search by username or real name to find friends or acquaintances, follow them to include them in Code Parties, and view their statistics.

- **Code Parties:** Collaborate with friends by joining or creating groups with shared coding goals (e.g., solve 10 problems). Groups have start and end dates, shared objectives, and leaderboards. Members can manage the group, track collective progress, and view visual dashboards showing both individual and group contributions, making it easy to compete and stay motivated together.

- **Security & Sessions:** User accounts are protected with hashed passwords, and session management ensures secure login and logout. Personal data and progress are stored safely, all actions are validated to prevent unauthorized access, and automatic database rollback maintains data integrity in case of errors or failed operations.

## SetUp 
```bash
# Clone the repository
git clone https://github.com/yourusername/LeetCode-Competition.git
cd LeetCode-Competition

# Create a virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Initialize the database
mysql -u root -p < LeetCodeCompetition.sql

# Run the app
python app.py
```

## Project Structure 
```
beta/
├── app.py                     # Main Flask application 
├── bcrypt_utils.py            # Password hashing utilities
├── db_queries.py              # Database queries for profiles, friends, and parties
├── leetcode_client.py         # Connects to LeetCode and updates user stats
├── party_charts.py            # Party dashboard visualizations
├── party_utils.py             # Party date and statistics helpers
├── LeetCodeCompetition.sql    # Database setup
├── create-filename-table.sql  # Database addition for file uploads
├── static/
│   ├── default_pfp.jpg
│   └── style.css
└── templates/
    ├── about.html
    ├── base.html
    ├── create_party.html
    ├── find_friends.html
    ├── login.html
    ├── main.html
    ├── my_parties.html
    ├── profile_edit.html
    ├── profile.html
    ├── signup.html
    └── view_group.html
```

# Authors
Nessa Tong, Sophie Lin, Ashley Yang, Jessica Dai
