import os
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import firebase_admin
from firebase_admin import credentials

from dotenv import load_dotenv

load_dotenv()

from backend import config
from backend.routers import users, habits, activity, analytics, history, notes, ai_chat, report, leaderboard, admin

app = FastAPI(title="Kaizen AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' "
        "https://www.gstatic.com "
        "https://apis.google.com "
        "https://cdn.jsdelivr.net "
        "https://www.youtube.com "
        "https://s.ytimg.com; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "connect-src 'self' "
        "https://identitytoolkit.googleapis.com "
        "https://securetoken.googleapis.com "
        "https://www.googleapis.com "
        "https://apis.google.com "
        "https://firebaseinstallations.googleapis.com; "
        "frame-src https://accounts.google.com https://*.firebaseapp.com "
        "https://www.youtube.com https://www.youtube-nocookie.com; "
        "frame-ancestors 'none';"
    )
    return response

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
app.include_router(report.router, prefix="/api")
app.include_router(leaderboard.router, prefix="/api")
app.include_router(admin.router, prefix="/api")

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

PAGES = {"dashboard", "activity", "graphs", "history", "ai", "pomodoro", "ambient", "landing", "profile", "admin", "leaderboard"}

@app.get("/")
def home():
    return FileResponse(os.path.join(FRONTEND, "landing.html"))

@app.get("/{page}.html")
def load_page(page: str):
    if page not in PAGES:
        raise HTTPException(status_code=404, detail="page not found")
    return FileResponse(os.path.join(FRONTEND, f"{page}.html"))
