import os

import pymysql
from pymysql.cursors import DictCursor

DB_HOST = os.getenv("MYSQL_HOST", "sql8.freesqldatabase.com")
DB_PORT = int(os.getenv("MYSQL_PORT", "3306"))
DB_NAME = os.getenv("MYSQL_DB", "sql8831734")
DB_USER = os.getenv("MYSQL_USER", "sql8831734")
DB_PASS = os.getenv("MYSQL_PASS", "XiZe3TIWsF")


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
                except pymysql.err.OperationalError as e:
                    if e.args[0] != 1060:
                        raise
        return True
    finally:
        conn.close()


def save_account(username, email, password, status="ready", obs=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO accounts (username, email, password_hash, status, obs) VALUES (%s, %s, %s, %s, %s)",
                (username, email, password, status, obs),
            )
            conn.commit()
            print(f"  [+] DB: saved {username} <{email}> (status={status})")
            return cur.lastrowid
    finally:
        conn.close()


def create_registred_table():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS registred (
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
                    cur.execute(f"ALTER TABLE registred ADD COLUMN {col} {dtype}")
                    conn.commit()
                except pymysql.err.OperationalError as e:
                    if e.args[0] != 1060:
                        raise
        return True
    finally:
        conn.close()


def save_registred(username, email, password, status="ready", obs=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO registred (username, email, password_hash, status, obs) VALUES (%s, %s, %s, %s, %s)",
                (username, email, password, status, obs),
            )
            conn.commit()
            print(f"  [+] DB: saved {username} <{email}> (status={status})")
            return cur.lastrowid
    finally:
        conn.close()
