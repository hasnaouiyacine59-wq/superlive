-- init.sql

CREATE TABLE IF NOT EXISTS accounts (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL,
    email TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    obs TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
