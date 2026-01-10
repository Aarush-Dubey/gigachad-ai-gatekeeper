import firebase_admin
from firebase_admin import credentials, firestore
import datetime

# Setup
cred = credentials.Certificate("server/firebase_credentials.json")
try:
    firebase_admin.initialize_app(cred)
except ValueError:
    pass # Already initialized

db = firestore.client()

# Default Project ID Check
print(f"Project: {db.project}")

# Write Test
doc_ref = db.collection("test_connectivity").document("ping")
try:
    doc_ref.set({
        "status": "online",
        "timestamp": datetime.datetime.now().isoformat(),
        "message": "GIGACHAD AI IS WATCHING"
    })
    print("✅ WRITE SUCCESS: Wrote to 'test_connectivity/ping'")
except Exception as e:
    print(f"❌ WRITE FAILED: {e}")

# Read Test
try:
    doc = doc_ref.get()
    if doc.exists:
        print(f"✅ READ SUCCESS: {doc.to_dict()}")
    else:
        print("❌ READ FAILED: Document not found.")
except Exception as e:
    print(f"❌ READ FAILED: {e}")
