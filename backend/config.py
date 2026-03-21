import os


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Required environment variable '{name}' is not set. "
            "Copy .env.example to .env and fill in the values."
        )
    return value

FIREBASE_SERVICE_ACCOUNT_KEY: str = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY", "")

FIREBASE_API_KEY: str = _require("FIREBASE_API_KEY")
FIREBASE_AUTH_DOMAIN: str = _require("FIREBASE_AUTH_DOMAIN")
FIREBASE_PROJECT_ID: str = _require("FIREBASE_PROJECT_ID")
FIREBASE_STORAGE_BUCKET: str = _require("FIREBASE_STORAGE_BUCKET")
FIREBASE_MESSAGING_SENDER_ID: str = _require("FIREBASE_MESSAGING_SENDER_ID")
FIREBASE_APP_ID: str = _require("FIREBASE_APP_ID")

OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")

_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000")
ALLOWED_ORIGINS: list[str] = [o.strip() for o in _raw_origins.split(",") if o.strip()]

_raw_admin = os.getenv("ADMIN_EMAILS", "")
ADMIN_EMAILS: list[str] = [e.strip().lower() for e in _raw_admin.split(",") if e.strip()]

