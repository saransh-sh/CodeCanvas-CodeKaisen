from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, timedelta
from firebase_admin import firestore

from backend.database import get_db
from backend.auth import get_uid

router = APIRouter()


class LogIn(BaseModel):
    habit_id: Optional[str] = Field(None, max_length=128)
    habit_name: str = Field(..., min_length=1, max_length=100)
    minutes_spent: int = Field(..., ge=1, le=1440)
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


def award_daily_xp(uid: str, day: date, db):
    from backend.routers.analytics import check_achievements

    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()

    if not user_doc.exists:
        return

    logs = list(
        db.collection("users").document(uid).collection("activity_logs")
        .where("log_date", "==", str(day)).stream()
    )
    habits = list(db.collection("users").document(uid).collection("habits").stream())

    if not habits:
        return

    habit_targets = {h.to_dict().get("name"): h.to_dict().get("target_minutes", 60) for h in habits}
    habit_progress = {}
    for log in logs:
        d = log.to_dict()
        habit_name = d.get("habit_name")
        habit_progress[habit_name] = habit_progress.get(habit_name, 0) + d.get("minutes_spent", 0)

    all_completed = all(
        habit_progress.get(name, 0) >= target
        for name, target in habit_targets.items()
    )

    if all_completed and len(habit_targets) > 0:
        user_data = user_doc.to_dict()
        perfect_days = user_data.get("perfect_days", [])
        day_str = str(day)

        if day_str not in perfect_days:
            perfect_days.append(day_str)
            current_bonus = user_data.get("achievements", {}).get("bonus_xp", 0)
            user_ref.update({
                "perfect_days": perfect_days,
                "achievements": {
                    "bonus_xp": current_bonus + 50,
                    "last_updated": firestore.SERVER_TIMESTAMP
                }
            })

    user_data = user_doc.to_dict()
    streak = user_data.get("streak", 0)
    yesterday = day - timedelta(days=1)
    yesterday_logs = list(
        db.collection("users").document(uid).collection("activity_logs")
        .where("log_date", "==", str(yesterday)).limit(1).stream()
    )

    if yesterday_logs and streak > 1:
        streak_days = user_data.get("streak_bonus_days", [])
        day_str = str(day)

        if day_str not in streak_days:
            streak_days.append(day_str)
            current_bonus = user_data.get("achievements", {}).get("bonus_xp", 0)
            user_ref.update({
                "streak_bonus_days": streak_days,
                "achievements": {
                    "bonus_xp": current_bonus + 20,
                    "last_updated": firestore.SERVER_TIMESTAMP
                }
            })

    check_achievements(uid, db)


@router.get("/activity")
def get_logs(log_date: Optional[date] = None, uid: str = Depends(get_uid), db=Depends(get_db)):
    query = db.collection("users").document(uid).collection("activity_logs")
    if log_date:
        query = query.where("log_date", "==", str(log_date))
    docs = query.order_by("log_date", direction=firestore.Query.DESCENDING).stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


@router.post("/activity", status_code=201)
def add_log(data: LogIn, uid: str = Depends(get_uid), db=Depends(get_db)):
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
    award_daily_xp(uid, data.log_date, db)

    habits = list(db.collection("users").document(uid).collection("habits").stream())
    habit_targets = {h.to_dict().get("name"): h.to_dict().get("target_minutes", 60) for h in habits}
    target = habit_targets.get(data.habit_name, 60)
    xp_gained = 10 if data.minutes_spent >= target else 5

    return {
        "id": doc_ref.id,
        "habit_id": data.habit_id,
        "habit_name": data.habit_name,
        "minutes_spent": data.minutes_spent,
        "log_date": str(data.log_date),
        "xp_gained": xp_gained
    }


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
    award_daily_xp(uid, data.log_date, db)
    if old_date_str and old_date_str != str(data.log_date):
        recalc_summary(uid, date.fromisoformat(old_date_str), db)
        award_daily_xp(uid, date.fromisoformat(old_date_str), db)
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
