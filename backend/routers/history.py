from fastapi import APIRouter, Depends
from datetime import date

from backend.database import get_db
from backend.auth import get_uid

router = APIRouter()


@router.get("/history")
def get_history(uid: str = Depends(get_uid), db=Depends(get_db)):
    docs = (
        db.collection("users").document(uid).collection("daily_summaries")
        .order_by("summary_date", direction="DESCENDING")
        .limit(30)
        .stream()
    )
    return [
        {
            "date": d.to_dict().get("summary_date"),
            "score": d.to_dict().get("productivity_score", 0),
            "completed_minutes": d.to_dict().get("total_completed_minutes", 0),
            "target_minutes": d.to_dict().get("total_target_minutes", 0),
        }
        for d in docs
    ]


@router.get("/history/{day}")
def get_day_detail(day: date, uid: str = Depends(get_uid), db=Depends(get_db)):
    logs = list(
        db.collection("users").document(uid).collection("activity_logs")
        .where("log_date", "==", str(day))
        .stream()
    )

    note_doc = (
        db.collection("users").document(uid).collection("notes").document(str(day)).get()
    )

    summary_doc = (
        db.collection("users").document(uid).collection("daily_summaries").document(str(day)).get()
    )

    all_habits = list(db.collection("users").document(uid).collection("habits").stream())
    done_set = {log.to_dict().get("habit_name") for log in logs}
    pending = [h.to_dict().get("name") for h in all_habits if h.to_dict().get("name") not in done_set]

    return {
        "date": str(day),
        "completed_tasks": [log.to_dict().get("habit_name") for log in logs],
        "pending_tasks": pending,
        "note": note_doc.to_dict().get("content", "") if note_doc.exists else "",
        "score": summary_doc.to_dict().get("productivity_score", 0) if summary_doc.exists else 0,
        "logs": [{"habit": log.to_dict().get("habit_name"), "minutes": log.to_dict().get("minutes_spent")} for log in logs],
    }
