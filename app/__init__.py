# ==============================================================================
# Application Factory
# ------------------------------------------------------------------------------
# THIS IS THE DEFINITIVE, FINAL, AND CORRECTED VERSION.
# It initializes Firebase from a secure environment variable, not a file.
# This is the robust method for serverless platforms like Cloud Run.
# ==============================================================================

import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask
from config import Config
from flask_mail import Mail
import os
import json

mail = Mail()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    mail.init_app(app)

    # --- THIS IS THE DEFINITIVE FIX FOR FIREBASE INITIALIZATION ---
    if not firebase_admin._apps:
        try:
            # Get the JSON credentials directly from the environment variable
            creds_json_str = os.environ.get('FIREBASE_CREDENTIALS_JSON')
            if not creds_json_str:
                raise ValueError("FIREBASE_CREDENTIALS_JSON environment variable not set.")
            
            # Convert the JSON string into a Python dictionary
            creds_dict = json.loads(creds_json_str)
            
            # Initialize the app with the credentials dictionary
            cred = credentials.Certificate(creds_dict)
            firebase_admin.initialize_app(cred)
            print("Firebase initialized successfully from environment variable.")
        except Exception as e:
            raise ValueError(f"Failed to initialize Firebase Admin SDK from JSON: {e}")

    db_client = firestore.client()
    app.config['DB'] = db_client
    
    # --- Register All Blueprints ---
    from .routes.main import bp as main_bp
    app.register_blueprint(main_bp)
    from .routes.auth import bp as auth_bp
    app.register_blueprint(auth_bp)
    from .routes.dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp)
    from .routes.friends import bp as social_bp 
    app.register_blueprint(social_bp)
    from .routes.challenges import bp as challenges_bp
    app.register_blueprint(challenges_bp)
    from .routes.study_plan import bp as study_plan_bp
    app.register_blueprint(study_plan_bp)

    return app
