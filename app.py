from flask import Flask, render_template, request, redirect, session, g
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change_this_secret")  # Use env variable

DATABASE = os.path.join(os.path.dirname(__file__), "ibems.db")


# --- Database Helpers ---
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            appliance TEXT,
            start_date TEXT,
            end_date TEXT,
            daily_hours TEXT,
            power_w REAL,
            rate REAL,
            total_kwh REAL,
            total_bill REAL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    db.commit()


# --- Routes ---
@app.route("/")
def home():
    if not session.get("user"):
        return redirect("/login")
    return redirect("/calculator")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username=? AND password=?", (u, p)).fetchone()
        if user:
            session["user"] = u
            session["user_id"] = user["id"]
            return redirect("/")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]
        try:
            db = get_db()
            db.execute("INSERT INTO users (username, password) VALUES (?,?)", (u, p))
            db.commit()
            return redirect("/login")
        except sqlite3.IntegrityError:
            return "Username already exists"
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/calculator", methods=["GET", "POST"])
def calculator():
    if not session.get("user"):
        return redirect("/login")

    result = None
    db = get_db()

    if request.method == "POST":
        appliance = request.form["appliance"]
        power = float(request.form["power"])
        rate = float(request.form["rate"])
        start_date = request.form["start_date"]
        end_date = request.form["end_date"]
        default_hours = float(request.form["hours"])

        d1 = datetime.strptime(start_date, "%Y-%m-%d")
        d2 = datetime.strptime(end_date, "%Y-%m-%d")
        days = (d2 - d1).days + 1

        daily_usage = [default_hours for _ in range(days)]

        changes_input = request.form["changes"]
        if changes_input.strip():
            for item in changes_input.split(","):
                try:
                    day, hrs = item.split("=")
                    day = int(day)
                    hrs = float(hrs)
                    if 1 <= day <= days:
                        daily_usage[day - 1] = hrs
                except:
                    pass

        total_hours = sum(daily_usage)
        total_kwh = (power * total_hours) / 1000
        total_bill = total_kwh * rate

        db.execute("""
            INSERT INTO usage (user_id, appliance, start_date, end_date, daily_hours, power_w, rate, total_kwh, total_bill)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (session["user_id"], appliance, start_date, end_date,
              str(daily_usage), power, rate, total_kwh, total_bill))
        db.commit()

        result = {
            "appliance": appliance,
            "days": days,
            "total_hours": total_hours,
            "kwh": round(total_kwh, 2),
            "bill": round(total_bill, 2)
        }

    history = db.execute("SELECT * FROM usage WHERE user_id=?", (session["user_id"],)).fetchall()

    return render_template("calculator.html", result=result, history=history)


@app.route("/history/<int:record_id>")
def view_history(record_id):
    if not session.get("user"):
        return redirect("/login")

    db = get_db()
    record = db.execute("SELECT * FROM usage WHERE id=? AND user_id=?", (record_id, session["user_id"])).fetchone()
    if not record:
        return "Record not found"

    daily_list = eval(record["daily_hours"]) if record["daily_hours"] else []

    return render_template("history.html", record=record, daily_list=daily_list)


if __name__ == "__main__":
    init_db()
    app.run(debug=False, host="0.0.0.0")
