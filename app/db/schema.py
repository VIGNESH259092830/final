from dataclasses import dataclass
from datetime import datetime

@dataclass
class Session:
    id: int
    company: str
    job_description: str
    resume_text: str
    extra_context: str
    created_at: datetime

@dataclass
class QAMessage:
    id: int
    session_id: int
    role: str  # 'question' or 'answer'
    content: str
    created_at: datetime