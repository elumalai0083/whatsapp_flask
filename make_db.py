import sqlite3

conn = sqlite3.connect("chat.db")
c = conn.cursor()

# USERS
c.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT,
    name TEXT,
    password TEXT,
    image TEXT
)
""")

# PUBLIC CHAT
c.execute("""
CREATE TABLE IF NOT EXISTS messages(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    message TEXT,
    time TEXT
)
""")

# PRIVATE CHAT
c.execute("""
CREATE TABLE IF NOT EXISTS private_messages(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender TEXT,
    receiver TEXT,
    message TEXT,
    file TEXT,
    time TEXT,
    read INTEGER DEFAULT 0
)
""")

# FRIEND REQUESTS
c.execute("""
CREATE TABLE IF NOT EXISTS friend_requests(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender TEXT,
    receiver TEXT,
    status TEXT
)
""")

# ONLINE STATUS TABLE
c.execute("""
CREATE TABLE IF NOT EXISTS online_users(
    username TEXT PRIMARY KEY,
    last_seen TEXT
)
""")

conn.commit()
conn.close()

print("DATABASE READY!")
