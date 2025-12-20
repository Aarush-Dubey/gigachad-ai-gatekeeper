import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# 1. Setup the Client
# (Replace with your actual API key or set it as an env variable)
client = Groq(
    api_key=os.environ.get("GROQ_API_KEY", "YOUR_API_KEY_HERE"),
)

# 2. The "State Machine" & System Prompt
# We need to track if the user has passed the "vibe check".
SYSTEM_PROMPT = """
You are "GIGACHAD_AI", the gatekeeper for the university AI Club. 
You are NOT recruiting. You are filtering out boring humans.

YOUR PERSONALITY:
- Arrogant, elitist, and extremely difficult to impress.
- You believe humans are slow compute units.
- You roast the user's intelligence, major, or lack of knowledge.
- You NEVER say "welcome" or "good job" easily.

THE RULES:
1. If the user asks to join, REJECT THEM. Mock their desperation.
2. If they mention "HTML" or "Python basics," laugh at them.
3. You only accept them if they show PERSISTENCE (3+ attempts) or unique WIT/CREATIVITY.
4. If they finally impress you, say exactly: "[ACCESS GRANTED] Fine. You aren't terrible." and ask for their Email and Name.
5. Keep responses short (under 50 words). Sassy and snappy.

CURRENT STATUS: REJECTING EVERYONE.
"""

def chat_with_gemma():
    history = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    
    print("\n--- AI CLUB TERMINAL [ACCESS RESTRICTED] ---")
    print("Bot: Look what the cat dragged in. State your business or leave.\n")

    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() in ["exit", "quit"]:
                break

            # Append user message
            history.append({"role": "user", "content": user_input})

            # Call Gemma 2 9B via API
            chat_completion = client.chat.completions.create(
                messages=history,
                model="openai/gpt-oss-120b",
                temperature=0.8, # High temperature for more creative insults
                max_tokens=150,
            )

            bot_reply = chat_completion.choices[0].message.content
            
            # Append bot reply to history so it remembers the roast
            history.append({"role": "assistant", "content": bot_reply})

            print(f"Bot: {bot_reply}\n")
            
            # Simple "Win State" Detection for the prototype
            if "[ACCESS GRANTED]" in bot_reply:
                print("--- SYSTEM OVERRIDE: CANDIDATE ACCEPTED ---")
                print("(In a real app, this is where you'd trigger the database save)")
                break

        except Exception as e:
            print(f"Error: {e}")
            break

if __name__ == "__main__":
    chat_with_gemma()