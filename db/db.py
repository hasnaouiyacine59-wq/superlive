import os
import psycopg2
from psycopg2.extras import execute_values

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "creds")
DB_USER = os.getenv("DB_USER", "user")
DB_PASS = os.getenv("DB_PASS", "password")

def get_connection():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASS
    )

def insert_account(username: str, email: str, password: str):
    sql = "INSERT INTO accounts (username, email, password_hash) VALUES (%s, %s, %s)"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (username, email, password))
            conn.commit()

def insert_multiple(accounts: list):
    sql = "INSERT INTO accounts (username, email, password_hash) VALUES %s"
    with get_connection() as conn:
        with conn.cursor() as cur:
            execute_values(cur, sql, accounts)
            conn.commit()