# game/db.py
import sqlite3, json

conn = sqlite3.connect("monopoly.db")

def init_db():
    conn.execute("""
        CREATE TABLE IF NOT EXISTS games (
            chat_id TEXT PRIMARY KEY,
            state    TEXT NOT NULL
        )
    """)

def save_state(chat_id, state):
    conn.execute("""
        INSERT INTO games (chat_id, state) VALUES (?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET state = excluded.state
    """, (chat_id , json.dumps(state)))
    conn.commit()

def load_state(chat_id):
    row = conn.execute(
        "SELECT state FROM games WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    return json.loads(row[0]) if row else None

def delete_state(chat_id):
    conn.execute("DELETE FROM games WHERE chat_id = ?", (chat_id,))
    conn.commit()