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

    def save_candidate_authenticated(self, user_data: dict, verified_email: str, chat_history: List[Dict], uid: str = None) -> bool:
        """
        Saves candidate submission data directly into the user's profile.
        Everything in one place: users/{uid}
        """
        if not self.db:
            logger.critical("Firestore not initialized.")
            return False
            
        # Domain Check
        if not verified_email.endswith("bits-pilani.ac.in"):
             return False

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"Saving submission to user profile: {user_data.get('name')} ({verified_email})")
        
        try:
            # If we have UID, update the user's profile directly
            if uid:
                doc_ref = self.db.collection("users").document(uid)
                doc_ref.update({
                    "submission": {
                        "student_id": user_data.get("student_id"),
                        "preference": user_data.get("preference"),
                        "skills": user_data.get("skills"),
                        "commitments": user_data.get("commitments"),
                        "notes": user_data.get("notes"),
                        "submitted_at": timestamp
                    },
                    "final_chat_history": chat_history,
                    "form_submitted": True,
                    "status": "submitted",
                    "synced_to_sheets": False
                })
                logger.info(f"✅ Submission saved to users/{uid}")
            else:
                # Fallback: create in users collection by email hash
                import hashlib
                uid_fallback = hashlib.md5(verified_email.encode()).hexdigest()
                doc_ref = self.db.collection("users").document(uid_fallback)
                doc_ref.set({
                    "email": verified_email,
                    "name": user_data.get("name"),
                    "submission": {
                        "student_id": user_data.get("student_id"),
                        "preference": user_data.get("preference"),
                        "skills": user_data.get("skills"),
                        "commitments": user_data.get("commitments"),
                        "notes": user_data.get("notes"),
                        "submitted_at": timestamp
                    },
                    "final_chat_history": chat_history,
                    "form_submitted": True,
                    "status": "submitted",
                    "synced_to_sheets": False
                }, merge=True)
                logger.info(f"✅ Submission saved to users/{uid_fallback} (fallback)")
                
        except Exception as e:
            logger.critical(f"FATAL: Firestore Write Failed! {e}")
            return False

        # DISABLED: Real-time Sheets sync causes rate limiting under high load
        # Data is secured in Firestore. Use /admin/sync for batch Sheets sync.
        # threading.Thread(target=self._sync_one, args=(user_data, verified_email, timestamp)).start()
        logger.info(f"✅ Data secured in Firestore. Pending batch sync to Sheets.")
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
        try:
            all_docs = list(self.db.collection("candidates").stream())
            total = len(all_docs)
            synced = sum(1 for d in all_docs if d.to_dict().get("synced"))
            return {"total": total, "synced": synced, "pending": total - synced}
        except:
            return {"status": "error"}

    # ========== USER PROFILE & CHAT CHECKPOINT SYSTEM ==========

    def get_or_create_profile(self, uid: str, email: str, name: str) -> Dict:
        """
        Gets existing user profile or creates a new one.
        Called on first chat message of a session.
        """
        if not self.db:
            logger.warning("Firestore unavailable for profile.")
            return {}
        
        try:
            doc_ref = self.db.collection("users").document(uid)
            doc = doc_ref.get()
            
            if doc.exists:
                # Update last active
                doc_ref.update({
                    "last_active": datetime.datetime.utcnow().isoformat(),
                })
                logger.info(f"👤 Profile found: {email}")
                return doc.to_dict()
            else:
                # Create new profile
                profile = {
                    "uid": uid,
                    "email": email,
                    "name": name,
                    "created_at": datetime.datetime.utcnow().isoformat(),
                    "last_active": datetime.datetime.utcnow().isoformat(),
                    "status": "in_progress",  # in_progress | submitted | granted
                    "sessions": [],
                    "total_messages": 0,
                    "access_granted": False
                }
                doc_ref.set(profile)
                logger.info(f"✨ New profile created: {email}")
                return profile
        except Exception as e:
            logger.error(f"Profile error for {email}: {e}")
            return {}

    def start_session(self, uid: str) -> str:
        """
        Starts a new chat session for the user.
        Returns the session_id.
        """
        import uuid
        session_id = str(uuid.uuid4())
        
        if not self.db:
            return session_id
        
        try:
            doc_ref = self.db.collection("users").document(uid)
            session = {
                "session_id": session_id,
                "started_at": datetime.datetime.utcnow().isoformat(),
                "messages": [],
                "outcome": "in_progress"  # in_progress | granted | abandoned
            }
            doc_ref.update({
                "sessions": firestore.ArrayUnion([session]),
                "last_active": datetime.datetime.utcnow().isoformat()
            })
            logger.info(f"🚀 Session started: {session_id[:8]}...")
        except Exception as e:
            logger.error(f"Session start error: {e}")
        
        return session_id

    def save_chat_checkpoint(self, uid: str, session_id: str, messages: List[Dict], force: bool = False) -> bool:
        """
        Saves chat checkpoint every 10 messages (or if force=True).
        Updates the session's messages array in the user's profile.
        """
        if not self.db:
            return False
        
        # Only save every 10 messages unless forced
        if not force and len(messages) % 10 != 0:
            return False
        
        try:
            doc_ref = self.db.collection("users").document(uid)
            doc = doc_ref.get()
            
            if not doc.exists:
                return False
            
            data = doc.to_dict()
            sessions = data.get("sessions", [])
            
            # Find and update the current session
            for i, session in enumerate(sessions):
                if session.get("session_id") == session_id:
                    sessions[i]["messages"] = messages
                    sessions[i]["last_checkpoint"] = datetime.datetime.utcnow().isoformat()
                    break
            
            doc_ref.update({
                "sessions": sessions,
                "total_messages": len(messages),
                "last_active": datetime.datetime.utcnow().isoformat()
            })
            
            logger.info(f"💾 Checkpoint saved: {len(messages)} messages for session {session_id[:8]}...")
            return True
        except Exception as e:
            logger.error(f"Checkpoint error: {e}")
            return False

    def mark_access_granted(self, uid: str, session_id: str) -> bool:
        """
        Marks the user as having been granted access.
        Updates both the session outcome and the user's overall status.
        """
        if not self.db:
            return False
        
        try:
            doc_ref = self.db.collection("users").document(uid)
            doc = doc_ref.get()
            
            if not doc.exists:
                return False
            
            data = doc.to_dict()
            sessions = data.get("sessions", [])
            
            for i, session in enumerate(sessions):
                if session.get("session_id") == session_id:
                    sessions[i]["outcome"] = "granted"
                    sessions[i]["granted_at"] = datetime.datetime.utcnow().isoformat()
                    break
            
            doc_ref.update({
                "sessions": sessions,
                "access_granted": True,
                "status": "granted",
                "last_active": datetime.datetime.utcnow().isoformat()
            })
            
            logger.info(f"🎉 Access granted for user: {uid}")
            return True
        except Exception as e:
            logger.error(f"Grant access error: {e}")
            return False

    def get_user_stats(self) -> Dict:
        """Returns stats about all users."""
        if not self.db:
            return {"error": "No DB"}
        try:
            users = list(self.db.collection("users").stream())
            total = len(users)
            granted = sum(1 for u in users if u.to_dict().get("access_granted"))
            in_progress = total - granted
            return {"total_users": total, "access_granted": granted, "in_progress": in_progress}
        except Exception as e:
            return {"error": str(e)}

    def mark_form_submitted(self, uid: str) -> bool:
        """
        Marks the user's form as submitted.
        Called after successful form submission.
        """
        if not self.db:
            return False
        
        try:
            doc_ref = self.db.collection("users").document(uid)
            doc_ref.update({
                "form_submitted": True,
                "status": "submitted",
                "submitted_at": datetime.datetime.utcnow().isoformat(),
                "last_active": datetime.datetime.utcnow().isoformat()
            })
            logger.info(f"📝 Form marked as submitted for user: {uid}")
            return True
        except Exception as e:
            logger.error(f"Mark submitted error: {e}")
            return False

    def check_user_status(self, uid: str) -> Dict:
        """
        Checks if a user has already submitted.
        Returns status info for frontend to decide what to show.
        """
        if not self.db:
            return {"error": "No DB", "submitted": False}
        
        try:
            doc_ref = self.db.collection("users").document(uid)
            doc = doc_ref.get()
            
            if not doc.exists:
                return {"exists": False, "submitted": False, "access_granted": False}
            
            data = doc.to_dict()
            return {
                "exists": True,
                "submitted": data.get("form_submitted", False),
                "access_granted": data.get("access_granted", False),
                "status": data.get("status", "unknown")
            }
        except Exception as e:
            logger.error(f"Check status error: {e}")
            return {"error": str(e), "submitted": False}
