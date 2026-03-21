from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, timedelta
from firebase_admin import firestore

from backend.database import get_db
from backend.auth import get_uid

router = APIRouter()


class UserIn(BaseModel):
    email: str = Field(..., max_length=254)
    display_name: Optional[str] = Field(None, max_length=100)


@router.post("/users", status_code=201)
def save_user(data: UserIn, uid: str = Depends(get_uid), db=Depends(get_db)):
    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()
    if user_doc.exists:
        if data.display_name:
            user_ref.update({"display_name": data.display_name})
        updated = user_ref.get().to_dict()
        return {**updated, "id": uid}
    user_data = {
        "email": data.email,
        "display_name": data.display_name,
        "streak": 0,
        "longest_streak": 0,
        "created_at": firestore.SERVER_TIMESTAMP,
    }
    user_ref.set(user_data)
    return {"id": uid, "email": data.email, "display_name": data.display_name, "streak": 0, "longest_streak": 0}


@router.get("/users/{uid}")
def fetch_user(uid: str, token_uid: str = Depends(get_uid), db=Depends(get_db)):
    if uid != token_uid:
        raise HTTPException(status_code=403, detail="access denied")
    user_doc = db.collection("users").document(uid).get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="user not found")
    return {**user_doc.to_dict(), "id": uid}


@router.put("/users/{uid}/streak")
def recalculate_streak(uid: str, token_uid: str = Depends(get_uid), db=Depends(get_db)):
    if uid != token_uid:
        raise HTTPException(status_code=403, detail="access denied")
    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="user not found")

    today = date.today()
    streak = 0

    for i in range(365):
        day = today - timedelta(days=i)
        day_str = str(day)
        logs = list(
            db.collection("users").document(uid).collection("activity_logs")
            .where("log_date", "==", day_str).limit(1).stream()
        )
        if logs:
            streak += 1
        else:
            if i == 0:
                continue
            break

    old_longest = user_doc.to_dict().get("longest_streak", 0)
    longest = max(old_longest, streak)
    user_ref.update({"streak": streak, "longest_streak": longest})
    return {"streak": streak, "longest_streak": longest}
