from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date
from firebase_admin import firestore

from backend.database import get_db
from backend.auth import get_uid

router = APIRouter()


class LogIn(BaseModel):
    habit_id: Optional[str] = None
    habit_name: str
    minutes_spent: int
    log_date: date


def recalc_summary(uid: str, day: date, db):
    logs = list(
        db.collection("users").document(uid).collection("activity_logs")
        .where("log_date", "==", str(day)).stream()
    )
    done_mins = sum(log.to_dict().get("minutes_spent", 0) for log in logs)

    habits = list(db.collection("users").document(uid).collection("habits").stream())
    target_mins = sum(h.to_dict().get("target_minutes", 0) for h in habits) or 1

    score = round(min(done_mins / target_mins * 100, 100), 2)

    summary_ref = (
        db.collection("users").document(uid).collection("daily_summaries").document(str(day))
    )
    summary_ref.set(
        {
            "summary_date": str(day),
            "total_completed_minutes": done_mins,
            "total_target_minutes": target_mins,
            "productivity_score": score,
        },
        merge=True,
    )

