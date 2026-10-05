# reset_db.py
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "interview_assistant.db")

def reset_database():
    """Drop and recreate all tables"""
    try:
        # Connect to SQLite database
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        
        print("🗑️ Dropping existing tables...")
        
        # Drop tables (SQLite handles foreign key constraints with PRAGMA)
        cursor.execute("DROP TABLE IF EXISTS qa_messages")
        cursor.execute("DROP TABLE IF EXISTS sessions")
        
        # Create sessions table
        print("📋 Creating sessions table...")
        cursor.execute("""
        CREATE TABLE sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company VARCHAR(255) NOT NULL,
            job_description TEXT NOT NULL,
            resume_text TEXT NOT NULL,
            extra_context TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create qa_messages table
        print("📋 Creating qa_messages table...")
        cursor.execute("""
        CREATE TABLE qa_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT CHECK(role IN ('question', 'answer')) NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Database reset successfully!")
        
    except sqlite3.Error as err:
        print(f"❌ Database reset error: {err}")
        raise err

if __name__ == "__main__":
    reset_database()