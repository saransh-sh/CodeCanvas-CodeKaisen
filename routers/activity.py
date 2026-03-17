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
@router.get("/activity")
def get_logs(log_date: Optional[date] = None, uid: str = Depends(get_uid), db=Depends(get_db)):
    query = db.collection("users").document(uid).collection("activity_logs")
    if log_date:
        query = query.where("log_date", "==", str(log_date))
    docs = query.order_by("log_date", direction=firestore.Query.DESCENDING).stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


@router.post("/activity", status_code=201)
def add_log(data: LogIn, uid: str = Depends(get_uid), db=Depends(get_db)):
    if data.minutes_spent <= 0:
        raise HTTPException(status_code=400, detail="minutes must be greater than 0")
    log_data = {
        "habit_id": data.habit_id,
        "habit_name": data.habit_name,
        "minutes_spent": data.minutes_spent,
        "log_date": str(data.log_date),
        "created_at": firestore.SERVER_TIMESTAMP,
    }
    ref = db.collection("users").document(uid).collection("activity_logs").add(log_data)
    _, doc_ref = ref
    recalc_summary(uid, data.log_date, db)
    return {"id": doc_ref.id, "habit_id": data.habit_id, "habit_name": data.habit_name,
            "minutes_spent": data.minutes_spent, "log_date": str(data.log_date)}


@router.put("/activity/{lid}")
def update_log(lid: str, data: LogIn, uid: str = Depends(get_uid), db=Depends(get_db)):
    log_ref = db.collection("users").document(uid).collection("activity_logs").document(lid)
    log_doc = log_ref.get()
    if not log_doc.exists:
        raise HTTPException(status_code=404, detail="log not found")
    old_date_str = log_doc.to_dict().get("log_date")
    log_ref.update({
        "habit_name": data.habit_name,
        "minutes_spent": data.minutes_spent,
        "log_date": str(data.log_date),
        **({"habit_id": data.habit_id} if data.habit_id else {}),
    })
    recalc_summary(uid, data.log_date, db)
    if old_date_str and old_date_str != str(data.log_date):
        recalc_summary(uid, date.fromisoformat(old_date_str), db)
    updated = log_ref.get().to_dict()
    return {"id": lid, **updated}


@router.delete("/activity/{lid}", status_code=204)
def delete_log(lid: str, uid: str = Depends(get_uid), db=Depends(get_db)):
    log_ref = db.collection("users").document(uid).collection("activity_logs").document(lid)
    log_doc = log_ref.get()
    if not log_doc.exists:
        raise HTTPException(status_code=404, detail="log not found")
    day_str = log_doc.to_dict().get("log_date")
    log_ref.delete()
    if day_str:
        recalc_summary(uid, date.fromisoformat(day_str), db)