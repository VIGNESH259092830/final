# app/db/qa_repo.py
from .connection import get_db
from datetime import datetime

def save_message(session_id, role, content):
    """Save a Q/A message to database"""
    db = get_db()
    cur = db.cursor()

    try:
        cur.execute("""
            INSERT INTO qa_messages (session_id, role, content)
            VALUES (?, ?, ?)
        """, (session_id, role, content))
        
        db.commit()
        print(f"💾 Saved message: session={session_id}, role={role}")
    except Exception as e:
        db.rollback()
        raise e
    finally:
        cur.close()
        db.close()


def get_recent_history(session_id, limit=6):
    """Get recent Q/A history for a session"""
    db = get_db()
    cur = db.cursor()

    try:
        cur.execute("""
            SELECT role, content, created_at
            FROM qa_messages
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (session_id, limit))

        rows = cur.fetchall()
        result = []
        
        for row in rows:
            row_dict = dict(row)
            if row_dict.get('created_at'):
                if isinstance(row_dict['created_at'], datetime):
                    row_dict['created_at'] = row_dict['created_at'].isoformat()
            result.append(row_dict)
        
        # Reverse to get chronological order
        return result[::-1]
    finally:
        cur.close()
        db.close()