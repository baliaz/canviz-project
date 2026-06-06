import sqlite3

# Connect to the database (it will create the file if it doesn't exist)
conn = sqlite3.connect("history.db")
c = conn.cursor()

# Create table if it doesn't exist
c.execute("""
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    scan_id TEXT,
    date TEXT,
    result TEXT,
    confidence TEXT,
    status TEXT
)
""")

conn.commit()
conn.close()

print("Database and table created successfully!")
