import json
import os
import socket
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
import http.cookiejar

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = os.path.join(PROJECT_DIR, "venv", "bin", "python")
APP_PATH = os.path.join(PROJECT_DIR, "app.py")
DB_PATH = os.path.join(PROJECT_DIR, "data", "database.db")
BASE = "http://127.0.0.1:5001"

OWNER_EMAIL = "s0906291@gmail.com"
OWNER_PASSWORD = "Srivalli200670"


def make_client():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def post_json(opener, path, payload):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with opener.open(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"raw": body}


def get_json(opener, path):
    req = urllib.request.Request(BASE + path)
    try:
        with opener.open(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"raw": body}


def db_counts():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    users = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    reviews = cur.execute("SELECT COUNT(*) FROM student_reviews").fetchone()[0]
    con.close()
    return users, reviews


def wait_for_port(host, port, timeout=20):
    start = time.time()
    while time.time() - start < timeout:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        try:
            sock.connect((host, port))
            sock.close()
            return True
        except OSError:
            time.sleep(0.25)
        finally:
            sock.close()
    return False


def start_server():
    proc = subprocess.Popen(
        [PYTHON, APP_PATH],
        cwd=PROJECT_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if not wait_for_port("127.0.0.1", 5001, timeout=25):
        proc.terminate()
        raise RuntimeError("Server did not start on port 5001")
    return proc


def stop_server(proc):
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
    subprocess.run(["pkill", "-9", "-f", "app.py"], check=False)
    time.sleep(1)


def seed_owner_once():
    subprocess.run([PYTHON, os.path.join(PROJECT_DIR, "seed_owner.py")], cwd=PROJECT_DIR, check=True)


def main():
    seed_owner_once()

    p = start_server()
    try:
        before = db_counts()

        owner = make_client()
        s1, d1 = post_json(owner, "/api/auth/login", {"email": OWNER_EMAIL, "password": OWNER_PASSWORD})

        student = make_client()
        stamp = int(time.time())
        student_email = f"student_{stamp}@mail.com"
        s2, d2 = post_json(
            student,
            "/api/auth/signup",
            {"name": "Demo Student", "email": student_email, "password": "student123"},
        )
        student_id = d2.get("user", {}).get("id")

        s3, d3 = post_json(
            student,
            "/api/student/reviews",
            {"hotel_name": "Sunset Inn", "rating": 4, "review_text": "Great room and helpful staff"},
        )

        s4, _ = get_json(student, "/api/admin/students")
        s5, _ = get_json(student, f"/api/admin/students/{student_id}/reviews")

        s6, d6 = get_json(owner, "/api/admin/students")
        s7, d7 = get_json(owner, f"/api/admin/students/{student_id}/reviews")

        after_create = db_counts()
    finally:
        stop_server(p)

    p = start_server()
    try:
        after_restart_1 = db_counts()
    finally:
        stop_server(p)

    p = start_server()
    try:
        after_restart_2 = db_counts()
        owner2 = make_client()
        s8, d8 = post_json(owner2, "/api/auth/login", {"email": OWNER_EMAIL, "password": OWNER_PASSWORD})
        s9, d9 = get_json(owner2, "/api/admin/students")
        s10, d10 = get_json(owner2, f"/api/admin/students/{student_id}/reviews")
    finally:
        stop_server(p)

    print("OWNER_LOGIN", s1, d1.get("success"), d1.get("user", {}).get("role"))
    print("STUDENT_SIGNUP", s2, d2.get("success"), student_id)
    print("STUDENT_REVIEW_SUBMIT", s3, d3.get("success"))
    print("STUDENT_ADMIN_LIST_STATUS", s4)
    print("STUDENT_ADMIN_DETAIL_STATUS", s5)
    print("OWNER_ADMIN_LIST_STATUS", s6, "TOTAL", d6.get("total"))
    print("OWNER_ADMIN_DETAIL_STATUS", s7, "TOTAL_REVIEWS", d7.get("total"))

    print("COUNTS_BEFORE", before)
    print("COUNTS_AFTER_CREATE", after_create)
    print("COUNTS_AFTER_RESTART_1", after_restart_1)
    print("COUNTS_AFTER_RESTART_2", after_restart_2)
    print("PERSIST_RESTART_1", after_create == after_restart_1)
    print("PERSIST_RESTART_2", after_create == after_restart_2)

    print("OWNER_LOGIN_AFTER_RESTART_2", s8, d8.get("success"), d8.get("user", {}).get("role"))
    print("OWNER_ADMIN_LIST_AFTER_RESTART_2", s9, "TOTAL", d9.get("total"))
    print("OWNER_REVIEW_DETAIL_AFTER_RESTART_2", s10, "TOTAL_REVIEWS", d10.get("total"))


if __name__ == "__main__":
    main()
