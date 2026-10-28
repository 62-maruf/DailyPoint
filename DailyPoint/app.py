# DailyPoint (Flask + SQLite)   run:  python app.py   open: http://localhost:5000
import os, sqlite3, calendar
from datetime import date
from flask import Flask, g, jsonify, redirect, render_template, request, session
from werkzeug.security import generate_password_hash, check_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "dailypoint.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")

# ---------------- database ----------------
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    c = g.pop("db", None)
    if c: c.close()

def init_db():
    c = sqlite3.connect(DB_PATH)
    c.executescript("""
    create table if not exists users(id integer primary key, username text unique, email text unique,
      password text, gender text default 'male');
    create table if not exists lists(id integer primary key, user_id integer, name text, pinned integer default 0);
    create table if not exists checks(list_id integer, day text, primary key(list_id, day));
    """)
    if "gender" not in [r[1] for r in c.execute("pragma table_info(users)")]:   # upgrade older databases
        c.execute("alter table users add column gender text default 'male'")
    c.commit(); c.close()

# ---------------- pages ----------------
def current_user():
    uid = session.get("uid")
    return db().execute("select * from users where id=?", (uid,)).fetchone() if uid else None

@app.route("/")
def home():
    return redirect("/app" if current_user() else "/login")

@app.route("/login")
def login_page():
    return redirect("/app") if current_user() else render_template("login.html")

@app.route("/register")
def register_page():
    return render_template("register.html")

@app.route("/app")
def main_page():
    return render_template("app.html") if current_user() else redirect("/login")

@app.route("/profile")
def profile_page():
    return render_template("profile.html") if current_user() else redirect("/login")

# ---------------- auth api ----------------
@app.post("/api/register")
def register():
    d = request.get_json()
    username, email = d.get("username", "").strip(), d.get("email", "").strip().lower()
    pw, cf = d.get("password", ""), d.get("confirm", "")
    gender = d.get("gender", "male")
    if gender not in ("male", "female", "others"): gender = "male"
    if not (username and email and pw): return jsonify(error="Please fill in all fields.")
    if "@" not in email or "." not in email: return jsonify(error="Invalid email.")
    if len(pw) < 6: return jsonify(error="Password must be at least 6 characters.")
    if pw != cf: return jsonify(error="Passwords do not match.")
    if db().execute("select 1 from users where email=? or lower(username)=?", (email, username.lower())).fetchone():
        return jsonify(error="Username or email already used.")
    cur = db().execute("insert into users(username,email,password,gender) values(?,?,?,?)",
                       (username, email, generate_password_hash(pw), gender))
    db().commit()
    session["uid"] = cur.lastrowid   # log in right after creating the account
    return jsonify(ok=True)

@app.post("/api/login")
def login():
    d = request.get_json()
    who = d.get("who", "").strip().lower()
    u = db().execute("select * from users where email=? or lower(username)=?", (who, who)).fetchone()
    if not u or not check_password_hash(u["password"], d.get("password", "")):
        return jsonify(error="Wrong username/email or password.")
    session["uid"] = u["id"]
    return jsonify(ok=True)

@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)

# ---------------- list api (login required) ----------------
def uid_or_401():
    u = current_user()
    return u["id"] if u else None

def owns(list_id, uid):
    return db().execute("select 1 from lists where id=? and user_id=?", (list_id, uid)).fetchone()

@app.get("/api/data")
def data():
    uid = uid_or_401()
    if not uid: return jsonify(error="login required"), 401
    today = date.today()
    y = request.args.get("year", today.year, type=int)
    m = request.args.get("month", today.month, type=int)
    lists = db().execute("select * from lists where user_id=? order by pinned desc, id", (uid,)).fetchall()
    out = []
    for l in lists:
        rows = db().execute("select day from checks where list_id=? and day like ?",
                            (l["id"], f"{y:04d}-{m:02d}-%")).fetchall()
        out.append({"id": l["id"], "name": l["name"], "pinned": l["pinned"],
                    "days": [int(r["day"][8:]) for r in rows]})
    done_today = [r["list_id"] for r in db().execute(
        "select list_id from checks where day=? and list_id in (select id from lists where user_id=?)",
        (today.isoformat(), uid))]
    gender = db().execute("select gender from users where id=?", (uid,)).fetchone()["gender"]
    return jsonify(gender=gender, year=y, month=m, daysInMonth=calendar.monthrange(y, m)[1],
                   today=today.isoformat(), lists=out, todayDone=done_today)

@app.post("/api/list/<action>")
def list_action(action):
    uid = uid_or_401()
    if not uid: return jsonify(error="login required"), 401
    d = request.get_json()
    name, lid = d.get("name", "").strip(), d.get("id")
    if action == "add" and name:
        db().execute("insert into lists(user_id,name) values(?,?)", (uid, name))
    elif action == "rename" and name and owns(lid, uid):
        db().execute("update lists set name=? where id=?", (name, lid))
    elif action == "pin" and owns(lid, uid):
        db().execute("update lists set pinned=1-pinned where id=?", (lid,))
    elif action == "delete" and owns(lid, uid):
        db().execute("delete from checks where list_id=?", (lid,))
        db().execute("delete from lists where id=?", (lid,))
    else:
        return jsonify(error="bad request"), 400
    db().commit()
    return jsonify(ok=True)

@app.post("/api/done")
def done():
    uid = uid_or_401()
    if not uid: return jsonify(error="login required"), 401
    today, ids = date.today().isoformat(), set(request.get_json().get("ids", []))
    for r in db().execute("select id from lists where user_id=?", (uid,)).fetchall():
        if r["id"] in ids:
            db().execute("insert or ignore into checks values(?,?)", (r["id"], today))
        else:
            db().execute("delete from checks where list_id=? and day=?", (r["id"], today))
    db().commit()
    return jsonify(ok=True)

@app.get("/api/profile")
def profile():
    u = current_user()
    if not u: return jsonify(error="login required"), 401
    rows = db().execute(
        "select l.name, substr(c.day,1,7) ym, count(*) cnt from checks c join lists l on l.id=c.list_id "
        "where l.user_id=? group by l.id, ym order by ym desc, l.id", (u["id"],)).fetchall()
    history = []
    for r in rows:
        y, m = int(r["ym"][:4]), int(r["ym"][5:])
        n = calendar.monthrange(y, m)[1]
        history.append({"list": r["name"], "month": r["ym"], "done": r["cnt"], "days": n, "full": r["cnt"] == n})
    return jsonify(username=u["username"], email=u["email"], gender=u["gender"], history=history)

init_db()
if __name__ == "__main__":
    app.run(debug=True, port=5000)
