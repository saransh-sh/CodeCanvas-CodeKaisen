import logging
import os
from firebase_admin import auth as fb_auth
from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)


def get_uid(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="need a bearer token")
    parts = authorization.split(" ", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=401, detail="token missing from header")
    token = parts[1]
    try:
        data = fb_auth.verify_id_token(token)
        return data["uid"]
    except Exception as e:
        logger.warning("Token verification failed: %s", str(e))
        raise HTTPException(status_code=401, detail="invalid or expired token")


def get_admin_uid(authorization: str = Header(...)):
    from backend import config

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="need a bearer token")
    parts = authorization.split(" ", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=401, detail="token missing from header")
    token = parts[1]
    try:
        data = fb_auth.verify_id_token(token)
    except Exception as e:
        logger.warning("Token verification failed: %s", str(e))
        raise HTTPException(status_code=401, detail="invalid or expired token")

    email = (data.get("email") or "").lower()
    if email not in config.ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="admin access required")
    return data["uid"]

