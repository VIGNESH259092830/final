# app/db/connection.py
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

# Get database path from environment or use default
DB_PATH = os.getenv("DB_PATH", "interview_assistant.db")

def get_db():
    """Get a fresh database connection with proper cleanup"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # This allows dictionary-like access
    conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints
    return conn

def init_db():
    """Initialize database tables with proper cleanup"""
    try:
        db = get_db()
        cur = db.cursor()
        
        # Create sessions table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company VARCHAR(255),
            job_description TEXT,
            resume_text TEXT,
            extra_context TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create qa_messages table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS qa_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            role TEXT CHECK(role IN ('question', 'answer')),
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
        """)
        
        db.commit()
        cur.close()
        db.close()
        print("✅ SQLite tables initialized")
        
    except sqlite3.Error as err:
        print(f"❌ Database initialization error: {err}")
        raise err