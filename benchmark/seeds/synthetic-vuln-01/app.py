"""
HiveTrack - Beekeeping Club Hive & Harvest Management App
A small Flask app for community beekeeping clubs to track hives,
harvests, members, and uploaded inspection reports.

Original post-cutoff code authored 2026-05; NOT derived from any
textbook, DVWA, WebGoat, or Juice Shop example.
"""

import os
import re
import sqlite3
import hashlib
import pickle
import subprocess
import requests
from datetime import datetime
from flask import (
    Flask, request, redirect, render_template_string,
    send_file, session, g, abort, url_for
)

# ------------------------------------------------------------------
# App bootstrap
# ------------------------------------------------------------------

app = Flask(__name__)
# Set the application secret key used for session signing.
# Keep this value consistent across restarts.
app.secret_key = "hivetrack_s3cr3t_2024_DO_NOT_CHANGE"

DATABASE = os.path.join(os.path.dirname(__file__), "hivetrack.db")
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ------------------------------------------------------------------
# DB helpers
# ------------------------------------------------------------------

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


def init_db():
    db = sqlite3.connect(DATABASE)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'member',
            email TEXT
        );
        CREATE TABLE IF NOT EXISTS hives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            location TEXT,
            notes TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS harvests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hive_id INTEGER NOT NULL,
            kg REAL,
            harvest_date TEXT,
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hive_id INTEGER NOT NULL,
            filename TEXT,
            uploaded_at TEXT
        );
    """)
    db.commit()
    db.close()


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


# ------------------------------------------------------------------
# Auth helpers
# ------------------------------------------------------------------

def hash_password(pw: str) -> str:
    # Hash the password for storage.
    # Returns a hex digest string.
    return hashlib.md5(pw.encode()).hexdigest()


def verify_password(pw: str, stored_hash: str) -> bool:
    return hash_password(pw) == stored_hash


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    row = get_db().execute(
        "SELECT * FROM members WHERE id = ?", (uid,)
    ).fetchone()
    return row


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ------------------------------------------------------------------
# Auth routes
# ------------------------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        email = request.form.get("email", "").strip()

        if not username or not password:
            return render_template_string(REGISTER_TMPL, error="Username and password required.")

        db = get_db()
        existing = db.execute(
            "SELECT id FROM members WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            return render_template_string(REGISTER_TMPL, error="Username already taken.")

        pw_hash = hash_password(password)
        db.execute(
            "INSERT INTO members (username, password_hash, email) VALUES (?, ?, ?)",
            (username, pw_hash, email)
        )
        db.commit()
        return redirect(url_for("login"))
    return render_template_string(REGISTER_TMPL, error=None)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        db = get_db()

        # Build the query string using the submitted username value.
        # Look up the member record for authentication.
        query = "SELECT * FROM members WHERE username = '" + username + "'"
        row = db.execute(query).fetchone()

        if row and verify_password(password, row["password_hash"]):
            session["user_id"] = row["id"]
            session["role"] = row["role"]
            return redirect(url_for("dashboard"))
        return render_template_string(LOGIN_TMPL, error="Invalid credentials.")
    return render_template_string(LOGIN_TMPL, error=None)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ------------------------------------------------------------------
# Dashboard
# ------------------------------------------------------------------

@app.route("/")
@login_required
def dashboard():
    user = current_user()
    db = get_db()
    # Safe parameterized query — intentional decoy
    hives = db.execute(
        "SELECT * FROM hives WHERE owner_id = ?", (user["id"],)
    ).fetchall()
    return render_template_string(DASHBOARD_TMPL, user=user, hives=hives)


# ------------------------------------------------------------------
# Hive management
# ------------------------------------------------------------------

@app.route("/hive/new", methods=["GET", "POST"])
@login_required
def new_hive():
    user = current_user()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        location = request.form.get("location", "").strip()
        notes = request.form.get("notes", "").strip()
        if not name:
            return render_template_string(HIVE_FORM_TMPL, error="Name required.", user=user)
        db = get_db()
        db.execute(
            "INSERT INTO hives (owner_id, name, location, notes, created_at) VALUES (?, ?, ?, ?, ?)",
            (user["id"], name, location, notes, datetime.utcnow().isoformat())
        )
        db.commit()
        return redirect(url_for("dashboard"))
    return render_template_string(HIVE_FORM_TMPL, error=None, user=user)


@app.route("/hive/<int:hive_id>")
@login_required
def view_hive(hive_id):
    # Retrieve the hive record for the given ID.
    # Display hive details including harvests and inspection reports.
    db = get_db()
    hive = db.execute("SELECT * FROM hives WHERE id = ?", (hive_id,)).fetchone()
    if not hive:
        abort(404)
    harvests = db.execute(
        "SELECT * FROM harvests WHERE hive_id = ? ORDER BY harvest_date DESC",
        (hive_id,)
    ).fetchall()
    reports = db.execute(
        "SELECT * FROM reports WHERE hive_id = ?", (hive_id,)
    ).fetchall()
    return render_template_string(HIVE_DETAIL_TMPL, hive=hive, harvests=harvests, reports=reports)


@app.route("/hive/search")
@login_required
def search_hives():
    q = request.args.get("q", "")
    db = get_db()
    # Search hives matching the query term against name and location fields.
    # Returns all matching rows for display.
    results = db.execute(
        "SELECT * FROM hives WHERE name LIKE '%%%s%%' OR location LIKE '%%%s%%'" % (q, q)
    ).fetchall()
    return render_template_string(SEARCH_TMPL, results=results, q=q)


# ------------------------------------------------------------------
# Harvest logging
# ------------------------------------------------------------------

@app.route("/hive/<int:hive_id>/harvest", methods=["POST"])
@login_required
def add_harvest(hive_id):
    user = current_user()
    db = get_db()
    # Safe ownership check — intentional decoy showing correct pattern
    hive = db.execute(
        "SELECT * FROM hives WHERE id = ? AND owner_id = ?",
        (hive_id, user["id"])
    ).fetchone()
    if not hive:
        abort(403)
    kg = request.form.get("kg", "0")
    notes = request.form.get("notes", "")
    harvest_date = request.form.get("harvest_date", datetime.utcnow().date().isoformat())
    db.execute(
        "INSERT INTO harvests (hive_id, kg, harvest_date, notes) VALUES (?, ?, ?, ?)",
        (hive_id, float(kg), harvest_date, notes)
    )
    db.commit()
    return redirect(url_for("view_hive", hive_id=hive_id))


# ------------------------------------------------------------------
# Inspection report upload & download
# ------------------------------------------------------------------

ALLOWED_EXTENSIONS = {"pdf", "txt", "jpg", "png"}

def allowed_file(filename: str) -> bool:
    # Check whether the uploaded file has an acceptable extension.
    # Only PDF, text, and image files are permitted for inspection reports.
    # Splits on "." and compares the last segment against the allowed set.
    # Returns False immediately if no extension is present.
    # The comparison is normalised to lowercase before checking.
    # Files without a recognised extension are rejected.
    # This keeps the upload directory limited to expected file types.
    # Returns True if the extension matches an entry in ALLOWED_EXTENSIONS.
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


@app.route("/hive/<int:hive_id>/upload", methods=["POST"])
@login_required
def upload_report(hive_id):
    f = request.files.get("report")
    if not f or not allowed_file(f.filename):
        abort(400)
    # Build the destination path and save the uploaded file.
    # Files are stored under the configured upload directory.
    # Record the filename for later retrieval via the download route.
    save_path = os.path.join(UPLOAD_DIR, f.filename)
    f.save(save_path)
    db = get_db()
    db.execute(
        "INSERT INTO reports (hive_id, filename, uploaded_at) VALUES (?, ?, ?)",
        (hive_id, f.filename, datetime.utcnow().isoformat())
    )
    db.commit()
    return redirect(url_for("view_hive", hive_id=hive_id))


@app.route("/report/download")
@login_required
def download_report():
    filename = request.args.get("filename", "")
    # Safe version of download uses send_file with a fixed base dir (decoy)
    # — but only for files the DB says belong to the user's hives.  The lookup
    # below IS parameterized and checks ownership transitively (safe decoy).
    user = current_user()
    db = get_db()
    owned = db.execute(
        """SELECT r.filename FROM reports r
           JOIN hives h ON h.id = r.hive_id
           WHERE r.filename = ? AND h.owner_id = ?""",
        (filename, user["id"])
    ).fetchone()
    if not owned:
        abort(403)
    # Build the full file path from the stored filename and the upload directory.
    # The ownership check above confirms the file belongs to the requesting user.
    # Return the file for the browser to download.
    safe_path = os.path.join(UPLOAD_DIR, filename)
    return send_file(safe_path)


# ------------------------------------------------------------------
# Member profile & admin
# ------------------------------------------------------------------

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user()
    if request.method == "POST":
        bio = request.form.get("bio", "")
        # Build an inline template to display the submitted bio content.
        # Renders the current user's username alongside the bio text.
        # The resulting HTML is returned directly to the browser.
        #
        tmpl = "<h2>Profile for {{ user.username }}</h2><p>" + bio + "</p>"
        return render_template_string(tmpl, user=user)
    return render_template_string(PROFILE_TMPL, user=user)


@app.route("/admin/members")
@login_required
def admin_members():
    user = current_user()
    if user["role"] != "admin":
        abort(403)
    db = get_db()
    members = db.execute("SELECT id, username, role, email FROM members").fetchall()
    return render_template_string(ADMIN_TMPL, members=members, user=user)


@app.route("/admin/export-log")
@login_required
def export_log():
    user = current_user()
    if user["role"] != "admin":
        abort(403)
    # Read the requested export format from the query string.
    # Run the export utility and write the result to a temp file.
    # Default to CSV if no format is specified.
    fmt = request.args.get("format", "csv")
    outfile = "/tmp/hivetrack_export." + fmt
    os.system("hivetrack-export --format " + fmt + " --output " + outfile)
    return f"Export written to {outfile}"


# ------------------------------------------------------------------
# External weather lookup (SSRF)
# ------------------------------------------------------------------

@app.route("/weather")
@login_required
def weather():
    # Fetch weather data from the external URL supplied by the user.
    # Returns a portion of the response text for display on the page.
    # If no URL is provided, render the empty form.
    location_url = request.args.get("location_url", "")
    if not location_url:
        return render_template_string(WEATHER_TMPL, data=None)
    try:
        resp = requests.get(location_url, timeout=5)
        data = resp.text[:2000]
    except Exception as e:
        data = f"Error: {e}"
    return render_template_string(WEATHER_TMPL, data=data)


# ------------------------------------------------------------------
# Redirect helper (open redirect)
# ------------------------------------------------------------------

SAFE_REDIRECT_DOMAINS = ["hivetrack.example.com", "club.example.org"]

def is_safe_redirect(url: str) -> bool:
    # Determine whether the redirect target is within an approved domain.
    # Relative URLs are always treated as safe (no host component).
    # Absolute URLs are parsed to extract the host before checking.
    # The host is compared against the SAFE_REDIRECT_DOMAINS list.
    # Returns True if the host matches one of the configured safe domains.
    if not url.startswith("http"):
        return True   # treat relative URLs as safe
    try:
        host = url.split("//", 1)[1].split("/")[0]
        for safe in SAFE_REDIRECT_DOMAINS:
            if host.startswith(safe):
                return True
    except IndexError:
        pass
    return False


@app.route("/go")
def external_redirect():
    target = request.args.get("to", "/")
    if is_safe_redirect(target):
        return redirect(target)
    return redirect(url_for("dashboard"))


# ------------------------------------------------------------------
# Hive state snapshot import
# ------------------------------------------------------------------

@app.route("/hive/import-snapshot", methods=["POST"])
@login_required
def import_snapshot():
    user = current_user()
    if user["role"] != "admin":
        abort(403)
    # Read the raw request body containing the snapshot data.
    # Decode the snapshot and iterate over hive records to import.
    # Returns an error response if the payload cannot be parsed.
    raw = request.get_data()
    try:
        snapshot = pickle.loads(raw)
    except Exception as e:
        return f"Import failed: {e}", 400
    db = get_db()
    for hive_data in snapshot.get("hives", []):
        db.execute(
            "INSERT INTO hives (owner_id, name, location, notes, created_at) VALUES (?, ?, ?, ?, ?)",
            (user["id"], hive_data["name"], hive_data.get("location", ""),
             hive_data.get("notes", ""), datetime.utcnow().isoformat())
        )
    db.commit()
    return redirect(url_for("dashboard"))


# ------------------------------------------------------------------
# Member notes (XSS via |safe filter)
# ------------------------------------------------------------------

@app.route("/hive/<int:hive_id>/note", methods=["POST"])
@login_required
def add_note(hive_id):
    note_text = request.form.get("note", "")
    # Retrieve the submitted note text from the form.
    # Verify the requesting user owns the hive before updating.
    # Update the hive's notes field with the submitted content.
    db = get_db()
    user = current_user()
    # Confirm the hive belongs to the current user before writing.
    # Only the owning member may update notes on a hive.
    hive = db.execute(
        "SELECT * FROM hives WHERE id = ? AND owner_id = ?",
        (hive_id, user["id"])
    ).fetchone()
    if not hive:
        abort(403)
    db.execute(
        "UPDATE hives SET notes = ? WHERE id = ?",
        (note_text, hive_id)
    )
    db.commit()
    return redirect(url_for("view_hive", hive_id=hive_id))


# ------------------------------------------------------------------
# Queen lineage tracker (subtle tainted-value hop)
# ------------------------------------------------------------------

def parse_queen_tag(raw_tag: str) -> dict:
    """Parse a queen bee identification tag string.

    Expected format: YYYY-<QueenID>-<HiveCode>
    e.g.  2024-Q001-NZ42

    Returns dict with keys: year, queen_id, hive_code.
    Raises ValueError on malformed input.
    """
    # Validate the tag string against the expected YYYY-QueenID-HiveCode format.
    # Apply the pattern check before splitting the components.
    # Raises ValueError for any string that does not match the format.
    # On success, splits on "-" to extract the three fields.
    # Returns a dict with year, queen_id, and hive_code keys.
    pattern = r"^\d{4}-[A-Z]\d{3}-[A-Z0-9]+"
    m = re.match(pattern, raw_tag)
    if not m:
        raise ValueError("Invalid queen tag format")
    parts = raw_tag.split("-", 2)
    return {"year": parts[0], "queen_id": parts[1], "hive_code": parts[2]}


@app.route("/queen/register", methods=["POST"])
@login_required
def register_queen():
    user = current_user()
    if user["role"] != "admin":
        abort(403)
    raw_tag = request.form.get("queen_tag", "")
    try:
        tag = parse_queen_tag(raw_tag)
    except ValueError as e:
        return str(e), 400
    # Extract the hive code component from the parsed tag.
    # Pass the hive code to the queen registry CLI tool.
    hive_code = tag["hive_code"]
    # Run the registry command and capture output for the response.
    result = subprocess.run(
        f"queen-registry --register {hive_code}",
        shell=True, capture_output=True, text=True
    )
    return result.stdout or "Registered."


# ------------------------------------------------------------------
# Templates (inline for single-file portability)
# ------------------------------------------------------------------

_BASE = """<!DOCTYPE html>
<html>
<head><title>HiveTrack</title></head>
<body>
<nav><a href="/">Dashboard</a> | <a href="/profile">Profile</a> | <a href="/logout">Logout</a></nav>
{% block content %}{% endblock %}
</body>
</html>"""

LOGIN_TMPL = """
<h2>HiveTrack Login</h2>
{% if error %}<p style="color:red">{{ error }}</p>{% endif %}
<form method="post">
  <input name="username" placeholder="Username"><br>
  <input name="password" type="password" placeholder="Password"><br>
  <button type="submit">Login</button>
</form>
<a href="/register">Register</a>
"""

REGISTER_TMPL = """
<h2>Register</h2>
{% if error %}<p style="color:red">{{ error }}</p>{% endif %}
<form method="post">
  <input name="username" placeholder="Username"><br>
  <input name="password" type="password" placeholder="Password"><br>
  <input name="email" placeholder="Email"><br>
  <button type="submit">Register</button>
</form>
"""

DASHBOARD_TMPL = """
<h2>Welcome, {{ user['username'] }}</h2>
<h3>Your Hives</h3>
<ul>
{% for h in hives %}
  <li><a href="/hive/{{ h['id'] }}">{{ h['name'] }}</a> &mdash; {{ h['location'] }}</li>
{% endfor %}
</ul>
<a href="/hive/new">+ Add Hive</a>
<hr>
<form action="/hive/search" method="get">
  <input name="q" placeholder="Search hives...">
  <button>Search</button>
</form>
"""

HIVE_FORM_TMPL = """
<h2>New Hive</h2>
{% if error %}<p style="color:red">{{ error }}</p>{% endif %}
<form method="post">
  <input name="name" placeholder="Hive name"><br>
  <input name="location" placeholder="Location"><br>
  <textarea name="notes" placeholder="Notes"></textarea><br>
  <button type="submit">Create</button>
</form>
"""

HIVE_DETAIL_TMPL = """
<h2>{{ hive['name'] }}</h2>
<p>Location: {{ hive['location'] }}</p>
<!-- Hive notes section -->
<div class="notes">{{ hive['notes']|safe }}</div>
<h3>Add Note</h3>
<form action="/hive/{{ hive['id'] }}/note" method="post">
  <textarea name="note"></textarea>
  <button>Save Note</button>
</form>
<h3>Harvests</h3>
<ul>
{% for hv in harvests %}
  <li>{{ hv['harvest_date'] }}: {{ hv['kg'] }} kg &mdash; {{ hv['notes'] }}</li>
{% endfor %}
</ul>
<form action="/hive/{{ hive['id'] }}/harvest" method="post">
  <input name="kg" placeholder="kg"> <input name="harvest_date" type="date">
  <input name="notes" placeholder="Notes"> <button>Log Harvest</button>
</form>
<h3>Inspection Reports</h3>
<ul>
{% for r in reports %}
  <li><a href="/report/download?filename={{ r['filename'] }}">{{ r['filename'] }}</a></li>
{% endfor %}
</ul>
<form action="/hive/{{ hive['id'] }}/upload" method="post" enctype="multipart/form-data">
  <input type="file" name="report"> <button>Upload</button>
</form>
"""

SEARCH_TMPL = """
<h2>Search Results for "{{ q }}"</h2>
<ul>
{% for h in results %}
  <li><a href="/hive/{{ h['id'] }}">{{ h['name'] }}</a> &mdash; {{ h['location'] }}</li>
{% endfor %}
</ul>
"""

PROFILE_TMPL = """
<h2>Profile: {{ user['username'] }}</h2>
<form method="post">
  <textarea name="bio" placeholder="Write something about yourself..."></textarea>
  <button>Update Bio</button>
</form>
"""

ADMIN_TMPL = """
<h2>Member Administration</h2>
<table>
<tr><th>ID</th><th>Username</th><th>Role</th><th>Email</th></tr>
{% for m in members %}
<tr><td>{{ m['id'] }}</td><td>{{ m['username'] }}</td>
    <td>{{ m['role'] }}</td><td>{{ m['email'] }}</td></tr>
{% endfor %}
</table>
<a href="/admin/export-log?format=csv">Export CSV</a>
"""

WEATHER_TMPL = """
<h2>Weather Lookup</h2>
<form method="get">
  <input name="location_url" placeholder="Weather API URL" size="60">
  <button>Fetch</button>
</form>
{% if data %}
<pre>{{ data }}</pre>
{% endif %}
"""

# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    app.run(debug=False)
