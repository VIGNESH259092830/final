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
            VALUES (%s, %s, %s)
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
    cur = db.cursor(dictionary=True)

    try:
        cur.execute("""
            SELECT role, content, created_at
            FROM qa_messages
            WHERE session_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (session_id, limit))

        rows = cur.fetchall()
        
        # Convert datetime objects to strings
        for row in rows:
            if 'created_at' in row and row['created_at']:
                if isinstance(row['created_at'], datetime):
                    row['created_at'] = row['created_at'].isoformat()
                elif hasattr(row['created_at'], 'strftime'):
                    row['created_at'] = row['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        # Reverse to get chronological order
        return rows[::-1]
    finally:
        cur.close()
        db.close()