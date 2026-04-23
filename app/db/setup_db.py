# setup_db.py
import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv()

def setup_database():
    """Create database and tables"""
    try:
        # Connect to MySQL server
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT")),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
        
        cursor = conn.cursor()
        
        # Create database if not exists
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {os.getenv('DB_NAME')}")
        print(f"✅ Database '{os.getenv('DB_NAME')}' created or already exists")
        
        # Switch to database
        cursor.execute(f"USE {os.getenv('DB_NAME')}")
        
        # Create sessions table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            company VARCHAR(255) NOT NULL,
            job_description TEXT NOT NULL,
            resume_text LONGTEXT NOT NULL,
            extra_context TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_company (company),
            INDEX idx_created_at (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        # Create qa_messages table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS qa_messages (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            session_id BIGINT NOT NULL,
            role ENUM('question','answer') NOT NULL,
            content LONGTEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
            INDEX idx_session_id (session_id),
            INDEX idx_created_at (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        cursor.close()
        conn.close()
        
        print("✅ Tables created successfully")
        
    except mysql.connector.Error as err:
        print(f"❌ Database setup error: {err}")
        raise err

if __name__ == "__main__":
    setup_database()