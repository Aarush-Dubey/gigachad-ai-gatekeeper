import os
import datetime
import threading
import json
import gspread
from google.oauth2.service_account import Credentials
from typing import Dict, Optional, List, Any
import logging

import firebase_admin
from firebase_admin import credentials, firestore

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
CREDENTIALS_FILE = "credentials.json" # For Sheets
FIREBASE_CREDS_FILE = "firebase_credentials.json" # For Firestore
SHEET_NAME = "candidates"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

class DatabaseManager:
    def __init__(self):
        self._init_firebase()
    
    def _init_firebase(self):
        """Init Firebase Admin via Service Account (File or Env Var)."""
        try:
            if not firebase_admin._apps:
                # 1. Try File
                if os.path.exists(FIREBASE_CREDS_FILE):
                    cred = credentials.Certificate(FIREBASE_CREDS_FILE)
                    firebase_admin.initialize_app(cred)
                # 2. Try Env Var (JSON content) - Best for Render
                elif os.environ.get("FIREBASE_CREDENTIALS_JSON"):
                    cred_dict = json.loads(os.environ.get("FIREBASE_CREDENTIALS_JSON"))
                    cred = credentials.Certificate(cred_dict)
                    firebase_admin.initialize_app(cred)
                else:
                    # 3. Fallback to ADC
                    logger.warning(f"No credentials file ({FIREBASE_CREDS_FILE}) or env var found. Trying default...")
                    firebase_admin.initialize_app()
            
            self.db = firestore.client()
            logger.info("Firebase Firestore Initialized.")
        except Exception as e:
            logger.critical(f"Firebase Init Failed: {e}")
            # Do not raise, allow app to start even if DB is broken (Partial Failure Mode)
            self.db = None

    def _get_google_sheet(self):
        """Authenticated Google Sheet object."""
        if not os.path.exists(CREDENTIALS_FILE):
            logger.error("Sheets Credentials not found: %s", CREDENTIALS_FILE)
            return None
        try:
            creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
            client = gspread.authorize(creds)
            return client.open(SHEET_NAME).sheet1
        except Exception as e:
            logger.error(f"Google Sheets Auth Error: {e}")
            return None

    def check_connection(self) -> bool:
        """Checks if Firestore is reachable."""
        if not self.db:
            return False
        try:
            # Retrieve a dummy doc or list collections to test conn
            self.db.collections()
            return True
        except:
            return False

    def save_candidate_authenticated(self, user_data: dict, verified_email: str, chat_history: List[Dict]) -> bool:
        """
        Saves candidate + chat history.
        """
        if not self.db:
            logger.critical("Firestore not initialized.")
            return False
            
        # Domain Check (Double Security) - redundant if guarded in main but good practice
        if not verified_email.endswith("bits-pilani.ac.in"):
             return False

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"Saving to Firestore: {user_data.get('name')} ({verified_email})")
        
        # 1. Firestore Write
        try:
            doc_data = {
                "name": user_data.get("name"),
                "email": verified_email,
                "student_id": user_data.get("student_id"),
                "preference": user_data.get("preference"),
                "skills": user_data.get("skills"),
                "commitments": user_data.get("commitments"),
                "notes": user_data.get("notes"),
                "chat_history": chat_history,
                "timestamp": timestamp,
                "synced": False
            }
            self.db.collection("candidates").add(doc_data)
        except Exception as e:
            logger.critical(f"FATAL: Firestore Write Failed! {e}")
            return False

        # 2. Sync to Sheets
        threading.Thread(target=self._sync_one, args=(user_data, verified_email, timestamp)).start()
        return True

    def _sync_one(self, user_data, email, timestamp):
        """Attempts to sync to sheets."""
        try:
            sheet = self._get_google_sheet()
            if not sheet:
                logger.warning(f"Sync skipped for {email}")
                return

            row = [
                user_data.get("name"), 
                email, 
                user_data.get("student_id"), 
                user_data.get("preference"),
                user_data.get("skills"),
                timestamp
            ]
            sheet.append_row(row)
            
            # Mark synced
            docs = self.db.collection("candidates").where("email", "==", email).stream()
            for doc in docs:
                doc.reference.update({"synced": True})
                
            logger.info(f"Synced {email} to Sheets.")
        except Exception as e:
            logger.error(f"Sync failed for {email}: {e}")

    def sync_pending(self) -> str:
        """Retries syncing all unsynced records."""
        if not self.db:
            return "Firestore unavailable."

        try:
            docs = self.db.collection("candidates").where("synced", "==", False).stream()
            count = 0
            sheet = self._get_google_sheet()
            
            for doc in docs:
                data = doc.to_dict()
                if sheet:
                    try:
                        sheet.append_row([data.get("name"), data.get("email"), data.get("student_id"), data.get("timestamp")])
                        doc.reference.update({"synced": True})
                        count += 1
                    except Exception as ex:
                        logger.error(f"Retry failed for {data.get('email')}: {ex}")
            
            return f"Synced {count} records."
        except Exception as e:
            return f"Error: {e}"

    def get_all_stats(self) -> Dict:
        if not self.db: return {"error": "No DB"}
        # Firestore count aggregation can be expensive/slow on huge datasets, 
        # but for this app straight count is fine or using aggregation queries if valid.
        # We'll just stream for now (not efficient for millions, fine for thousands)
        try:
            all_docs = list(self.db.collection("candidates").stream())
            total = len(all_docs)
            synced = sum(1 for d in all_docs if d.to_dict().get("synced"))
            return {"total": total, "synced": synced, "pending": total - synced}
        except:
            return {"status": "error"}
