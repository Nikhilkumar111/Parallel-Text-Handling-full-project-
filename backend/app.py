import os
import json
import sqlite3
import traceback
import smtplib
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from backend_text_analysis import TextAnalyzer

# ==============================
# LOAD ENV
# ==============================
load_dotenv()

app = Flask(__name__)

# ==============================
# CORS CONFIG (IMPORTANT)
# ==============================
CORS(
    app,
    resources={r"/api/*": {
        "origins": [
            "http://localhost:3000",
            "https://parallel-text-handling-full-project.vercel.app"
        ]
    }}
)

# ==============================
# DATABASE
# ==============================
DATABASE_PATH = os.getenv(
    "DATABASE_PATH",
    os.path.join(os.getcwd(), "users.db")
)

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                email TEXT UNIQUE,
                password TEXT
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS search_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                column_name TEXT,
                content TEXT,
                sentiment_score REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS inbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                message TEXT,
                type TEXT,
                report_data TEXT,
                email_sent INTEGER DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS activity_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                operations TEXT,
                status TEXT,
                records_count INTEGER,
                processing_time REAL,
                report_data TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS contact_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                email TEXT,
                message TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

init_db()

# ==============================
# AUTH ROUTES
# ==============================
@app.route("/api/signup", methods=["POST"])
def signup():
    try:
        data = request.json
        password_hash = generate_password_hash(data["password"])

        with get_db() as db:
            db.execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (data["full_name"], data["email"], password_hash)
            )
            db.commit()

        return jsonify({"message": "Signup successful"}), 201

    except sqlite3.IntegrityError:
        return jsonify({"message": "Email already exists"}), 409

    except Exception as e:
        traceback.print_exc()
        return jsonify({"message": str(e)}), 500


@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    with get_db() as db:
        user = db.execute(
            "SELECT * FROM users WHERE email = ?",
            (data["email"],)
        ).fetchone()

    if user and check_password_hash(user["password"], data["password"]):
        return jsonify({"message": "Login success"}), 200

    return jsonify({"message": "Invalid credentials"}), 401


# ==============================
# CONTACT
# ==============================
@app.route("/api/contact", methods=["POST"])
def contact():
    try:
        data = request.json
        with get_db() as db:
            db.execute(
                "INSERT INTO contact_messages (name, email, message) VALUES (?, ?, ?)",
                (data["name"], data["email"], data["message"])
            )
            db.commit()
        return jsonify({"message": "Message received"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================
# ANALYSIS
# ==============================
@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.json

    analyzer = TextAnalyzer()
    results, rows, stats, scores = analyzer.run_pipeline(
        data.get("text", ""),
        data.get("operations", [])
    )

    with get_db() as db:
        for i, row in enumerate(rows[:50]):
            for col, value in row.items():
                if len(str(value)) > 2:
                    db.execute(
                        "INSERT INTO search_index (filename, column_name, content, sentiment_score) VALUES (?, ?, ?, ?)",
                        (
                            data.get("filename", "dataset.csv"),
                            col,
                            str(value),
                            scores[i] if i < len(scores) else 0
                        )
                    )

        db.execute(
            "INSERT INTO activity_history (filename, operations, status, records_count, processing_time, report_data) VALUES (?, ?, ?, ?, ?, ?)",
            (
                data.get("filename", "dataset.csv"),
                ", ".join(data.get("operations", [])),
                "Completed",
                len(rows),
                stats["processing_time"],
                json.dumps(results)
            )
        )
        db.commit()

    return jsonify({"results": results, "stats": stats})


# ==============================
# FETCH DATA
# ==============================
@app.route("/api/search")
def search():
    q = request.args.get("q", "")
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM search_index WHERE content LIKE ? ORDER BY timestamp DESC LIMIT 20",
            (f"%{q}%",)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/inbox")
def inbox():
    with get_db() as db:
        rows = db.execute("SELECT * FROM inbox ORDER BY timestamp DESC").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/history")
def history():
    with get_db() as db:
        rows = db.execute("SELECT * FROM activity_history ORDER BY timestamp DESC").fetchall()
    return jsonify([dict(r) for r in rows])


# ==============================
# RUN APP
# ==============================
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5001)),
        debug=False
    )
