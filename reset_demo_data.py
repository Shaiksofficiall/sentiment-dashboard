import os
import sqlite3

DB_PATH = os.path.join("data", "database.db")


def main():
    if not os.path.exists(DB_PATH):
        print(f"[RESET] Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM student_reviews")
    cursor.execute("DELETE FROM users")

    conn.commit()
    conn.close()

    print("[RESET] Deleted all users and student reviews.")


if __name__ == "__main__":
    main()
