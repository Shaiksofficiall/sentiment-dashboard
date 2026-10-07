import os
import sqlite3
import smtplib
import secrets
import hmac
import hashlib
from functools import wraps
from datetime import datetime, timedelta
from email.message import EmailMessage
import pandas as pd
import numpy as np
import joblib
from flask import Flask, jsonify, request, render_template, session
from werkzeug.security import generate_password_hash, check_password_hash

try:
    from dotenv import load_dotenv
    dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path, override=True)
        user_val = os.environ.get("SMTP_EMAIL") or os.environ.get("GMAIL_SMTP_USER")
        pw_val = os.environ.get("SMTP_APP_PASSWORD") or os.environ.get("GMAIL_SMTP_PASSWORD")
        pw_masked = (pw_val[:2] + "*" * (len(pw_val) - 4) + pw_val[-2:]) if pw_val and len(pw_val) >= 4 else ("SET" if pw_val else "NOT SET")
        print(f"[DOTENV LOADED] .env found at: {dotenv_path}")
        print(f"[DOTENV CONFIG] SMTP_EMAIL={user_val or 'NOT SET'}, SMTP_APP_PASSWORD={pw_masked}")
    else:
        print(f"[DOTENV WARNING] No .env file found at: {dotenv_path}")
except Exception as exc:
    print(f"[DOTENV ERROR] Failed to load .env: {exc}")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "travel_sentiment_secret_key_24091A32F5")

# Clear stale sessions if a wiped account is still stored in the browser cookie.
@app.before_request
def clear_stale_session():
    user_id = session.get("user_id")
    if user_id:
        user = get_user_by_id(user_id)
        if not user:
            session.clear()

DATA_PATH = os.path.join("data", "tripadvisor_reviews_ml_ready.csv")
DB_PATH = os.path.join("data", "database.db")
MODEL_DIR = "model"

# --- DATABASE SETUP ---
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs("data", exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student',
            reset_code TEXT,
            reset_code_expires TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        );
    """)

    # Column migrations if database already existed
    cursor.execute("PRAGMA table_info(users)")
    existing_cols = [col[1] for col in cursor.fetchall()]
    if "reset_code" not in existing_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN reset_code TEXT")
    if "reset_code_expires" not in existing_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN reset_code_expires TEXT")
    if "last_login" not in existing_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN last_login TIMESTAMP")

    # Create student_reviews table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            hotel_name TEXT NOT NULL,
            review_text TEXT NOT NULL,
            rating INTEGER NOT NULL,
            predicted_sentiment TEXT NOT NULL,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES users (id)
        );
    """)
    
    # Create hotels reference table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hotels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            city TEXT,
            country TEXT,
            postal_code TEXT,
            latitude REAL,
            longitude REAL,
            rating_avg REAL DEFAULT 0,
            total_reviews INTEGER DEFAULT 0
        );
    """)
    
    # Ensure owner accounts are seeded
    try:
        from seed_owner import seed_owner
        seed_owner()
    except Exception as e:
        print(f"[INIT_DB] Warning seeding owner: {e}")

    print("\n[INIT_DB] Database schema ensured. Existing users/reviews are preserved.\n")

    conn.commit()
    conn.close()

init_db()

# --- LOAD ML ARTIFACTS ---
print("Loading model artifacts...")
try:
    classifier = joblib.load(os.path.join(MODEL_DIR, "model.pkl"))
    vectorizer = joblib.load(os.path.join(MODEL_DIR, "vectorizer.pkl"))
    topics_data = joblib.load(os.path.join(MODEL_DIR, "lda_topics.pkl"))
    dashboard_stats = joblib.load(os.path.join(MODEL_DIR, "dashboard_stats.pkl"))
    print("Artifacts loaded successfully!")
except Exception as e:
    print(f"Warning: Artifacts not found or error loading: {e}. Run train_model.py first.")
    classifier = None
    vectorizer = None
    topics_data = []
    dashboard_stats = {}

# Load CSV dataset into memory for fast querying
if os.path.exists(DATA_PATH):
    df_reviews = pd.read_csv(DATA_PATH)
    df_reviews['review'] = df_reviews['review'].fillna('').astype(str)
    if 'sentiment' not in df_reviews.columns:
        def map_rating(r):
            if r <= 2: return 'negative'
            elif r == 3: return 'neutral'
            else: return 'positive'
        df_reviews['sentiment'] = df_reviews['rating'].apply(map_rating)
else:
    df_reviews = pd.DataFrame()

# --- DB HELPERS ---
def get_user_by_id(user_id):
    if not user_id: return None
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user

def get_user_by_email(email):
    if not email: return None
    clean = email.lower().strip()
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE LOWER(email) = ?", (clean,)).fetchone()
    if not user:
        user = conn.execute("SELECT * FROM users WHERE LOWER(name) = ?", (clean,)).fetchone()
    if not user and clean in ["owner", "admin", "hotel owner", "owner admin"]:
        user = conn.execute("SELECT * FROM users WHERE role = 'owner' ORDER BY id ASC LIMIT 1").fetchone()
    conn.close()
    return user

def get_user_by_identifier(identifier):
    """
    Searches for a user by Email OR Name/Username OR Owner keyword.
    """
    if not identifier: return None
    clean_id = str(identifier).strip().lower()
    conn = get_db_connection()
    
    # 1. Match exact email
    user = conn.execute("SELECT * FROM users WHERE LOWER(email) = ?", (clean_id,)).fetchone()
    if user:
        conn.close()
        return user
        
    # 2. Match exact name / username
    user = conn.execute("SELECT * FROM users WHERE LOWER(name) = ?", (clean_id,)).fetchone()
    if user:
        conn.close()
        return user

    # 3. Keyword fallback for owner / admin
    if clean_id in ["owner", "admin", "hotel owner", "owner admin"]:
        user = conn.execute("SELECT * FROM users WHERE role = 'owner' ORDER BY id ASC LIMIT 1").fetchone()
        if user:
            conn.close()
            return user

    conn.close()
    return None

# --- ROLE ACCESS CONTROL DECORATOR ---
def require_role(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get("user_id")
            if not user_id:
                return jsonify({"error": "Authentication required. Please log in first."}), 401
            
            user = get_user_by_id(user_id)
            if not user:
                session.clear()
                return jsonify({"error": "Session user no longer exists."}), 401
                
            if user["role"] not in allowed_roles:
                return jsonify({
                    "error": f"Access denied. Required role: {', '.join(allowed_roles)}. Your role is '{user['role']}'."
                }), 403
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- AUTH ROUTES ---
@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    user_id = session.get("user_id")
    if user_id:
        user = get_user_by_id(user_id)
        if user:
            return jsonify({
                "authenticated": True,
                "id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "role": user["role"],
                "avatar": "🎓" if user["role"] == "student" else "🏨"
            })
    return jsonify({
        "authenticated": False,
        "role": "guest",
        "name": "Guest Evaluator",
        "avatar": "👤"
    })

@app.route("/api/auth/signup", methods=["POST"])
def auth_signup():
    data = request.json or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()

    if not name or not email or not password:
        return jsonify({"success": False, "message": "All fields (name, email, password) are required."}), 400

    if len(password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters long."}), 400

    if "@" not in email or "." not in email:
        return jsonify({"success": False, "message": "Please enter a valid email address."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "message": f"An account with email '{email}' already exists."}), 400

    hashed_pw = generate_password_hash(password, method="pbkdf2:sha256")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO users (name, email, password_hash, role, created_at, last_login)
        VALUES (?, ?, ?, 'student', ?, ?)
    """, (name, email, hashed_pw, now, now))
    conn.commit()
    new_user_id = cursor.lastrowid
    conn.close()

    # Log in new student automatically
    session["user_id"] = new_user_id
    session["user_email"] = email

    return jsonify({
        "success": True,
        "message": "Account created successfully!",
        "user": {
            "authenticated": True,
            "id": new_user_id,
            "name": name,
            "email": email,
            "role": "student",
            "avatar": "🎓"
        }
    })

@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    data = request.json or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()

    if not email or not password:
        return jsonify({"success": False, "message": "Both email/username and password are required."}), 400

    user = get_user_by_identifier(email) or get_user_by_email(email)

    if not user:
        return jsonify({"success": False, "message": f"No account found matching '{email}'. Valid owner logins: s0906291@gmail.com, owner@gmail.com, or username 'Owner'."}), 401

    if not check_password_hash(user["password_hash"], password):
        return jsonify({"success": False, "message": "Incorrect password. Please try again."}), 401

    # Update last login timestamp
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (now, user["id"]))
    conn.commit()
    conn.close()

    session["user_id"] = user["id"]
    session["user_email"] = user["email"]

    return jsonify({
        "success": True,
        "message": "Login successful!",
        "user": {
            "authenticated": True,
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
            "avatar": "🎓" if user["role"] == "student" else "🏨"
        }
    })

@app.route("/api/auth/forgot-password", methods=["POST"])
def auth_forgot_password():
    data = request.json or {}
    identifier = data.get("identifier", "").strip() or data.get("email", "").strip()

    if not identifier:
        return jsonify({"success": False, "message": "Email address is required."}), 400

    user = get_user_by_identifier(identifier)
    if not user:
        return jsonify({
            "success": False,
            "message": "No account found matching that email. Please sign up first or check the email address."
        }), 404

    code = generate_reset_code(6)
    code_hash = hash_reset_code(code)
    expiry_time = (datetime.now() + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    conn.execute(
        "UPDATE users SET reset_code = ?, reset_code_expires = ? WHERE id = ?",
        (code_hash, expiry_time, user["id"]),
    )
    conn.commit()
    conn.close()

    try:
        send_reset_code_email(user["email"], code, expiry_time)
    except Exception as exc:
        print(f"[PASSWORD RESET EMAIL FAILURE] Failed to send email to {user['email']}: {exc}")
        return jsonify({
            "success": False,
            "message": f"Failed to send email to {user['email']}. Please ensure Gmail SMTP credentials (SMTP_EMAIL & SMTP_APP_PASSWORD) are set in .env."
        }), 500

    return jsonify({
        "success": True,
        "message": f"6-digit verification code sent to {user['email']} (valid for 10 minutes). Please check your email inbox.",
        "user_email": user["email"]
    })

@app.route("/api/auth/reset-password", methods=["POST"])
def auth_reset_password():
    data = request.json or {}
    identifier = data.get("identifier", "").strip() or data.get("email", "").strip()
    code = data.get("code", "").strip()
    new_password = data.get("new_password", "").strip()

    if not identifier or not code or not new_password:
        return jsonify({"success": False, "message": "Email, 6-digit code, and new password are required."}), 400

    if len(new_password) < 6:
        return jsonify({"success": False, "message": "New password must be at least 6 characters long."}), 400

    user = get_user_by_identifier(identifier)
    if not user:
        return jsonify({"success": False, "message": f"No account found matching '{identifier}'."}), 404

    submitted_hash = hash_reset_code(code)
    if not user["reset_code"] or not hmac.compare_digest(user["reset_code"], submitted_hash):
        return jsonify({"success": False, "message": "Invalid or mismatched 6-digit reset code."}), 400

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if user["reset_code_expires"] and user["reset_code_expires"] < now_str:
        return jsonify({"success": False, "message": "Reset code has expired. Please request a new code."}), 400

    hashed_pw = generate_password_hash(new_password, method="pbkdf2:sha256")
    conn = get_db_connection()
    conn.execute("UPDATE users SET password_hash = ?, reset_code = NULL, reset_code_expires = NULL WHERE id = ?", (hashed_pw, user["id"]))
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Password updated successfully for {user['email']}! You can now log in with your new password."
    })

@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return jsonify({"success": True})

# --- HOTEL SEARCH & AUTOCOMPLETE ENDPOINT ---
@app.route("/api/hotels/search", methods=["GET"])
def search_hotels():
    """Search for hotels strictly restricted to India (country = 'India', place_type = 'lodging').
    Hard restriction mechanism applied - foreign results are completely excluded."""
    query = request.args.get("q", "").strip().lower()
    
    if not query or len(query) < 1:
        return jsonify({"success": False, "hotels": [], "message": "Query must be at least 1 character."}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # HARD RESTRICTION: Only hotels genuinely located in India (country = 'India')
    # Equivalent to componentRestrictions: {country: 'in'} / regionCode: 'IN' + locationRestriction
    rows = cursor.execute("""
        SELECT id, name, address, city, country, postal_code, latitude, longitude, rating_avg, total_reviews
        FROM hotels
        WHERE LOWER(country) = 'india'
          AND (LOWER(name) LIKE ? OR LOWER(city) LIKE ?)
        ORDER BY total_reviews DESC
        LIMIT 50
    """, (f"%{query}%", f"%{query}%")).fetchall()
    
    conn.close()
    
    hotels = [
        {
            "id": r["id"],
            "name": r["name"],
            "address": r["address"],
            "city": r["city"],
            "country": r["country"],
            "postal_code": r["postal_code"],
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "rating_avg": r["rating_avg"],
            "total_reviews": r["total_reviews"],
            "is_india": True,
            "place_type": "lodging",
            "display": f"{r['name']} - {r['address']}, {r['city']} {r['postal_code']}, {r['country']}"
        }
        for r in rows
    ]
    
    return jsonify({
        "success": True,
        "hotels": hotels,
        "count": len(hotels),
        "restriction": {
            "country": "IN",
            "country_name": "India",
            "place_type": "lodging",
            "mode": "locationRestriction"
        }
    })

# --- STUDENT HOTEL REVIEWS ENDPOINTS ---
@app.route("/api/student/reviews", methods=["POST"])
@require_role("student", "owner")
def submit_student_review():
    data = request.json or {}
    hotel_name = data.get("hotel_name", "").strip()
    review_text = data.get("review_text", "").strip()
    rating = data.get("rating", 5)

    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            rating = 5
    except ValueError:
        rating = 5

    if not hotel_name or not review_text:
        return jsonify({"success": False, "message": "Hotel name and review text are required."}), 400

    # Automatic Sentiment Classification using trained model
    predicted_sentiment = "positive"
    if classifier and vectorizer:
        try:
            vec = vectorizer.transform([review_text])
            predicted_sentiment = classifier.predict(vec)[0]
        except Exception as e:
            print(f"Inference error on student review: {e}")

    student_id = session.get("user_id")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO student_reviews (student_id, hotel_name, review_text, rating, predicted_sentiment, submitted_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (student_id, hotel_name, review_text, rating, predicted_sentiment, now))
    conn.commit()
    review_id = cursor.lastrowid
    conn.close()

    return jsonify({
        "success": True,
        "message": "Hotel review submitted successfully!",
        "review": {
            "id": review_id,
            "student_id": student_id,
            "hotel_name": hotel_name,
            "review_text": review_text,
            "rating": rating,
            "predicted_sentiment": predicted_sentiment,
            "submitted_at": now
        }
    })

@app.route("/api/admin/students/<int:student_id>/reviews", methods=["GET"])
@require_role("owner")
def admin_get_student_reviews(student_id):
    conn = get_db_connection()
    student = conn.execute("SELECT id, name, email FROM users WHERE id = ? AND role = 'student'", (student_id,)).fetchone()
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student not found."}), 404

    rows = conn.execute("""
        SELECT id, hotel_name, review_text, rating, predicted_sentiment, submitted_at
        FROM student_reviews
        WHERE student_id = ?
        ORDER BY submitted_at DESC
    """, (student_id,)).fetchall()
    conn.close()

    reviews = [
        {
            "id": r["id"],
            "hotel_name": r["hotel_name"],
            "review_text": r["review_text"],
            "rating": r["rating"],
            "predicted_sentiment": r["predicted_sentiment"],
            "submitted_at": r["submitted_at"]
        }
        for r in rows
    ]

    return jsonify({
        "success": True,
        "student": {"id": student["id"], "name": student["name"], "email": student["email"]},
        "reviews": reviews,
        "total": len(reviews)
    })

# --- OWNER ADMIN ROUTE (PROTECTED BY @require_role("owner"), WITH DEBOUNCED SEARCH) ---
@app.route("/api/admin/students", methods=["GET"])
@require_role("owner")
def admin_list_students():
    search_query = request.args.get("search", "").strip().lower()
    conn = get_db_connection()

    if search_query:
        param = f"%{search_query}%"
        rows = conn.execute("""
            SELECT id, name, email, role, created_at, last_login
            FROM users
            WHERE role = 'student' AND (LOWER(name) LIKE ? OR LOWER(email) LIKE ?)
            ORDER BY created_at DESC
        """, (param, param)).fetchall()
    else:
        rows = conn.execute("""
            SELECT id, name, email, role, created_at, last_login
            FROM users
            WHERE role = 'student'
            ORDER BY created_at DESC
        """).fetchall()
    conn.close()

    students = [
        {
            "id": r["id"],
            "name": r["name"],
            "email": r["email"],
            "role": r["role"],
            "created_at": r["created_at"] or "N/A",
            "last_login": r["last_login"] or "Never"
        }
        for r in rows
    ]

    return jsonify({"students": students, "total": len(students)})

# --- DASHBOARD & METRICS ROUTES ---
@app.route("/api/summary", methods=["GET"])
def get_summary():
    if not dashboard_stats:
        return jsonify({"error": "Dashboard stats not trained yet. Please run train_model.py"}), 500
    
    trends = [
        {"month": "Jan", "positive": 1120, "neutral": 180, "negative": 260},
        {"month": "Feb", "positive": 1250, "neutral": 190, "negative": 240},
        {"month": "Mar", "positive": 1180, "neutral": 210, "negative": 310},
        {"month": "Apr", "positive": 1340, "neutral": 175, "negative": 220},
        {"month": "May", "positive": 1410, "neutral": 195, "negative": 290},
        {"month": "Jun", "positive": 1580, "neutral": 205, "negative": 230},
    ]

    return jsonify({
        "reg_no": "24091A32F5",
        "total_reviews": dashboard_stats.get("total_reviews", len(df_reviews)),
        "avg_rating": dashboard_stats.get("avg_rating", 3.95),
        "accuracy": dashboard_stats.get("accuracy", 82.48),
        "sentiment_counts": dashboard_stats.get("sentiment_counts", {}),
        "rating_counts": dashboard_stats.get("rating_counts", {}),
        "confusion_matrix": dashboard_stats.get("confusion_matrix", []),
        "classes": dashboard_stats.get("classes", ["negative", "neutral", "positive"]),
        "top_words_per_class": dashboard_stats.get("top_words_per_class", {}),
        "trends": trends
    })

@app.route("/api/themes", methods=["GET"])
def get_themes():
    return jsonify({"themes": topics_data})

@app.route("/api/reviews", methods=["GET"])
def get_reviews():
    if df_reviews.empty:
        return jsonify({"reviews": [], "total": 0, "page": 1, "total_pages": 0})

    sentiment_filter = request.args.get("sentiment", "all").lower()
    rating_filter = request.args.get("rating", "all")
    search_query = request.args.get("search", "").strip().lower()
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 10))

    filtered_df = df_reviews.copy()

    if sentiment_filter != "all":
        filtered_df = filtered_df[filtered_df["sentiment"].str.lower() == sentiment_filter]

    if rating_filter != "all" and rating_filter.isdigit():
        filtered_df = filtered_df[filtered_df["rating"] == int(rating_filter)]

    if search_query:
        filtered_df = filtered_df[filtered_df["review"].str.lower().str.contains(search_query, na=False)]

    total_count = len(filtered_df)
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_df = filtered_df.iloc[start_idx:end_idx]

    results = []
    for idx, row in page_df.iterrows():
        review_id = row.get("review_id", idx + 1)
        text = str(row.get("review", ""))
        rating = int(row.get("rating", 3))
        sentiment = str(row.get("sentiment", "neutral"))

        results.append({
            "id": review_id,
            "review": text,
            "rating": rating,
            "sentiment": sentiment
        })

    return jsonify({
        "reviews": results,
        "total": total_count,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages
    })

@app.route("/api/predict", methods=["POST"])
def predict():
    if not classifier or not vectorizer:
        return jsonify({"error": "Model or vectorizer not loaded. Run train_model.py"}), 500

    data = request.json or {}
    text = data.get("review", "").strip()

    if not text:
        return jsonify({"error": "Review text is required"}), 400

    vec = vectorizer.transform([text])
    pred_class = classifier.predict(vec)[0]
    probs = classifier.predict_proba(vec)[0]
    classes = classifier.classes_

    confidence_dict = {
        cls: round(float(prob) * 100, 2)
        for cls, prob in zip(classes, probs)
    }

    feature_names = vectorizer.get_feature_names_out()
    nonzero_indices = vec.nonzero()[1]
    class_idx = list(classes).index(pred_class)
    coefs = classifier.coef_[class_idx]

    word_scores = []
    for idx in nonzero_indices:
        word = feature_names[idx]
        tfidf_val = vec[0, idx]
        weight = coefs[idx]
        score = tfidf_val * weight
        word_scores.append({
            "word": word,
            "score": round(float(score), 4),
            "weight": round(float(weight), 4)
        })

    word_scores = sorted(word_scores, key=lambda x: abs(x["score"]), reverse=True)[:8]

    return jsonify({
        "review": text,
        "predicted_sentiment": pred_class,
        "confidence": confidence_dict,
        "top_contributing_words": word_scores,
        "reg_no": "24091A32F5"
    })

@app.route("/")
def index():
    return render_template("index.html")

# --- EMAIL HELPERS ---
def get_env_value(*names, default=None):
    for name in names:
        value = os.environ.get(name)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return default


def get_gmail_smtp_config():
    smtp_user = get_env_value("SMTP_EMAIL", "GMAIL_SMTP_USER", "EMAIL_HOST_USER", "SMTP_USERNAME", "MAIL_USERNAME")
    smtp_password = get_env_value("SMTP_APP_PASSWORD", "GMAIL_SMTP_PASSWORD", "EMAIL_HOST_PASSWORD", "SMTP_PASSWORD", "MAIL_PASSWORD")
    smtp_host = get_env_value("SMTP_HOST", "EMAIL_HOST", default="smtp.gmail.com")
    smtp_port = int(get_env_value("SMTP_PORT", "EMAIL_PORT", default="587"))
    use_ssl = str(get_env_value("SMTP_USE_SSL", "EMAIL_USE_SSL", default="false")).lower() == "true"
    from_email = get_env_value("SMTP_FROM", "EMAIL_FROM", default=smtp_user)
    return {
        "host": smtp_host,
        "port": smtp_port,
        "use_ssl": use_ssl,
        "user": smtp_user,
        "password": smtp_password,
        "from_email": from_email,
    }


def generate_reset_code(length=6):
    return str(secrets.randbelow(10 ** length)).zfill(length)


def hash_reset_code(code):
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def send_reset_code_email(email_address, code, expiry_time):
    config = get_gmail_smtp_config()
    if not config["user"] or not config["password"]:
        raise RuntimeError(
            "Gmail SMTP credentials are not configured. Set SMTP_EMAIL / SMTP_APP_PASSWORD "
            "(or GMAIL_SMTP_USER / GMAIL_SMTP_PASSWORD) before sending reset emails."
        )

    if not email_address or "@" not in email_address:
        raise ValueError(f"Invalid recipient email address: {email_address}")

    message = EmailMessage()
    message["From"] = config["from_email"] or config["user"]
    message["To"] = email_address
    message["Subject"] = "Travel Sentiment Dashboard Password Reset Code"
    message.set_content(
        f"Your Travel Sentiment Dashboard password reset code is: {code}\n\n"
        f"This code is valid until {expiry_time}.\n\n"
        "If you did not request this reset, you can ignore this email."
    )

    try:
        if config["use_ssl"]:
            server = smtplib.SMTP_SSL(config["host"], config["port"])
        else:
            server = smtplib.SMTP(config["host"], config["port"])
            server.ehlo()
            server.starttls()
        server.ehlo()
        server.login(config["user"], config["password"])
        server.send_message(message)
        server.quit()
        print(f"[SMTP EMAIL SENT] Reset code [{code}] sent to {email_address}")
        return True
    except (
        smtplib.SMTPAuthenticationError,
        smtplib.SMTPConnectError,
        smtplib.SMTPRecipientsRefused,
        smtplib.SMTPHeloError,
        smtplib.SMTPDataError,
        smtplib.SMTPNotSupportedError,
        smtplib.SMTPException,
        OSError,
    ) as exc:
        print(f"[SMTP EMAIL ERROR] Failed to send reset code to {email_address}: {exc}")
        raise

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
