# reset_db.py
import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv()

def reset_database():
    """Drop and recreate all tables"""
    try:
        # Connect to MySQL server
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT")),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )
        
        cursor = conn.cursor()
        
        print("🗑️ Dropping existing tables...")
        
        # Drop tables in correct order (due to foreign key constraints)
        cursor.execute("DROP TABLE IF EXISTS qa_messages")
        cursor.execute("DROP TABLE IF EXISTS sessions")
        
        # Create sessions table
        print("📋 Creating sessions table...")
        cursor.execute("""
        CREATE TABLE sessions (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            company VARCHAR(255) NOT NULL,
            job_description TEXT NOT NULL,
            resume_text LONGTEXT NOT NULL,
            extra_context TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        # Create qa_messages table
        print("📋 Creating qa_messages table...")
        cursor.execute("""
        CREATE TABLE qa_messages (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            session_id BIGINT NOT NULL,
            role ENUM('question','answer') NOT NULL,
            content LONGTEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Database reset successfully!")
        
    except mysql.connector.Error as err:
        print(f"❌ Database reset error: {err}")
        raise err

if __name__ == "__main__":
    reset_database()