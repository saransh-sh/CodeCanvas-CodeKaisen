import os
from firebase_admin import auth as fb_auth
from fastapi import Header, HTTPException


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
        raise HTTPException(status_code=401, detail=str(e))