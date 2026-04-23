# app/db/session_repo.py
from .connection import get_db
from datetime import datetime

def create_session(company, jd, resume, extra):
    """Create a new session and return the session ID"""
    db = get_db()
    cur = db.cursor()

    try:
        cur.execute("""
            INSERT INTO sessions (company, job_description, resume_text, extra_context)
            VALUES (%s, %s, %s, %s)
        """, (company, jd, resume, extra))

        session_id = cur.lastrowid
        db.commit()
        
        print(f"✅ Session created: ID={session_id}, Company={company}")
        return session_id
        
    except Exception as e:
        db.rollback()
        raise e
    finally:
        cur.close()
        db.close()


def get_session(session_id):
    """Get a session by ID"""
    db = get_db()
    cur = db.cursor(dictionary=True)

    try:
        cur.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
        row = cur.fetchone()
        
        # Convert datetime to string for JSON serialization
        if row and 'created_at' in row and row['created_at']:
            if isinstance(row['created_at'], datetime):
                row['created_at'] = row['created_at'].isoformat()
            elif hasattr(row['created_at'], 'strftime'):
                row['created_at'] = row['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                
        return row
    finally:
        cur.close()
        db.close()


def get_all_sessions():
    """Get all sessions ordered by date"""
    db = get_db()
    cur = db.cursor(dictionary=True)
    
    try:
        cur.execute("""
            SELECT id, company, job_description, created_at 
            FROM sessions 
            ORDER BY created_at DESC
        """)
        
        rows = cur.fetchall()
        
        # Convert datetime objects to strings for JSON serialization
        for row in rows:
            if 'created_at' in row and row['created_at']:
                if isinstance(row['created_at'], datetime):
                    row['created_at'] = row['created_at'].isoformat()
                elif hasattr(row['created_at'], 'strftime'):
                    row['created_at'] = row['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return rows
    finally:
        cur.close()
        db.close()


def delete_session(session_id):
    """Delete a session and its Q/A history"""
    db = get_db()
    cur = db.cursor()
    
    try:
        # Delete Q/A messages first (due to foreign key constraint)
        cur.execute("DELETE FROM qa_messages WHERE session_id = %s", (session_id,))
        # Then delete the session
        cur.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        raise e
    finally:
        cur.close()
        db.close()