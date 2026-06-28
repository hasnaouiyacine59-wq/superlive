import os
import random

import pymysql
from pymysql.cursors import DictCursor

DB_HOST = os.getenv("MYSQL_HOST", "sql8.freesqldatabase.com")
DB_PORT = int(os.getenv("MYSQL_PORT", "3306"))
DB_NAME = os.getenv("MYSQL_DB", "sql8831734")
DB_USER = os.getenv("MYSQL_USER", "sql8831734")
DB_PASS = os.getenv("MYSQL_PASS", "XiZe3TIWsF")


def random_username():
    adjectives = ["cool", "fast", "mega", "neo", "super", "ultra", "hyper", "epic", "omega", "alpha",
                  "dark", "shadow", "storm", "thunder", "blaze", "frost", "crystal", "phantom", "cyber", "nova"]
    nouns = ["wolf", "tiger", "eagle", "panda", "dragon", "hawk", "lion", "fox", "shark", "phoenix",
             "raider", "ninja", "pilot", "rider", "hunter", "knight", "ghost", "viper", "runner", "storm"]
    adj = random.choice(adjectives)
    noun = random.choice(nouns)
    num = random.randint(10, 9999)
    return f"{adj}{noun}{num}"


def get_connection():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        cursorclass=DictCursor,
        connect_timeout=10,
    )


def test_connection():
    print("=" * 60)
    print("  MySQL Connection Test")
    print("=" * 60)
    print(f"  Host:     {DB_HOST}:{DB_PORT}")
    print(f"  Database: {DB_NAME}")
    print(f"  User:     {DB_USER}")
    print()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT VERSION() AS version, DATABASE() AS db, @@port AS port")
            row = cur.fetchone()
            if not row:
                print("  [!] Query returned no data")
                return False
            print(f"  [+] Connected successfully")
            print(f"  [+] MySQL version: {row['version']}")
            print(f"  [+] Database:       {row['db']}")
            print(f"  [+] Port:           {row['port']}")
        return True
    finally:
        conn.close()


def create_accounts_table():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    status VARCHAR(50) DEFAULT 'active',
                    obs TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        with conn.cursor() as cur:
            for col, dtype in [("status", "VARCHAR(50) DEFAULT 'active'"), ("obs", "TEXT")]:
                try:
                    cur.execute(f"ALTER TABLE accounts ADD COLUMN {col} {dtype}")
                    conn.commit()
                    print(f"  [+] Added column '{col}'")
                except pymysql.err.OperationalError as e:
                    if e.args[0] == 1060:
                        pass
                    else:
                        raise
        print("  [+] accounts table ready")
        return True
    finally:
        conn.close()


def insert_test_account(username, email, password):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO accounts (username, email, password_hash, status, obs) VALUES (%s, %s, %s, %s, %s)",
                (username, email, password, "active", "test entry"),
            )
            conn.commit()
            print(f"  [+] Inserted: {username} <{email}>")
            return cur.lastrowid
    finally:
        conn.close()


def fetch_accounts():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, username, email, password_hash, status, obs, created_at FROM accounts ORDER BY created_at DESC")
            rows = cur.fetchall()
            return rows
    finally:
        conn.close()


def delete_account(row_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM accounts WHERE id = %s", (row_id,))
            conn.commit()
            print(f"  [+] Deleted row id={row_id}")
            return cur.rowcount > 0
    finally:
        conn.close()


def list_tables():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW TABLES")
            rows = cur.fetchall()
            key = list(rows[0].keys())[0] if rows else None
            names = [r[key] for r in rows] if key else []
            print(f"  [+] Tables ({len(names)}): {', '.join(names) if names else 'none'}")
            return names
    finally:
        conn.close()


def main():
    if not test_connection():
        print("  [!] Connection failed — aborting")
        return

    print()
    list_tables()
    print()
    create_accounts_table()

    print()
    username = random_username()
    email = f"{username}@test.local"
    password = username + "!Aa1"
    print(f"  Test credentials:")
    print(f"    username:     {username}")
    print(f"    email:        {email}")
    print(f"    password:     {password}")
    row_id = insert_test_account(username, email, password)

    print()
    rows = fetch_accounts()
    print(f"  Accounts in DB ({len(rows)}):")
    print(f"  {'ID':>4}  {'Username':<22}  {'Email':<36}  {'Status':<10}  {'Obs':<20}  {'Created':<20}")
    print(f"  {'-'*4}  {'-'*22}  {'-'*36}  {'-'*10}  {'-'*20}  {'-'*20}")
    for r in rows:
        print(f"  {r['id']:>4}  {r['username']:<22}  {r['email']:<36}  {r['status']:<10}  {(r['obs'] or ''):<20}  {r['created_at']}")

    print()
    delete_account(row_id)

    print()
    print("  [✓] All tests passed")


if __name__ == "__main__":
    main()
