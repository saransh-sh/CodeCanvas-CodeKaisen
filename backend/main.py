import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import firebase_admin
from firebase_admin import credentials

from dotenv import load_dotenv

load_dotenv()

from backend import config
from backend.routers import users, habits, activity, analytics, history, notes, ai_chat

app = FastAPI(title="Kaizen AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if config.FIREBASE_SERVICE_ACCOUNT_KEY and os.path.exists(config.FIREBASE_SERVICE_ACCOUNT_KEY):
    cred = credentials.Certificate(config.FIREBASE_SERVICE_ACCOUNT_KEY)
    firebase_admin.initialize_app(cred)
else:
    firebase_admin.initialize_app()

app.include_router(users.router, prefix="/api")
app.include_router(habits.router, prefix="/api")
app.include_router(activity.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(history.router, prefix="/api")
app.include_router(notes.router, prefix="/api")
app.include_router(ai_chat.router, prefix="/api")

@app.get("/api/config/firebase")
def firebase_config():
 
    return {
        "apiKey": config.FIREBASE_API_KEY,
        "authDomain": config.FIREBASE_AUTH_DOMAIN,
        "projectId": config.FIREBASE_PROJECT_ID,
        "storageBucket": config.FIREBASE_STORAGE_BUCKET,
        "messagingSenderId": config.FIREBASE_MESSAGING_SENDER_ID,
        "appId": config.FIREBASE_APP_ID,
    }

FRONTEND = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
app.mount("/static", StaticFiles(directory=os.path.join(FRONTEND, "static")), name="static")
app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND, "assets")), name="assets")

PAGES = {"dashboard", "activity", "graphs", "history", "ai", "pomodoro", "ambient", "landing", "profile"}

@app.get("/")
def home():
    return FileResponse(os.path.join(FRONTEND, "landing.html"))

@app.get("/{page}.html")
def load_page(page: str):
    if page not in PAGES:
        raise HTTPException(status_code=404, detail="page not found")
    return FileResponse(os.path.join(FRONTEND, f"{page}.html"))