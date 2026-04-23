import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

def get_db():
    """Get a fresh database connection with proper cleanup"""
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        autocommit=True,
        buffered=True  # Add this to prevent unread result issues
    )

def init_db():
    """Initialize database tables with proper cleanup"""
    try:
        db = get_db()
        cur = db.cursor()
        
        # Create sessions table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            company VARCHAR(255),
            job_description TEXT,
            resume_text LONGTEXT,
            extra_context TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create qa_messages table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS qa_messages (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            session_id BIGINT,
            role ENUM('question','answer'),
            content LONGTEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
        """)
        
        cur.close()
        db.close()
        print("✅ MySQL tables initialized")
        
    except mysql.connector.Error as err:
        print(f"❌ Database initialization error: {err}")
        raise err