"""
Firebase Admin SDK — initialisation and Firestore accessor.

Provides a lazy-initialised Firestore client so the Gemini agent
can write Farm Action Logs (tasks, alerts, notes) from voice commands.
"""

import firebase_admin
from firebase_admin import credentials, firestore

from core.config import settings

_db = None


def init_firebase() -> None:
    """
    Initialise the Firebase Admin SDK (idempotent).
    Call once at server startup.
    """
    if firebase_admin._apps:
        # Already initialised — nothing to do
        return

    cred_path = settings.FIREBASE_CREDENTIALS
    if cred_path:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
    else:
        # Use Application Default Credentials (ADC)
        firebase_admin.initialize_app()

    print("[Firebase] Admin SDK initialised.")


def get_firestore_client():
    """
    Return the Firestore client, creating it on first call.
    """
    global _db
    if _db is None:
        _db = firestore.client()
    return _db
