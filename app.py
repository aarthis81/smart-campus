import sqlite3
from datetime import date
from flask import Flask, render_template, request, redirect, url_for, flash, g

app = Flask(__name__)
app.secret_key = "practice-secret"   # needed for flash messages
DATABASE = "bookings.db"


# ---------- Database helpers ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row   # lets us use row["name"]
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)
    db.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            capacity INTEGER NOT NULL
        )""")
    db.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            student_name TEXT NOT NULL,
            date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            FOREIGN KEY (room_id) REFERENCES rooms (id)
        )""")
    # Seed sample rooms only once
    if db.execute("SELECT COUNT(*) FROM rooms").fetchone()[0] == 0:
        db.executemany(
            "INSERT INTO rooms (name, capacity) VALUES (?, ?)",
            [("Library Room A", 4), ("Library Room B", 6),
             ("Discussion Hall", 10), ("Quiet Pod", 2)],
        )
    db.commit()
    db.close()


def has_conflict(room_id, day, start, end):
    """Two time ranges overlap if each starts before the other ends."""
    row = get_db().execute(
        "SELECT 1 FROM bookings "
        "WHERE room_id = ? AND date = ? AND start_time < ? AND end_time > ?",
        (room_id, day, end, start),
    ).fetchone()
    return row is not None


# ---------- Routes ----------
@app.route("/")
def index():
    today = date.today().isoformat()
    rooms = get_db().execute(
        "SELECT r.*, "
        "(SELECT COUNT(*) FROM bookings b WHERE b.room_id = r.id AND b.date = ?) "
        "AS today_count FROM rooms r",
        (today,),
    ).fetchall()
    return render_template("index.html", rooms=rooms)


@app.route("/book", methods=["GET", "POST"])
def book():
    db = get_db()
    rooms = db.execute("SELECT * FROM rooms").fetchall()
    today = date.today().isoformat()

    if request.method == "POST":
        room_id = request.form.get("room_id")
        name = request.form.get("student_name", "").strip()
        day = request.form.get("date")
        start = request.form.get("start_time")
        end = request.form.get("end_time")

        if not (room_id and name and day and start and end):
            flash("Please fill in every field.", "error")
        elif day < today:
            flash("You can't book a date in the past.", "error")
        elif end <= start:
            flash("End time must be after the start time.", "error")
        elif has_conflict(room_id, day, start, end):
            flash("Sorry, that room is already booked at that time.", "error")
        else:
            db.execute(
                "INSERT INTO bookings (room_id, student_name, date, start_time, end_time) "
                "VALUES (?, ?, ?, ?, ?)",
                (room_id, name, day, start, end),
            )
            db.commit()
            flash("Room booked successfully!", "success")
            return redirect(url_for("bookings"))

    selected = request.args.get("room_id", "")
    return render_template("book.html", rooms=rooms, today=today, selected=selected)


@app.route("/bookings")
def bookings():
    rows = get_db().execute(
        "SELECT b.id, b.student_name, b.date, b.start_time, b.end_time, r.name AS room_name "
        "FROM bookings b JOIN rooms r ON r.id = b.room_id "
        "ORDER BY b.date, b.start_time"
    ).fetchall()
    return render_template("bookings.html", bookings=rows)


@app.route("/cancel/<int:booking_id>", methods=["POST"])
def cancel(booking_id):
    db = get_db()
    db.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
    db.commit()
    flash("Booking cancelled.", "success")
    return redirect(url_for("bookings"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)