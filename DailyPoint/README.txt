DailyPoint - daily to-do list with GitHub-style green boxes (Flask + SQLite)
============================================================================
Requirements: Python 3.8+

Setup & run:
    pip install -r requirements.txt
    python app.py
Open: http://localhost:5000

Optional: set SECRET_KEY to any long random text (used to sign login cookies).
If you used an older version, the database is upgraded automatically (gender column).

FILES
app.py            Flask app: routes and SQLite database
templates/        login, register, app (main page), profile pages
static/           style.css, common.js and the icons
dailypoint.db     created automatically (users, lists, completed days)
