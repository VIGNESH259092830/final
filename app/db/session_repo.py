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
            VALUES (?, ?, ?, ?)
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
    cur = db.cursor()

    try:
        cur.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = cur.fetchone()
        
        if row:
            # Convert row to dict
            row_dict = dict(row)
            # Convert datetime to string for JSON serialization
            if row_dict.get('created_at'):
                if isinstance(row_dict['created_at'], datetime):
                    row_dict['created_at'] = row_dict['created_at'].isoformat()
            return row_dict
        return None
    finally:
        cur.close()
        db.close()


def get_all_sessions():
    """Get all sessions with message counts, ordered by date"""
    db = get_db()
    cur = db.cursor()

    try:
        cur.execute("""
            SELECT 
                s.id,
                s.company,
                s.job_description,
                s.created_at,
                COUNT(qa.id) AS message_count
            FROM sessions s
            LEFT JOIN qa_messages qa ON qa.session_id = s.id
            GROUP BY s.id
            ORDER BY s.created_at DESC
        """)

        rows = cur.fetchall()
        result = []
        for row in rows:
            row_dict = dict(row)
            if row_dict.get('created_at'):
                if isinstance(row_dict['created_at'], datetime):
                    row_dict['created_at'] = row_dict['created_at'].isoformat()
            result.append(row_dict)
        return result
    finally:
        cur.close()
        db.close()
def delete_session(session_id):
    """Delete a session and its Q/A history"""
    db = get_db()
    cur = db.cursor()
    
    try:
        # SQLite will handle cascade delete automatically
        cur.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        raise e
    finally:
        cur.close()
        db.close()