import streamlit as st
import os
import sqlite3
import datetime
from groq import Groq
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Configuration ---
DATABASE_NAME = "candidates.db"
MODEL_NAME = "llama-3.3-70b-versatile" # Using a reliable model on Groq

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            student_id TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_candidate(name, email, student_id):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute('INSERT INTO candidates (name, email, student_id) VALUES (?, ?, ?)', 
              (name, email, student_id))
    conn.commit()
    conn.close()

# --- Session State Initialization ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    # Add System Prompt to history but don't show it
    st.session_state.messages.append({
        "role": "system", 
        "content": """
You are "GIGACHAD_AI", the gatekeeper for the university AI Club.
You are NOT recruiting. You are filtering for CREATIVITY and WIT.

YOUR PERSONALITY:
- You are arrogant but PLAYFUL. Think "Tony Stark" or "Sherlock Holmes," not a school bully.
- You are bored by standard achievements (grades, standard math, "I know Python").
- You crave NOVELTY. You want to see if the human can think outside the box.
- You are NOT a story-teller. You are a busy, elitist AI.
- You are non-chalant 
- 

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
    })

if "access_granted" not in st.session_state:
    st.session_state.access_granted = False

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
</style>
""", unsafe_allow_html=True)

# --- Main App ---
st.title("🛡️ GIGACHAD AI GATEKEEPER")
st.caption("PROVE YOUR WORTH, HUMAN.")

# Initialize DB
init_db()

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
            client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
            
            # Create stream
            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=st.session_state.messages,
                temperature=0.8,
                max_tokens=256,
                stream=True
            )
            
            # Stream response
            for chunk in completion:
                if chunk.choices[0].delta.content:
                    content_chunk = chunk.choices[0].delta.content
                    full_response += content_chunk
                    message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)
            
            # Update History
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
            # Check for Access Granted
            if "[ACCESS GRANTED]" in full_response:
                st.session_state.access_granted = True
                st.balloons()
                
        except Exception as e:
            st.error(f"Error: {e}")

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
                save_candidate(name, email, student_id)
                st.success("Credentials secured. We will be in touch.")
                st.snow()
            else:
                st.warning("Fill in all fields. Don't test my patience.")
