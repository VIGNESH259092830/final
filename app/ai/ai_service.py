from openai import AzureOpenAI
import threading
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize Azure OpenAI client
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version="2024-02-15-preview"
)

DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")

def ask_ai(text, callback):
    """Asynchronous AI call"""
    if not text:
        callback("")
        return

    def run():
        try:
            resp = client.chat.completions.create(
                model=DEPLOYMENT,
                messages=[{"role": "user", "content": text}],
                temperature=0.3,
                max_tokens=1000,
            )
            callback(resp.choices[0].message.content)
        except Exception as e:
            callback(f"Error: {str(e)}")

    threading.Thread(target=run, daemon=True).start()

def ask_ai_sync(text):
    """Synchronous AI call for streaming"""
    if not text:
        return ""
    
    try:
        resp = client.chat.completions.create(
            model=DEPLOYMENT,
            messages=[{"role": "user", "content": text}],
            temperature=0.3,
            max_tokens=1000,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"