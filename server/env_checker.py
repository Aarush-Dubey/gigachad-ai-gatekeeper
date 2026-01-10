import os

REQUIRED_ENV_VARS = [
    "GROQ_KEY_1",
    "FIREBASE_API_KEY",
    "FIREBASE_AUTH_DOMAIN",
    "FIREBASE_PROJECT_ID",
    "FIREBASE_STORAGE_BUCKET",
    "FIREBASE_MESSAGING_SENDER_ID",
    "FIREBASE_APP_ID",
    "ADMIN_SECRET"
]

def check_env():
    missing = []
    for var in REQUIRED_ENV_VARS:
        if not os.getenv(var):
            missing.append(var)
            
    # Check Firebase Admin Credentials (File OR JSON Var)
    has_creds_file = os.path.exists(os.path.join(os.path.dirname(__file__), "firebase_credentials.json"))
    has_creds_var = os.getenv("FIREBASE_CREDENTIALS_JSON")
    
    if not has_creds_file and not has_creds_var:
        missing.append("FIREBASE_CREDENTIALS_JSON (or firebase_credentials.json file)")

    return missing
