import sqlite3
import os
from datetime import datetime

DB_FILE = "database/coin_data.db"

def init_bid_tracking():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS bid_tracker (
            user_id TEXT,
            month TEXT,
            bid_count INTEGER,
            PRIMARY KEY (user_id, month)
        )
    ''')
    conn.commit()
    conn.close()
def can_bid(user_id):
    from datetime import datetime
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    month = datetime.utcnow().strftime("%Y-%m")
    c.execute("SELECT bid_count FROM bid_tracker WHERE user_id = ? AND month = ?", (str(user_id), month))
    row = c.fetchone()
    conn.close()
    return (row[0] if row else 0) < 4

def increment_bid(user_id):
    from datetime import datetime
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    month = datetime.utcnow().strftime("%Y-%m")
    c.execute('''
        INSERT INTO bid_tracker (user_id, month, bid_count) VALUES (?, ?, 1)
        ON CONFLICT(user_id, month) DO UPDATE SET bid_count = bid_count + 1
    ''', (str(user_id), month))
    conn.commit()
    conn.close()




def init_db():
    os.makedirs("database", exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS SMILES (
            user_id TEXT PRIMARY KEY,
            balance INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()
    init_bid_tracking()

    
def get_balance(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT balance FROM SMILES WHERE user_id = ?", (str(user_id),))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def update_balance(user_id, new_balance):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO SMILES (user_id, balance) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET balance = ?",
        (str(user_id), new_balance, new_balance)
    )
    conn.commit()
    conn.close()

def change_balance(user_id, amount):
    """Add or subtract SMILES. Use negative amount to subtract."""
    current = get_balance(user_id)
    new_balance = current + amount
    update_balance(user_id, new_balance)
    return new_balance

def get_top_balances(limit):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id, balance FROM SMILES ORDER BY balance DESC LIMIT ?", (limit,))
    top_users = c.fetchall()
    conn.close()
    return top_users
