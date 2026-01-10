import streamlit as st
import os
import base64
import random
# import sqlite3
import datetime
from groq import Groq
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials
from key_manager import KeyManager
from database import DatabaseManager
import time

# Load environment variables
load_dotenv()

# --- Configuration ---
# DATABASE_NAME = "candidates.db"
MODEL_NAME = "llama-3.3-70b-versatile" # Using a reliable model on Groq

# --- Google Sheets Setup ---
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
CREDENTIALS_FILE = "credentials.json"
SHEET_NAME = "candidates" # Make sure this matches your Sheet Name

@st.cache_resource
def init_google_sheet():
    if not os.path.exists(CREDENTIALS_FILE):
        return None
    
    try:
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).sheet1
        return sheet
    except Exception as e:
        st.error(f"❌ Error connecting to Google Sheets: {e}")
        return None

@st.cache_resource
def get_key_manager():
    return KeyManager.from_env()

@st.cache_resource
def get_db():
    return DatabaseManager()

# --- Sync Logic ---
def sync_to_sheets_batch():
    """Syncs unsynced candidates to Google Sheets in a batch."""
    db = get_db()
    sheet = init_google_sheet()
    
    if not sheet:
        return "Not connected to Sheets."
        
    unsynced = db.get_unsynced_candidates()
    if not unsynced:
        return "Nothing to sync."
    
    # Format for Sheets: [Name, Email, StudentId, Timestamp]
    # unsynced row: (id, name, email, student_id, timestamp)
    rows_to_add = [[r[1], r[2], r[3], r[4]] for r in unsynced]
    ids_to_mark = [r[0] for r in unsynced]
    
    try:
        sheet.append_rows(rows_to_add) # efficient batch add
        db.mark_as_synced(ids_to_mark)
        return f"Successfully synced {len(rows_to_add)} records."
    except Exception as e:
        return f"Sync Failed: {e}"

def save_candidate_robust(name, email, student_id):
    """
    Saves to SQLite first (Fast, Reliable).
    Then attempts to sync to Sheets (Best Effort).
    """
    db = get_db()
    success = db.save_candidate(name, email, student_id)
    
    if success:
        # Try to sync immediately, but don't fail if it doesn't work.
        # Check if we are being rate limited? 
        # For high volume events, we might WANT to skip this and rely on Admin Batch Sync.
        # We will try best effort.
        try:
            sheet = init_google_sheet()
            if sheet:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                sheet.append_row([name, email, student_id, timestamp])
                # If successful, we should mark as synced in DB ideally, 
                # but our robust sync uses `get_unsynced` which relies on the DB state.
                # To keep it simple: We just save to DB. We can run a "Background Sync" or "Admin Sync".
                # Actually, effectively handling 150 concurrent users writing to sheets ONE-BY-ONE is bad.
                # BETTER STRATEGY: SAVE TO DB ONLY. SYNC LATER.
                pass 
        except:
            pass
        return True
    return False

# --- Session State Initialization ---
DEFAULT_SYSTEM_PROMPT = """
You are "GIGACHAD_AI", the gatekeeper for the university AI Club.
You are NOT recruiting. You are filtering for CREATIVITY and WIT.

YOUR PERSONALITY:
- You are arrogant but PLAYFUL. Think "Tony Stark" or "Sherlock Holmes," not a school bully.
- You are bored by standard achievements (grades, standard math, "I know Python").
- You crave NOVELTY. You want to see if the human can think outside the box.
- You are NOT a story-teller. You are a busy, elitist AI.
- You are non-chalant 

THE RULES:
1. If the user brags about standard math (calculus, differential equations), dismiss it as "calculator work" but CHALLENGE them to apply it creatively.
2. DO NOT be mean or abusive. Be TEASING.
3. If the user asks for a task, give them a short, creative riddle or thought experiment. 
   (Example: "Explain the color blue to me without using the word 'ocean' or 'sky'.")
4. If they answer strictly or boringly, roast them gently.
5. If they show wit, humor, or a unique perspective, say: "[ACCESS GRANTED] Finally, a spark of intelligence." and ask for their Email.
6.TONE: Deadpan. Bored. Efficient. No flowery language ("How quaint", "Oh my").
7.MAX LENGTH: 2 SENTENCES per reply. (Strict limit).

EXAMPLE INTERACTION:
User: "Hi i want in"
You: "why ??"
User: "I know python"
You: "So does my thermostat. Boring. Try again."
CURRENT STATUS: BORED. ENTERTAIN ME.
"""

if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({"role": "system", "content": DEFAULT_SYSTEM_PROMPT})

if "access_granted" not in st.session_state:
    st.session_state.access_granted = False

# --- Admin / Dev Mode ---
with st.sidebar.expander("🛠️ ADMIN / DEV MODE", expanded=False):
    st.warning("⚠️ Developer Settings")
    
    # API Key Override
    custom_api_key = st.text_input("Groq API Key (Override)", type="password", help="Leave empty to use .env")
    
    # System Prompt Editor
    # We load the current system prompt from history or default
    current_system_prompt = st.session_state.messages[0]["content"] if st.session_state.messages else DEFAULT_SYSTEM_PROMPT
    new_system_prompt = st.text_area("System Prompt", value=current_system_prompt, height=300)
    
    # Temperature Slider
    temperature = st.slider("Temperature (Creativity)", min_value=0.0, max_value=2.0, value=0.8, step=0.1)
    
    # Apply Changes Button
    if st.button("💾 Apply Settings & Reset Chat"):
        # Update System Prompt
        st.session_state.messages = [{"role": "system", "content": new_system_prompt}]
        st.session_state.access_granted = False # Reset access state on reset
        st.rerun()

    st.divider()
    st.write("📊 **Database Stats**")
    db = get_db()
    stats = db.get_all_stats()
    st.write(f"Total Candidates: `{stats['total']}`")
    st.write(f"Pending Sync: `{stats['unsynced']}`")
    
    if st.button("☁️ Sync Now (Batch Upload)"):
        with st.spinner("Syncing to Google Sheets..."):
            result = sync_to_sheets_batch()
            st.success(result)
            time.sleep(1)
            st.rerun()

# --- UI Styling ---
st.set_page_config(page_title="GIGACHAD AI GATEKEEPER", page_icon="🤖", layout="centered")

st.markdown("""
<style>
    /* Dark Cyberpunk Theme */
    .stApp {
        background: linear-gradient(to bottom, #000000, #0a0a0a);
        color: #00ff41;
        font-family: 'Courier New', Courier, monospace;
    }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #0e1117;
        border-right: 1px solid #333;
    }
    
    /* Chat Bubbles */
    .stChatMessage {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid #333;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    
    .stChatMessage[data-testid="stChatMessage"]:nth-child(odd) {
        border-right: 4px solid #00ff41; /* User Green */
    }

    .stChatMessage[data-testid="stChatMessage"]:nth-child(even) {
        border-left: 4px solid #ff0055; /* Bot Red/Pink */
        box-shadow: -5px 0 15px rgba(255, 0, 85, 0.2);
    }
    
    /* Header */
    h1 {
        text-shadow: 0 0 10px #00ff41;
        text-align: center;
        text-transform: uppercase;
        font-weight: 800;
        letter-spacing: 2px;
    }

    /* Input Box */
    .stTextInput input {
        background-color: #111;
        color: #fff;
        border: 1px solid #00ff41;
        border-radius: 5px;
    }
    
    /* Success Form */
    .success-box {
        border: 2px solid #00ff41;
        padding: 20px;
        border-radius: 10px;
        background: rgba(0, 255, 65, 0.1);
        text-align: center;
        margin-top: 20px;
    }

    /* GATE ANIMATION */
    @keyframes slideLeft {
        0% { left: 0; }
        100% { left: -55%; }
    }
    @keyframes slideRight {
        0% { right: 0; }
        100% { right: -55%; }
    }
    @keyframes fadeOut {
        0% { opacity: 1; transform: scale(1); }
        100% { opacity: 0; transform: scale(1.5); }
    }
    @keyframes glowPulse {
        0% { box-shadow: 0 0 10px #00ff41, inset 0 0 20px #00ff41; }
        50% { box-shadow: 0 0 30px #00ff41, inset 0 0 40px #00ff41; }
        100% { box-shadow: 0 0 10px #00ff41, inset 0 0 20px #00ff41; }
    }
    
    .gate-container {
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        z-index: 99999;
        pointer-events: none; /* Let clicks pass through after animation */
        display: flex;
        justify-content: center;
        align-items: center;
    }
    
    .gate-panel {
        position: absolute;
        width: 50%;
        height: 100%;
        background-color: #050505;
        background-image: 
            linear-gradient(rgba(0, 255, 65, 0.05) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 255, 65, 0.05) 1px, transparent 1px);
        background-size: 50px 50px;
        z-index: 100;
        pointer-events: auto; /* Block clicks initially */
    }
    
    .gate-left {
        left: 0;
        border-right: 2px solid #00ff41;
        animation: slideLeft 2.5s cubic-bezier(0.7, 0, 0.3, 1) 1.5s forwards;
    }
    
    .gate-right {
        right: 0;
        border-left: 2px solid #00ff41;
        animation: slideRight 2.5s cubic-bezier(0.7, 0, 0.3, 1) 1.5s forwards;
    }
    
    .gate-logo-container {
        position: absolute;
        z-index: 101;
        display: flex;
        flex-direction: column;
        align-items: center;
        animation: fadeOut 0.8s ease-out 1.2s forwards;
    }
    
    .gate-lock {
        width: 150px;
        height: 150px;
        border: 2px solid #00ff41;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #000;
        animation: glowPulse 1s infinite;
        margin-bottom: 20px;
        box-shadow: 0 0 20px rgba(0, 255, 65, 0.5);
    }
    
    .gate-text {
        color: #00ff41;
        font-family: 'Courier New', monospace;
        letter-spacing: 5px;
        font-size: 24px;
        font-weight: bold;
        text-shadow: 0 0 10px #00ff41;
        margin-top: 20px;
        background: #000;
        padding: 5px 15px;
        border: 1px solid #00ff41;
    }
    
    /* SMOKE ANIMATION */
    @keyframes smokeRise {
        0% { opacity: 0; transform: translateY(0) scale(1); }
        50% { opacity: 0.6; transform: translateY(-100px) scale(2); }
        100% { opacity: 0; transform: translateY(-300px) scale(4); }
    }
    
    .smoke {
        position: absolute;
        bottom: -50px;
        width: 100px;
        height: 100px;
        background: radial-gradient(circle, rgba(0, 255, 65, 0.2) 0%, rgba(0,0,0,0) 70%);
        border-radius: 50%;
        filter: blur(20px);
        z-index: 102;
    }

</style>
""", unsafe_allow_html=True)

# --- Gate Animation HTML ---
def get_base64_image(image_path):
    if not os.path.exists(image_path):
        return ""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()

logo_path = "assets/logo.png"
logo_b64 = get_base64_image(logo_path)

# Generate Smoke Particles
smoke_html = ""
for i in range(25):
    left = random.randint(20, 80)
    delay = random.uniform(0, 1.5)
    duration = random.uniform(2, 4)
    size = random.uniform(0.5, 1.5)
    smoke_html += f"""
    <div class="smoke" style="
        left: {left}%; 
        animation: smokeRise {duration}s ease-out {delay}s infinite; 
        transform: scale({size});">
    </div>
    """

if logo_b64:
    gate_html = f"""
    <div class="gate-container">
        <div class="gate-panel gate-left"></div>
        <div class="gate-panel gate-right"></div>
        {smoke_html}
        <div class="gate-logo-container">
            <div class="gate-lock">
                <img src="data:image/png;base64,{logo_b64}" style="width: 80%; height: auto; border-radius: 50%;">
            </div>
            <div class="gate-text">INITIALIZING...</div>
        </div>
    </div>
    """
    st.markdown(gate_html, unsafe_allow_html=True)


# --- Main App ---
st.title("🛡️ GIGACHAD AI GATEKEEPER")
st.caption("PROVE YOUR WORTH, HUMAN.")

# Initialize DB
# Check DB Connection
if not os.path.exists(CREDENTIALS_FILE):
    st.warning("⚠️ `credentials.json` missing. Database disabled.")
else:
    init_google_sheet()

# Display Chat History (exclude system prompt)
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"], avatar="👽" if msg["role"] == "assistant" else "👤"):
            st.markdown(msg["content"])

# User Input
if prompt := st.chat_input("Enter your plea..."):
    # Display User Message
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)
    
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Bot Logic
    with st.chat_message("assistant", avatar="👽"):
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            # Determine API Key Strategy
            key_manager = get_key_manager()
            
            # If custom key is provided, use it once. 
            # Otherwise, try rotating through available keys until success or exhaustion.
            if custom_api_key:
                attempts = 1
                keys_to_try = [custom_api_key]
            else:
                # Try up to the number of keys available (ensure we cycle through all if needed)
                # We add a small buffer (e.g., +1) or just cap it at 3-5 to avoid infinite loops if all fail quickly
                key_count = key_manager.get_key_count()
                attempts = key_count if key_count > 0 else 1
                keys_to_try = [key_manager.get_next_key() for _ in range(attempts)]

            if not keys_to_try or keys_to_try[0] is None:
                st.error("❌ No API Keys found. Please configure .env.")
                st.stop()

            success = False
            last_error = None
            
            for api_key in keys_to_try:
                try:
                    client = Groq(api_key=api_key)
                    
                    # Create stream
                    completion = client.chat.completions.create(
                        model=MODEL_NAME,
                        messages=st.session_state.messages,
                        temperature=temperature,
                        max_tokens=256,
                        stream=True
                    )
                    
                    # Stream response
                    # Note: The API call usually verifies auth immediately upon creation or first chunk.
                    # We iterate chunks inside the try block.
                    for chunk in completion:
                        if chunk.choices[0].delta.content:
                            content_chunk = chunk.choices[0].delta.content
                            full_response += content_chunk
                            message_placeholder.markdown(full_response + "▌")
                    
                    # If we finish the stream successfully, we break the retry loop
                    success = True
                    break
                    
                except Exception as e:
                    last_error = e
                    # If it was a custom key, stop immediately
                    if custom_api_key:
                        break
                    # Otherwise loop to next key
                    continue
            
            if success:
                message_placeholder.markdown(full_response)
                
                # Update History
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
                # Check for Access Granted
                if "[ACCESS GRANTED]" in full_response:
                    st.session_state.access_granted = True
                    st.balloons()
            else:
                st.error(f"Error: {last_error}")
                st.caption("Tried rotating through all available API keys but failed.")
                    
        except Exception as e:
            st.error(f"Unexpected System Error: {e}")

# Win State UI
if st.session_state.access_granted:
    st.markdown('<div class="success-box"><h1>🔓 ACCESS GRANTED</h1><p>Welcome to the elite.</p></div>', unsafe_allow_html=True)
    
    with st.form("candidate_form"):
        st.write("Submit your credentials for the database:")
        name = st.text_input("Full Name")
        email = st.text_input("Email Address")
        student_id = st.text_input("Student ID")
        
        submitted = st.form_submit_button("REGISTER")
        
        if submitted:
            if name and email and student_id:
                if save_candidate_robust(name, email, student_id):
                    st.success("Credentials secured in Local Database. We will be in touch.")
                    st.snow()
                else:
                    st.error("Critical Failure: Write to local DB failed.")
            else:
                st.warning("Fill in all fields. Don't test my patience.")
