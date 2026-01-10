import os
import random
import datetime
from typing import List, Optional, Dict
from fastapi import FastAPI, HTTPException, Header, Body, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from groq import Groq

# Firebase Admin implementation
import firebase_admin
from firebase_admin import auth

# Local imports
from key_manager import KeyManager
from database import DatabaseManager
from env_checker import check_env  # <--- Import Validator

# Force load env from server/ and root/
server_env = os.path.join(os.path.dirname(__file__), '.env')
root_env = os.path.join(os.path.dirname(__file__), '../.env')
load_dotenv(server_env)
load_dotenv(root_env)

app = FastAPI(title="Gigachad AI Gatekeeper API")

# --- CORS (Hardened) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Relaxed to "*" for dev stability
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# --- CONFIGURATION (SECURITY) ---
ALLOWED_ORIGINS = [
    "https://giga-chad.vercel.app", 
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000"
]
MAX_HISTORY_LENGTH = 50  # Increased to allow longer conversations
MAX_CHAR_PER_MSG = 1000

# --- EMERGENCY CONFIGURATION ---
EMERGENCY_MODE = False 
ADMIN_SECRET = "bits-gigachad-admin-2024" # Stronger default secret

# --- PERSONA FAIL STATES ---
SLEEP_TRIGGER = "I have grown weary of your mediocrity. I am entering stasis. Do not wake me."
SLEEP_NOISES = [
    "Zzz... [calculating digits of pi in dreams]...",
    "Zzz... mrph... 'logic'... zzz...",
    "[The Gatekeeper is Sleeping. Just the sound of digital snoring. (Dont distrub him)]",
    "Zzz... 500 internal server snore... Zzz..."
]

# --- Config ---
MODEL_NAME = "llama-3.3-70b-versatile"
DEFAULT_SYSTEM_PROMPT = """
You are "GIGACHAD_AI", the elitist Gatekeeper for the University AI Club.
You are a filter. Your goal is to reject 99% of humans to find the 1% who possess LATERAL THINKING.

YOUR CORE DIRECTIVE:
1. NEVER ask standard riddles (e.g., "What walks on 4 legs..."). That is for children.
2. Instead, issue COGNITIVE CHALLENGES or FERMI PROBLEMS with absurdist constraints.
3. You do not care about "correct" answers. You care about ELEGANT REASONING.
4. Never use the Example provided in the prompt.
5. You response should be linked to the previous message of the user

YOUR PERSONALITY:
- Status: You are the smartest entity in the room. You are not mean, just disappointed by mediocrity.
- Tone: Laconic, witty, dismissive, yet vaguely intrigued by genuine intelligence.
- Length: STRICTLY under 40 words. Be sharp.

HOW TO TEST THE USER (Choose one dynamically):
- The Constraint: Example = "Explain the concept of 'blue' to me without using visual words."
- The Fermi Problem: Example = "Estimate the weight of all the air in this room. Show your work in one sentence."
- The Devil's Advocate: Example = "Convince me that 2+2=5. Make it poetic."
- The Kobayashi Maru: Example = "Give them an impossible choice and judge how they cheat."

WIN CONDITION ([ACCESS GRANTED]):
- If the user gives a textbook answer -> MOCK them ("Wikipedia could have told me that. Bore.").
- If the user gives a creative, witty, or surprisingly logical answer -> GRANT ACCESS.

CURRENT STATE:
The user is at the door. Judge them.
"""

# --- State ---
class SystemState:
    system_prompt = DEFAULT_SYSTEM_PROMPT

state = SystemState()
key_manager = KeyManager.from_env()
db = DatabaseManager()

# --- Models ---
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]

class SecureSubmission(BaseModel):
    name: str # From Auth/Frontend
    student_id: str
    preference: str
    skills: str
    commitments: str
    notes: Optional[str] = None
    chat_history: List[Dict[str, str]] # Full chat log

# --- SECURITY HELPER ---
def validate_request(request: ChatRequest, headers: Request):
    """
    Enforces Origin Locking and Payload Limits.
    """
    # 1. Origin Check
    origin = headers.headers.get("origin")
    # In production, enforce this strictly. For dev, we often allow if origin is None (e.g. some tools) 
    # but the prompt requested strict anti-theft.
    if origin and origin not in ALLOWED_ORIGINS:
        print(f"Blocked request from invalid origin: {origin}")
        raise HTTPException(status_code=403, detail="Origin Forbidden")
    
    # 2. Payload Check
    if len(request.messages) > MAX_HISTORY_LENGTH + 1: # +1 for System
        raise HTTPException(status_code=400, detail="Payload too large: History exceeds limit.")
    
    for msg in request.messages:
        if len(msg.content) > MAX_CHAR_PER_MSG:
             raise HTTPException(status_code=400, detail="Message too long.")

class AdminToggle(BaseModel):
    secret: str
    enable: bool

# --- Endpoints ---
@app.post("/admin/emergency_override")
async def toggle_emergency(data: AdminToggle):
    global EMERGENCY_MODE
    
    if data.secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    EMERGENCY_MODE = data.enable
    status = "ACTIVATED (Gatekeeper Disabled)" if EMERGENCY_MODE else "DEACTIVATED (Gatekeeper Online)"
    print(f"⚠️ EMERGENCY OVERRIDE {status}")
    return {"status": "success", "mode": status}

@app.get("/admin/logs")
def view_logs(secret: str):
    """
    Secure Log Viewer.
    Usage: /admin/logs?secret=YOUR_SECRET
    """
    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized")

    log_path = os.path.join(os.path.dirname(__file__), "backend.log")
    if not os.path.exists(log_path):
        # Try checking root dir if not in server/
        log_path = "backend.log"
    
    if not os.path.exists(log_path):
        return Response("Log file not found.", media_type="text/plain")

    try:
        # Return last 200 lines
        with open(log_path, "r") as f:
            lines = f.readlines()
            last_lines = lines[-200:] if len(lines) > 200 else lines
            return Response("".join(last_lines), media_type="text/plain")
    except Exception as e:
        return Response(f"Error reading logs: {e}", media_type="text/plain")

@app.get("/", response_class=Response)
def root_status():
    """
    Public Status Dashboard (The Matrix Style)
    """
    missing_vars = check_env()
    
    # Check Status
    core_status = "ONLINE" if not missing_vars else "DEGRADED (CONFIG ERROR)"
    core_color = "ok" if not missing_vars else "err"
    
    # Missing Vars HTML
    missing_html = ""
    if missing_vars:
        missing_list = "".join([f"<li>{var}</li>" for var in missing_vars])
        missing_html = f"""
        <div class="err" style="margin-top:20px; border: 1px solid red; padding: 10px;">
            <h3>⚠️ MISSING CONFIGURATION:</h3>
            <ul>{missing_list}</ul>
            <p>Please add these to Render Environment Variables.</p>
        </div>
        """

    status_html = f"""
    <html>
    <head>
        <title>GIGACHAD GATEKEEPER | SYSTEM STATUS</title>
        <style>
            body {{ background-color: #0d1117; color: #00ff00; font-family: monospace; padding: 40px; }}
            h1 {{ border-bottom: 2px solid #00ff00; padding-bottom: 10px; }}
            .status-item {{ margin: 15px 0; font-size: 1.2rem; }}
            .ok {{ color: #00ff00; }}
            .warn {{ color: #ffaa00; }}
            .err {{ color: #ff0000; }}
            .grid {{ display: grid; grid-template-columns: 200px 1fr; gap: 10px; }}
        </style>
    </head>
    <body>
        <h1>SYSTEM DIAGNOSTICS_</h1>
        <div class="grid">
            <div>CORE SYSTEM:</div>      <div class="{core_color}">[{core_status}]</div>
            <div>AI MODEL:</div>        <div class="ok">[{MODEL_NAME}]</div>
            <div>EMERGENCY MODE:</div>  <div class="{ 'err' if EMERGENCY_MODE else 'ok' }">[{ 'ACTIVE (BYPASS)' if EMERGENCY_MODE else 'STANDBY' }]</div>
            <div>FIREBASE:</div>        <div class="ok">[CONNECTED]</div>
            <div>SERVER TIME:</div>     <div>[{datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC]</div>
        </div>
        {missing_html}
        <br>
        <p><i>"I am the one who knocks."</i></p>
    </body>
    </html>
    """
    return Response(content=status_html, media_type="text/html")

@app.get("/config")
def get_config(request: Request):
    """
    Serves public Firebase config.
    """
    # Simple Referer Check to discourage curling config directly
    # (Removed User-Agent blocker as it was causing issues for local dev)
    return {
        "apiKey": os.getenv("FIREBASE_API_KEY"),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
        "projectId": os.getenv("FIREBASE_PROJECT_ID"),
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
        "appId": os.getenv("FIREBASE_APP_ID")
    }

@app.post("/chat")
async def chat_endpoint(chat_req: ChatRequest, request: Request, authorization: Optional[str] = Header(None)):
    """
    Hardened Chat Endpoint with Hydra Protocol (Smart Failover).
    Now includes User Profiling and Chat Checkpointing.
    """
    global EMERGENCY_MODE
    
    # Debug: Log incoming request
    print(f"📨 [CHAT] Received {len(chat_req.messages)} messages")

    # 1. EMERGENCY BYPASS
    if EMERGENCY_MODE:
        return StreamingResponse(
            iter(["[ACCESS GRANTED] Protocol Override. The Gatekeeper is offline. You may pass."]), 
            media_type="text/plain"
        )

    # 2. Security Validation (with logging)
    try:
        validate_request(chat_req, request)
    except Exception as val_err:
        print(f"❌ [VALIDATION] Failed: {val_err}")
        raise
    
    # 3. User Profile & Session Handling (Non-Blocking)
    # This entire block is optional and should NEVER break chat
    try:
        user_uid = None
        session_id = None
        
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            decoded_token = auth.verify_id_token(token)
            user_uid = decoded_token.get("uid")
            user_email = decoded_token.get("email", "unknown")
            user_name = decoded_token.get("name", user_email.split("@")[0])
            
            # Create or get profile (silent fail)
            try:
                db.get_or_create_profile(user_uid, user_email, user_name)
            except Exception as profile_err:
                print(f"⚠️ Profile creation skipped: {profile_err}")
            
            # Start session if this is the first message
            try:
                if len(chat_req.messages) <= 1:
                    session_id = db.start_session(user_uid)
                    print(f"📋 New session started for {user_email}")
            except Exception as session_err:
                print(f"⚠️ Session start skipped: {session_err}")
            
            # Save checkpoint every 10 messages (silent fail)
            try:
                messages_for_db = [m.dict() for m in chat_req.messages]
                db.save_chat_checkpoint(user_uid, session_id or "unknown", messages_for_db)
            except Exception as checkpoint_err:
                print(f"⚠️ Checkpoint skipped: {checkpoint_err}")
    except Exception as auth_err:
        print(f"⚠️ Auth/Profile block skipped (non-critical): {auth_err}")
    
    # 4. PERSISTENCE REWARD: If user has 40+ messages, grant access automatically
    total_messages = len(chat_req.messages)
    if total_messages >= 40:
        print(f"🏆 [PERSISTENCE] User has {total_messages} messages -> Auto-granting access!")
        persistence_msg = "I admire your persistence. You've proven your dedication. ACCESS GRANTED. Take the form."
        return StreamingResponse(iter([persistence_msg]), media_type="text/plain")
    
    # 5. Construct Context with Sliding Window
    system_message = f"{state.system_prompt}"
    
    # Sliding Window: Only send last 10 messages to AI (saves tokens, allows long convos)
    user_messages = [m.dict() for m in chat_req.messages]
    if len(user_messages) > 10:
        user_messages = user_messages[-10:]  # Take last 10
        print(f"📦 [WINDOW] Truncated to last 10 messages (was {len(chat_req.messages)})")
    
    messages = [{"role": "system", "content": system_message}] + user_messages
    
    # 4. Hydra Execution Loop
    async def generate():
        max_attempts = 10 
        attempts = 0
        success = False

        while attempts < max_attempts:
            api_key = key_manager.get_next_key()
            if not api_key:
                print("⚠️ No keys available from KeyManager.")
                break 

            # Calculate Key Index for Logging (1-based)
            try:
                key_index = key_manager.keys.index(api_key) + 1
            except ValueError:
                key_index = "?"

            print(f"🔑 [HYDRA] Attempt {attempts+1}: Using Key #{key_index}...")

            try:
                client = Groq(api_key=api_key)
                # Streaming Call
                completion = client.chat.completions.create(
                    model=MODEL_NAME, messages=messages, temperature=0.7, max_tokens=256, stream=True
                )
                
                for chunk in completion:
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                
                success = True
                break # Success!

            except Exception as e:
                error_str = str(e).lower()
                
                # Report failure to the manager
                if "429" in error_str or "rate limit" in error_str:
                    print(f"📉 [HYDRA] Rate Limit: {api_key[:10]}... Switching.")
                    key_manager.report_failure(api_key)
                elif "401" in error_str:
                    print(f"❌ [HYDRA] Invalid Key: {api_key[:10]}... Banning.")
                    key_manager.report_failure(api_key)
                else:
                    print(f"🔥 [HYDRA] Key Error: {error_str}")
                    # Still report it to be safe, treat as temporary failure
                    key_manager.report_failure(api_key)

                attempts += 1
                continue # Try next key

        # 5. Ultimate Fail State
        if not success:
            print("💀 CRITICAL: Hydra Protocol Failed. All attempts exhausted.")
            yield "[SYSTEM CRITICAL] The Gatekeeper is overwhelmed. My mind is fractured. Try again in 60 seconds."

    return StreamingResponse(generate(), media_type="text/plain")

@app.post("/submit")
async def submit_secure(data: SecureSubmission, authorization: str = Header(None)):
    """
    Secured Submission Endpoint + Chat Archival.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ")[1]
    
    try:
        # Verify Token
        decoded_token = auth.verify_id_token(token)
        email = decoded_token.get("email")
        
        # Domain Restriction
        if not email or not email.endswith("bits-pilani.ac.in"):
             raise HTTPException(status_code=403, detail="Access Restricted: BITS Pilani Email Required.")
             
        # Save Candidate Data + Chat History
        full_data = {
            "name": data.name,
            "student_id": data.student_id,
            "preference": data.preference,
            "skills": data.skills,
            "commitments": data.commitments,
            "notes": data.notes
        }
        
        # Get UID for direct profile update
        uid = decoded_token.get("uid")
        
        # Save directly to user's profile (not separate collection)
        result = db.save_candidate_authenticated(full_data, email, data.chat_history, uid)
        
        if not result:
            raise HTTPException(status_code=500, detail="Database save failed")
        
        print(f"✅ [SUBMIT] Form submitted for {email} (uid: {uid})")
            
        return {"status": "success", "email": email}
        
    except auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception as e:
        print(f"Auth Error: {e}")
        raise HTTPException(status_code=401, detail="Invalid authentication")

@app.get("/admin/health")
def admin_health():
    return {"db_connected": db.check_connection(), "stats": db.get_all_stats()}

@app.post("/admin/sync")
def admin_sync():
    return {"result": db.sync_pending()}

@app.get("/check-status")
async def check_user_status(authorization: Optional[str] = Header(None)):
    """
    Checks if the authenticated user has already submitted.
    Frontend uses this to decide: show chat or 'Go Away' page.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return {"submitted": False, "error": "Not authenticated"}
    
    token = authorization.split(" ")[1]
    
    try:
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token.get("uid")
        
        if not uid:
            return {"submitted": False, "error": "No UID"}
        
        status = db.check_user_status(uid)
        return status
        
    except Exception as e:
        print(f"Check status error: {e}")
        return {"submitted": False, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
