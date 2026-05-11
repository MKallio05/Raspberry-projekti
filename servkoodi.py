from flask import Flask, render_template, Response, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import random
import json
import time

app = Flask(__name__)
app.secret_key = "tosirandomsecret"

DB_PATH          = "slots.db"
SYMBOLS          = ["♠", "♥", "♦", "♣", "★"]
STARTING_CREDITS = 100
ADMIN_PASSWORD   = "admin1234"
PI_USERNAME      = "player1"  

WIN_LINES = [
    ("row0",  [(0,0),(0,1),(0,2)]),
    ("row1",  [(1,0),(1,1),(1,2)]),
    ("row2",  [(2,0),(2,1),(2,2)]),
    ("diag0", [(0,0),(1,1),(2,2)]),
    ("diag1", [(0,2),(1,1),(2,0)]),
]

last_spin_results = {}


# ── Database ──────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT    UNIQUE NOT NULL,
                password TEXT    NOT NULL,
                credits  INTEGER NOT NULL DEFAULT 100,
                bet      INTEGER NOT NULL DEFAULT 1
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS spins (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL,
                bet           INTEGER NOT NULL,
                win           INTEGER NOT NULL,
                credits_after INTEGER NOT NULL,
                timestamp     DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        db.commit()


# ── Auth helpers ──────────────────────────────────────────

def logged_in():
    return "user_id" in session

def admin_logged_in():
    return session.get("is_admin") is True

def current_user():
    if not logged_in():
        return None
    with get_db() as db:
        return db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

def require_login(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not logged_in():
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def require_admin(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not admin_logged_in():
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


# ── Auth routes ───────────────────────────────────────────

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    if not username or not password:
        return render_template("register.html", error="Fill in all fields.")
    if len(username) < 3:
        return render_template("register.html", error="Username too short (min 3 chars).")
    if len(password) < 4:
        return render_template("register.html", error="Password too short (min 4 chars).")
    hashed = generate_password_hash(password)
    try:
        with get_db() as db:
            db.execute("INSERT INTO users (username, password, credits) VALUES (?, ?, ?)",
                       (username, hashed, STARTING_CREDITS))
            db.commit()
    except sqlite3.IntegrityError:
        return render_template("register.html", error="Username already taken.")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    with get_db() as db:
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not user or not check_password_hash(user["password"], password):
        return render_template("login.html", error="Invalid username or password.")
    session["user_id"] = user["id"]
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── Admin ─────────────────────────────────────────────────

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "GET":
        return render_template("admin_login.html")
    if request.form.get("password", "") != ADMIN_PASSWORD:
        return render_template("admin_login.html", error="Wrong password.")
    session["is_admin"] = True
    return redirect(url_for("admin_panel"))

@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))

@app.route("/admin")
@require_admin
def admin_panel():
    with get_db() as db:
        users = db.execute("""
            SELECT u.id, u.username, u.credits,
                COUNT(s.id) AS total_spins,
                COALESCE(SUM(s.win), 0) AS total_won,
                COALESCE(SUM(s.bet), 0) AS total_bet,
                COALESCE(SUM(CASE WHEN s.win > 0 THEN 1 ELSE 0 END), 0) AS wins
            FROM users u LEFT JOIN spins s ON s.user_id = u.id
            GROUP BY u.id ORDER BY u.username ASC
        """).fetchall()
    return render_template("admin.html", users=users)

@app.route("/admin/credits", methods=["POST"])
@require_admin
def admin_credits():
    uid    = request.form.get("user_id", type=int)
    amount = request.form.get("amount",  type=int)
    if uid is not None and amount is not None:
        with get_db() as db:
            db.execute("UPDATE users SET credits = MAX(0, credits + ?) WHERE id = ?", (amount, uid))
            db.commit()
    return redirect(url_for("admin_panel"))

@app.route("/admin/delete", methods=["POST"])
@require_admin
def admin_delete():
    uid = request.form.get("user_id", type=int)
    if uid is not None:
        with get_db() as db:
            db.execute("DELETE FROM spins WHERE user_id = ?", (uid,))
            db.execute("DELETE FROM users WHERE id = ?", (uid,))
            db.commit()
    return redirect(url_for("admin_panel"))

@app.route("/admin/user/<int:uid>")
@require_admin
def admin_user_stats(uid):
    with get_db() as db:
        user = db.execute("SELECT id, username, credits FROM users WHERE id = ?", (uid,)).fetchone()
        if not user:
            return redirect(url_for("admin_panel"))
        balance_rows = db.execute(
            "SELECT timestamp, credits_after FROM spins WHERE user_id = ? ORDER BY timestamp ASC", (uid,)).fetchall()
        spin_rows = db.execute(
            "SELECT timestamp, bet, win FROM spins WHERE user_id = ? ORDER BY timestamp ASC", (uid,)).fetchall()
        summary = db.execute("""
            SELECT COUNT(*) AS total_spins,
                COALESCE(SUM(bet), 0) AS total_bet,
                COALESCE(SUM(win), 0) AS total_won,
                COALESCE(SUM(CASE WHEN win > 0 THEN 1 ELSE 0 END), 0) AS wins,
                COALESCE(SUM(CASE WHEN win = 0 THEN 1 ELSE 0 END), 0) AS losses
            FROM spins WHERE user_id = ?
        """, (uid,)).fetchone()
    return render_template("admin_user.html",
        user=dict(user),
        balance_data=json.dumps([{"t": r["timestamp"], "c": r["credits_after"]} for r in balance_rows]),
        spin_data=json.dumps([{"t": r["timestamp"], "bet": r["bet"], "win": r["win"]} for r in spin_rows]),
        summary=dict(summary))


@app.route("/admin/stats")
@require_admin
def admin_stats():
    with get_db() as db:
        summary = db.execute("""
            SELECT
                COUNT(*)                                                AS total_spins,
                COALESCE(SUM(win), 0)                                   AS total_won,
                COALESCE(SUM(bet), 0)                                   AS total_bet,
                COALESCE(SUM(CASE WHEN win > 0 THEN 1 ELSE 0 END), 0)  AS total_wins,
                COALESCE(SUM(CASE WHEN win = 0 THEN 1 ELSE 0 END), 0)  AS total_losses
            FROM spins
        """).fetchone()

        per_user = db.execute("""
            SELECT u.username,
                COUNT(s.id)                                                AS spins,
                COALESCE(SUM(CASE WHEN s.win > 0 THEN 1 ELSE 0 END), 0)  AS wins,
                COALESCE(SUM(s.win), 0)                                    AS total_won,
                COALESCE(SUM(s.bet), 0)                                    AS total_bet
            FROM users u
            LEFT JOIN spins s ON s.user_id = u.id
            GROUP BY u.id
            ORDER BY spins DESC
        """).fetchall()

    return render_template("admin_stats.html",
        summary={
            "total_spins":  summary["total_spins"]  or 0,
            "total_won":    summary["total_won"]    or 0,
            "total_bet":    summary["total_bet"]    or 0,
            "total_wins":   summary["total_wins"]   or 0,
            "total_losses": summary["total_losses"] or 0,
        },
        per_user=json.dumps([{
            "username":  r["username"],
            "spins":     r["spins"],
            "wins":      r["wins"],
            "total_won": r["total_won"],
            "total_bet": r["total_bet"],
        } for r in per_user]),
    )


# ── Pi routes (no session needed) ────────────────────────

def get_pi_user_id():
    with get_db() as db:
        row = db.execute("SELECT id FROM users WHERE username = ?", (PI_USERNAME,)).fetchone()
        return row["id"] if row else None

@app.route("/pi/spin", methods=["POST"])
def pi_spin():
    uid = get_pi_user_id()
    if uid is None:
        return jsonify({"error": f"Pi user '{PI_USERNAME}' not found"}), 404
    return jsonify(do_spin(uid))

@app.route("/pi/bet_up")
def pi_bet_up():
    uid = get_pi_user_id()
    if uid is None:
        return jsonify({"error": f"Pi user '{PI_USERNAME}' not found"}), 404
    with get_db() as db:
        db.execute("UPDATE users SET bet = bet + 1 WHERE id = ?", (uid,))
        db.commit()
        user = db.execute("SELECT bet FROM users WHERE id = ?", (uid,)).fetchone()
    return str(user["bet"])

@app.route("/pi/bet_down")
def pi_bet_down():
    uid = get_pi_user_id()
    if uid is None:
        return jsonify({"error": f"Pi user '{PI_USERNAME}' not found"}), 404
    with get_db() as db:
        db.execute("UPDATE users SET bet = MAX(1, bet - 1) WHERE id = ?", (uid,))
        db.commit()
        user = db.execute("SELECT bet FROM users WHERE id = ?", (uid,)).fetchone()
    return str(user["bet"])


# ── Game routes ───────────────────────────────────────────

@app.route("/")
@require_login
def index():
    user = current_user()
    return render_template("testi2.html", username=user["username"])

@app.route("/spin", methods=["POST"])
@require_login
def spin():
    return jsonify(do_spin(session["user_id"]))

@app.route("/bet_up")
@require_login
def bet_up():
    uid = session["user_id"]
    with get_db() as db:
        db.execute("UPDATE users SET bet = bet + 1 WHERE id = ?", (uid,))
        db.commit()
        user = db.execute("SELECT bet FROM users WHERE id = ?", (uid,)).fetchone()
    return str(user["bet"])

@app.route("/bet_down")
@require_login
def bet_down():
    uid = session["user_id"]
    with get_db() as db:
        db.execute("UPDATE users SET bet = MAX(1, bet - 1) WHERE id = ?", (uid,))
        db.commit()
        user = db.execute("SELECT bet FROM users WHERE id = ?", (uid,)).fetchone()
    return str(user["bet"])

@app.route("/state")
@require_login
def state():
    user = current_user()
    return jsonify({"credits": user["credits"], "bet": user["bet"]})

@app.route("/stream")
@require_login
def stream():
    uid = session["user_id"]
    def generate():
        last_sent = None
        while True:
            result = last_spin_results.get(uid)
            if result is not None and result != last_sent:
                yield f"data: {json.dumps(result)}\n\n"
                last_sent = result
            time.sleep(0.1)
    return Response(generate(), mimetype="text/event-stream")

@app.route("/stats")
@require_login
def stats():
    uid = session["user_id"]
    with get_db() as db:
        user = db.execute("SELECT username FROM users WHERE id = ?", (uid,)).fetchone()
        balance_rows = db.execute(
            "SELECT timestamp, credits_after FROM spins WHERE user_id = ? ORDER BY timestamp ASC", (uid,)).fetchall()
        spin_rows = db.execute(
            "SELECT timestamp, bet, win FROM spins WHERE user_id = ? ORDER BY timestamp ASC", (uid,)).fetchall()
        summary = db.execute("""
            SELECT COUNT(*) AS total_spins,
                COALESCE(SUM(bet), 0) AS total_bet,
                COALESCE(SUM(win), 0) AS total_won,
                COALESCE(SUM(CASE WHEN win > 0 THEN 1 ELSE 0 END), 0) AS wins,
                COALESCE(SUM(CASE WHEN win = 0 THEN 1 ELSE 0 END), 0) AS losses
            FROM spins WHERE user_id = ?
        """, (uid,)).fetchone()
    return render_template("stats.html",
        username=user["username"],
        balance_data=json.dumps([{"t": r["timestamp"], "c": r["credits_after"]} for r in balance_rows]),
        spin_data=json.dumps([{"t": r["timestamp"], "bet": r["bet"], "win": r["win"]} for r in spin_rows]),
        summary=dict(summary))


# ── Spin logic ────────────────────────────────────────────

def do_spin(user_id):
    with get_db() as db:
        user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        credits, bet = user["credits"], user["bet"]
        if credits < bet:
            return {"error": "not enough credits"}
        credits -= bet
        grid = [[random.choice(SYMBOLS) for _ in range(3)] for _ in range(3)]
        PARTIAL_LINES = ["row0", "row1", "row2"]  # only rows count for partial wins

        win_lines = []
        partial_lines = 0
        for name, positions in WIN_LINES:
            syms = [grid[r][c] for r, c in positions]
            if syms[0] == syms[1] == syms[2]:
                win_lines.append(name)
            elif syms[0] == syms[1] and name in PARTIAL_LINES:
                partial_lines += 1

        win = len(win_lines) * bet * 3 + partial_lines * bet

        credits += win
        db.execute("UPDATE users SET credits = ? WHERE id = ?", (credits, user_id))
        db.execute("INSERT INTO spins (user_id, bet, win, credits_after) VALUES (?, ?, ?, ?)",
                   (user_id, bet, win, credits))
        db.commit()
    result = {"grid": grid, "win_lines": win_lines, "credits": credits, "bet": bet, "win": win}
    last_spin_results[user_id] = result
    return result


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, threaded=True, debug=True)