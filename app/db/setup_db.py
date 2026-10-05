# setup_db.py
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "interview_assistant.db")

def setup_database():
    """Create database and tables"""
    try:
        # Connect to SQLite database (creates file if not exists)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print(f"✅ Database created at: {DB_PATH}")
        
        # Create sessions table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company VARCHAR(255) NOT NULL,
            job_description TEXT NOT NULL,
            resume_text TEXT NOT NULL,
            extra_context TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create indexes for sessions
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_company ON sessions(company)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON sessions(created_at)")
        
        # Create qa_messages table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS qa_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT CHECK(role IN ('question', 'answer')) NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
        """)
        
        # Create indexes for qa_messages
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON qa_messages(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_qa_created_at ON qa_messages(created_at)")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Tables created successfully")
        
    except sqlite3.Error as err:
        print(f"❌ Database setup error: {err}")
        raise err

if __name__ == "__main__":
    setup_database()