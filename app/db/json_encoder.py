# app/db/json_encoder.py
import json
from datetime import datetime, date, time
from decimal import Decimal

class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder for datetime objects"""
    def default(self, obj):
        if isinstance(obj, (datetime, date, time)):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        return super().default(obj)

def json_serializable(data):
    """Convert data to JSON serializable format"""
    if isinstance(data, dict):
        return {k: json_serializable(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [json_serializable(item) for item in data]
    elif isinstance(data, (datetime, date, time)):
        return data.isoformat()
    elif isinstance(data, Decimal):
        return float(data)
    elif hasattr(data, 'strftime'):
        return data.strftime('%Y-%m-%d %H:%M:%S')
    else:
        return data