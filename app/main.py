from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import sys
import os
import socket
import httpx
import asyncio

socket.setdefaulttimeout(10)

# ================= PATH FIX (MUST BE FIRST) =================
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(BASE_DIR)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
# ===========================================================

import threading
import time
import json
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk
from openai import AzureOpenAI
import html 

# Import modules
from app.audio.mic_stt import start_mic_stt, get_mic_status
from app.audio.system_stt import start_system_stt, get_system_status
from app.shared.state import state

# Import database modules
from app.db.connection import init_db
from app.db.session_repo import create_session, get_all_sessions, get_session, delete_session
from app.db.qa_repo import save_message, get_recent_history

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/web"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔥 ULTRA-FAST: Connection pooling with keep-alive
http_client = httpx.Client(
    timeout=10.0,  # Reduced timeout for speed
    limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
    headers={"Connection": "keep-alive"}
)

# 🔥 CRITICAL: Use GPT-3.5 Turbo for 1-2 second first token!
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version="2024-02-15-preview",
    http_client=http_client,
    timeout=10.0,
    max_retries=0  # No retries for speed
)

# 🔥 MUST be gpt-35-turbo for fast responses!
DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-35-turbo")

# Speech config
speech_config = speechsdk.SpeechConfig(
    subscription=os.getenv("AZURE_SPEECH_KEY"),
    region=os.getenv("AZURE_SPEECH_REGION"),
)
speech_config.speech_recognition_language = os.getenv("AZURE_SPEECH_LANGUAGE", "en-US")

# Initialize database
try:
    init_db()
    print("✅ Database initialized")
except Exception as e:
    print(f"⚠️ Database warning: {e}")

# Global session state
current_session_id = None
session_data = {
    'company': '',
    'job_description': '',
    'resume_text': '',
    'extra_context': ''
}

# Duplicate prevention
_last_processed_mic_text = ""
_last_processed_system_text = ""
_last_processed_time = 0
state.speech_config = speech_config

# ================= AUDIO CALLBACKS =================
def on_mic_text(text, is_final=True):
    if text and text.strip():
        text = text.strip()
        global _last_processed_mic_text, _last_processed_time
        current_time = time.time()
        
        if text == _last_processed_mic_text and (current_time - _last_processed_time) < 0.3:
            return
        
        _last_processed_mic_text = text
        _last_processed_time = current_time
        state.process_stt_text("mic", text, is_final)

def on_system_text(text, is_final=True):
    if text and text.strip():
        text = text.strip()
        global _last_processed_system_text, _last_processed_time
        current_time = time.time()
        
        if text == _last_processed_system_text and (current_time - _last_processed_time) < 0.3:
            return
        
        _last_processed_system_text = text
        _last_processed_time = current_time
        state.process_stt_text("system", text, is_final)

# ================= 🔥 ULTRA-FAST PROMPT CACHE =================
_prompt_cache = {
    'session_id': None,
    'company': '',
    'jd_summary': '',
    'resume_skills': [],
    'candidate_name': ''
}

def build_interview_prompt(session_data: dict, current_question: str, history: list = None) -> str:

    company = session_data.get('company', 'Unknown Company')
    resume_text = session_data.get('resume_text', '')

    question_type = detect_question_type(current_question)
    is_resume = is_resume_based_question(current_question)

    conversation_context = build_conversation_context(history)

    # 🔥 DEFAULT = NORMAL PROMPT
    if not is_resume:
        prompt = f"""
You are a Senior FAANG Software Engineer, Java Backend Architect, and Technical Interview Coach.

Detected Question Type: {question_type}

Interview Question:
"{current_question}"

Company:
{company}

Interview Context:
{conversation_context}

-----------------------------------------------------

Give a strong **concept-based answer**.

SECTION 1 — Direct Answer  
SECTION 2 — Explanation  
SECTION 3 — Example  
SECTION 4 — Java Code (if needed)  
SECTION 5 — SQL (if needed)  
SECTION 6 — Architecture Insight  

Rules:
- Simple English
- Bullet points
- No resume references
- No "In my project"

Start answer.
"""
        return prompt
    

    # 🔥 ONLY IF RESUME QUESTION → USE RESUME
    prompt = f"""
You are a Senior Java Developer answering an interview.

This is a RESUME-BASED question.

Interview Question:
"{current_question}"

Company:
{company}

-----------------------------------------------------

Candidate Resume:
{resume_text}

-----------------------------------------------------

INSTRUCTIONS:

- Answer MUST be based on real experience
- Use:
  "In my project..."
  "I worked on..."
  "I implemented..."
- Use Spring Boot, Microservices examples
- Do NOT give generic theory

-----------------------------------------------------

SECTION 1 — Direct Answer (Spoken)
SECTION 2 — What exactly you did
SECTION 3 — Tech stack used
SECTION 4 — Challenges faced
SECTION 5 — Outcome / result

Rules:
- Sound like real developer
- Confident tone
- Short & clear

Start answer.

"""
    return prompt



def detect_question_type(question: str) -> str:
    q = question.lower()

    coding_keywords = ["java program", "write a program", "factorial", "fibonacci",
                       "palindrome", "prime", "reverse string", "sorting", "algorithm"]

    system_keywords = ["design", "architecture", "scalable", "system design"]

    hr_keywords = ["tell me about yourself", "strength", "weakness", "challenge", "conflict"]

    for k in coding_keywords:
        if k in q:
            return "coding"

    for k in system_keywords:
        if k in q:
            return "system_design"

    for k in hr_keywords:
        if k in q:
            return "hr"

    return "concept"
def is_resume_based_question(question: str) -> bool:
    q = question.lower()

    resume_keywords = [
        "experience", "project", "worked on", "implemented",
        "your role", "responsibility", "what did you do",
        "how did you", "real time", "production",
        "current company", "previous company",
        "use case", "challenge you faced"
    ]

    return any(k in q for k in resume_keywords)

def build_conversation_context(history):
    if not history:
        return ""

    context = "Interview conversation so far:\n"

    for item in history[-5:]:
        role = "Interviewer" if item["role"] == "question" else "Candidate"
        text = item["content"][:150]
        context += f"{role}: {text}\n"

    return context
# ================= DATABASE ENDPOINTS =================
@app.post("/api/session/create")
async def create_new_session(request: Request):
    try:
        data = await request.json()
        
        company = data.get("company", "").strip()
        job_description = data.get("job_description", "").strip()
        resume_text = data.get("resume_text", "").strip()
        extra_context = data.get("extra_context", "").strip()
        
        if not company or not job_description or not resume_text:
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        global current_session_id, session_data
        current_session_id = create_session(company, job_description, resume_text, extra_context)
        
        session_data = {
            'company': company,
            'job_description': job_description,
            'resume_text': resume_text,
            'extra_context': extra_context
        }
        
        # Reset cache
        global _prompt_cache
        _prompt_cache['session_id'] = None
        
        return JSONResponse({"success": True, "session_id": current_session_id})
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/session/list")
async def list_sessions():
    try:
        sessions = get_all_sessions()
        return JSONResponse({"success": True, "sessions": sessions})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/session/{session_id}")
async def get_session_by_id(session_id: int):
    try:
        session = get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        history = get_recent_history(session_id, limit=20)
        
        return JSONResponse({"success": True, "session": session, "history": history})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/session/{session_id}")
async def delete_session_by_id(session_id: int):
    try:
        delete_session(session_id)
        return JSONResponse({"success": True})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/session/{session_id}/message")
async def add_session_message(session_id: int, request: Request):
    try:
        data = await request.json()
        role = data.get("role")
        content = data.get("content", "").strip()
        
        if role not in ['question', 'answer'] or not content:
            raise HTTPException(status_code=400, detail="Invalid role or content")
        
        save_message(session_id, role, content)
        
        return JSONResponse({"success": True})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ================= FIXED SSE STREAM - SENDS AI STATUS =================
@app.get("/stream")
def stream():
    def gen():
        last_sent_line = ""
        last_partial = ""
        last_sent_time = 0
        last_ai_status = False
        
        while True:
            try:
                state.update_event.wait(timeout=0.005)
                state.update_event.clear()
                
                text_data = state.get_text_for_sse()
                
                current_line = text_data["current_line"]
                partial_buffer = text_data["partial_buffer"]
                last_source = text_data["last_source"]
                has_partial = text_data["has_partial"]
                timestamp = text_data["timestamp"]
                is_ai_responding = text_data.get("is_ai_responding", False)  # 🔥 Get AI status
                
                current_time = time.time()
                
                # 🔥 Send AI status updates
                if is_ai_responding != last_ai_status:
                    data = {
                        'type': 'ai_status',  # Special type for status
                        'is_responding': is_ai_responding,
                        'timestamp': timestamp
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                    last_ai_status = is_ai_responding
                
                # If AI is responding, still send transcript updates but with special flag
                if is_ai_responding:
                    # Still send but with ai_responding flag
                    if current_line and current_line != last_sent_line:
                        if current_time - last_sent_time > 0.05:
                            data = {
                                'type': 'transcript', 
                                'text': current_line, 
                                'source': last_source or "unknown",
                                'is_final': True,
                                'ai_responding': True,  # 🔥 Flag for frontend
                                'timestamp': timestamp
                            }
                            yield f"data: {json.dumps(data)}\n\n"
                            last_sent_line = current_line
                            last_partial = ""
                            last_sent_time = current_time
                else:
                    # Normal transcript updates when AI not responding
                    if current_line and current_line != last_sent_line:
                        if current_time - last_sent_time > 0.05:
                            data = {
                                'type': 'transcript', 
                                'text': current_line, 
                                'source': last_source or "unknown",
                                'is_final': True,
                                'timestamp': timestamp
                            }
                            yield f"data: {json.dumps(data)}\n\n"
                            last_sent_line = current_line
                            last_partial = ""
                            last_sent_time = current_time
                    
                    elif has_partial and partial_buffer and partial_buffer != last_partial:
                        if current_time - last_sent_time > 0.03:
                            data = {
                                'type': 'transcript', 
                                'text': partial_buffer, 
                                'source': last_source or "unknown",
                                'is_final': False,
                                'is_partial': True,
                                'timestamp': timestamp
                            }
                            yield f"data: {json.dumps(data)}\n\n"
                            last_partial = partial_buffer
                            last_sent_time = current_time
                
                time.sleep(0.001)
                
            except Exception as e:
                print(f"⚠️ SSE error: {e}")
                time.sleep(0.01)
    
    return StreamingResponse(gen(), media_type="text/event-stream")

def format_ai_response_bullets(response_text):
    """Format AI response with bullet points and code blocks"""
    response_text = response_text.strip()
    if not response_text:
        return ""
    
    lines = response_text.split('\n')
    formatted_lines = []
    in_code_block = False
    current_code_block = []
    code_language = ""
    
    for line in lines:
        if line.strip().startswith('```'):
            if not in_code_block:
                in_code_block = True
                lang_part = line.strip()[3:].strip()
                code_language = lang_part if lang_part else 'text'
            else:
                in_code_block = False
                code_content = '\n'.join(current_code_block).strip()
                code_html = f'''
                <div class="chatgpt-code-block">
                    <div class="code-header">
                        <span class="code-language">{code_language}</span>
                        <button class="copy-button">Copy code</button>
                    </div>
                    <pre><code class="language-{code_language}">{html.escape(code_content)}</code></pre>
                </div>
                '''
                formatted_lines.append(code_html)
                current_code_block = []
                code_language = ""
            continue
        
        if in_code_block:
            current_code_block.append(line)
        else:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith(('-', '•', '*', '1.', '2.', '3.', '4.', '5.')):
                clean_line = line.lstrip('-•* 1234567890.').strip()
                if clean_line:
                    formatted_lines.append(f'<div class="bullet-item">• {html.escape(clean_line)}</div>')
            else:
                if '`' in line:
                    parts = line.split('`')
                    if len(parts) >= 3:
                        line = parts[0] + '<code class="inline-code">' + html.escape(parts[1]) + '</code>' + parts[2]
                
                if line and len(line) > 1:
                    formatted_lines.append(f'<div class="text-paragraph">{html.escape(line)}</div>')
    
    result = ""
    in_bullet_list = False
    
    for line in formatted_lines:
        if 'bullet-item' in line:
            if not in_bullet_list:
                result += '<div class="bullet-list">'
                in_bullet_list = True
            result += line
        else:
            if in_bullet_list:
                result += '</div>'
                in_bullet_list = False
            result += line
    
    if in_bullet_list:
        result += '</div>'
    
    if not result:
        result = f'<div class="text-paragraph">{html.escape(response_text)}</div>'
    
    return result


# ================= 🔥 ULTRA-FAST ANSWER ENDPOINT - OPTIMIZED HEADERS =================
@app.post("/api/answer-stream-fast")
async def answer_with_context_stream_fast(request: Request):
    """
    ULTRA-FAST AI streaming - First token in 1-2 seconds with GPT-3.5 Turbo!
    """
    try:
        body = await request.json()
        question = body.get("text", "").strip()

        if not question:
            return JSONResponse({"success": False, "error": "Empty question"})

        print(f"🚀 Question: '{question}' (using {DEPLOYMENT})")

        # Get history
        history = []
        if current_session_id:
            history = get_recent_history(current_session_id, limit=5)
            save_message(current_session_id, "question", question)

        # Build prompt with YOUR exact format
        prompt = build_interview_prompt(session_data, question, history)

        # Reset state
        state.reset_for_answer_button(question)

        async def generate():
            try:
                start_time = time.time()
                
                # 🔥 STEP 1: Fake token IMMEDIATELY (0ms) - UI unfreezes
                yield f"data: {json.dumps({'type':'ai_stream','content':'Thinking...'})}\n\n"
                await asyncio.sleep(0.05)

                yield f"data: {json.dumps({'type':'ai_stream','content':'Analyzing question...'})}\n\n"
                await asyncio.sleep(0.05)

                yield f"data: {json.dumps({'type':'ai_stream','content':'Preparing answer...'})}\n\n"
                print(f"⚡ Fake token: {time.time()-start_time:.3f}s")
                
                first_token_sent = False
                full_response = ""

                # 🔥 STEP 2: Call GPT-3.5 Turbo with timeout
                try:
                    # Use asyncio timeout
                    stream = await asyncio.wait_for(
                        asyncio.to_thread(
                            client.chat.completions.create,
                            model=DEPLOYMENT,
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.2,
                            max_tokens=650,
                            stream=True
                        ),
                        timeout=5.0
                    )

                    # 🔥 STEP 3: Stream tokens immediately with minimal delay
                    token_count = 0
                    for chunk in stream:
                        if not chunk.choices:
                            continue

                        delta = chunk.choices[0].delta
                        if not delta or not delta.content:
                            continue

                        token = delta.content
                        full_response += token
                        token_count += 1

                        if not first_token_sent:
                            elapsed = time.time() - start_time
                            print(f"⚡ FIRST REAL TOKEN: {elapsed:.2f}s {'✅' if elapsed <= 2 else '❌'}")
                            first_token_sent = True

                        # Send each token immediately
                        yield f"data: {json.dumps({'type': 'ai_stream', 'content': token})}\n\n"
                        
                        # 🔥 Small delay for first few tokens to ensure browser renders
                        if token_count < 5:
                            await asyncio.sleep(0.002)
                        else:
                            await asyncio.sleep(0)

                except asyncio.TimeoutError:
                    print("⚠️ Timeout - sending fallback")
                    fallback = "I'm thinking about your question... One moment please."
                    yield f"data: {json.dumps({'type': 'ai_stream', 'content': fallback})}\n\n"
                    full_response = fallback

                total_time = time.time() - start_time
                print(f"✅ Complete: {total_time:.2f}s")

                # Save answer
                if current_session_id and full_response and "thinking" not in full_response:
                    save_message(current_session_id, "answer", full_response)

                # Format and send complete
                final_html = format_ai_response_bullets(full_response) if full_response else ""
                yield f"data: {json.dumps({'type': 'ai_complete', 'content': final_html})}\n\n"

                state.complete_ai_response(full_response)

            except Exception as e:
                print(f"❌ ERROR: {e}")
                state.is_ai_responding = False
                yield f"data: {json.dumps({'type': 'ai_error', 'error': str(e)})}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate, private",
                "Pragma": "no-cache",
                "Expires": "0",
                "X-Accel-Buffering": "no",
                "Transfer-Encoding": "chunked",
                "Content-Type": "text/event-stream; charset=utf-8",
                "Connection": "keep-alive"
            }
        )

    except Exception as e:
        print(f"❌ POST ERROR: {e}")
        return JSONResponse({"success": False, "error": str(e)})
# ================= OTHER ENDPOINTS =================
@app.post("/api/clear-and-reset")
async def clear_and_reset():
    state.reset_for_clear_button()
    return JSONResponse({"success": True})

@app.post("/api/chat-question")
async def chat_question(request: Request):
    try:
        body = await request.json()
        question = body.get("text", "").strip()
        
        if not question:
            return JSONResponse({"error": "Empty question", "success": False})
        
        state.reset_for_clear_button()
        state.process_stt_text("chat", question, is_final=True)
        
        return JSONResponse({"success": True})
        
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})

def start_audio_services():
    try:
        start_system_stt(speech_config, on_system_text)
        start_mic_stt(on_mic_text)
        print("✅ Audio services started")
    except Exception as e:
        print(f"❌ Audio error: {e}")
        threading.Timer(3.0, start_audio_services).start()

@app.get("/", response_class=HTMLResponse)
def landing_page():
    with open("app/web/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/download")
def download_exe():
    exe_path = os.path.join(BASE_DIR, "downloads", "InterviewHelperSetup.exe")
    return FileResponse(path=exe_path, filename="InterviewHelperSetup.exe")

@app.post("/toggle-mic")
async def toggle_mic():
    with state.lock:
        new_state = not state.mute_mic
        state.set_mute_state("mic", new_state)
    return JSONResponse({"muted": state.mute_mic})

@app.post("/toggle-system")
async def toggle_system():
    with state.lock:
        new_state = not state.mute_system
        state.set_mute_state("system", new_state)
    return JSONResponse({"muted": state.mute_system})

@app.get("/health")
def health_check():
    return JSONResponse({"status": "healthy", "model": DEPLOYMENT})

# ================= STARTUP =================
@app.on_event("startup")
def startup():
    try:
        print(f"🔥 Warming {DEPLOYMENT} for ultra-fast responses...")
        # Warm up the model
        stream = client.chat.completions.create(
            model=DEPLOYMENT,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
            stream=True
        )
        for _ in stream:
            break
        print(f"✅ {DEPLOYMENT} ready - First token in 1-2 seconds expected!")
    except Exception as e:
        print(f"⚠️ Warm-up failed: {e}")

    threading.Thread(target=start_audio_services, daemon=True).start()

@app.get("/api/test-stream")
async def test_stream():
    """Test endpoint to verify streaming works"""
    async def generate():
        words = ["This", "is", "a", "test", "of", "streaming", "responses."]
        for word in words:
            yield f"data: {json.dumps({'type': 'ai_stream', 'content': word + ' '})}\n\n"
            await asyncio.sleep(0.1)
        yield f"data: {json.dumps({'type': 'ai_complete', 'content': 'Test complete!'})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )

# ================= MAIN =================
if __name__ == "__main__":
    import multiprocessing
    import uvicorn

    multiprocessing.freeze_support()

    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=8000,
        log_level="info",
        loop="asyncio"
    )

    server = uvicorn.Server(config)
    server.run()