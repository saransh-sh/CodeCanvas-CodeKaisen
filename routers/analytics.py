from fastapi import APIRouter, Depends
from datetime import date, timedelta
from backend.database import get_db
from backend.auth import get_uid

router = APIRouter()

@router.get("/analytics/today")
def today_stats(uid: str = Depends(get_uid), db=Depends(get_db)):
    today = date.today()
    logs = list(
        db.collection("users").document(uid).collection("activity_logs")
        .where("log_date", "==", str(today)).stream()
    )
    habits = list(db.collection("users").document(uid).collection("habits").stream())

    # map habit name -> how many mins done today
    done_map = {}
    for log in logs:
        d = log.to_dict()
        done_map[d["habit_name"]] = done_map.get(d["habit_name"], 0) + d.get("minutes_spent", 0)

    result = []
    for h in habits:
        hd = h.to_dict()
        done = done_map.get(hd["name"], 0)
        target = hd.get("target_minutes", 60)
        if done >= target:
            color = "green"
        elif done > 0:
            color = "yellow"
        else:
            color = "red"
        result.append({"name": hd["name"], "target": target, "spent": done, "status": color})

    return {"date": str(today), "progress": result}


@router.get("/analytics/weekly")
def weekly_stats(uid: str = Depends(get_uid), db=Depends(get_db)):
    today = date.today()
    start = str(today - timedelta(days=6))
    docs = (
        db.collection("users").document(uid).collection("daily_summaries")
        .where("summary_date", ">=", start)
        .order_by("summary_date")
        .stream()
    )
    return [
        {
            "date": d.to_dict().get("summary_date"),
            "score": d.to_dict().get("productivity_score", 0),
            "completed_minutes": d.to_dict().get("total_completed_minutes", 0),
        }
        for d in docs
    ]


@router.get("/analytics/distribution")
def time_distribution(uid: str = Depends(get_uid), db=Depends(get_db)):
    today = date.today()
    start = str(today - timedelta(days=6))
    docs = (
        db.collection("users").document(uid).collection("activity_logs")
        .where("log_date", ">=", start)
        .stream()
    )
    totals: dict = {}
    for doc in docs:
        d = doc.to_dict()
        name = d.get("habit_name", "other")
        totals[name] = totals.get(name, 0) + d.get("minutes_spent", 0)
    return [{"habit": k, "minutes": v} for k, v in totals.items()]


@router.get("/analytics/radar")
def radar_stats(uid: str = Depends(get_uid), db=Depends(get_db)):
  
    today = date.today()
    week_start_date = today - timedelta(days=6)
    week_start = str(week_start_date)
    days_in_range = (today - week_start_date).days + 1  # inclusive range

    habits = list(db.collection("users").document(uid).collection("habits").stream())

    if not habits:
        return {"labels": [], "data": []}

    logs = list(
        db.collection("users").document(uid).collection("activity_logs")
        .where("log_date", ">=", week_start)
        .stream()
    )
    habit_mins: dict = {}
    for log in logs:
        d = log.to_dict()
        name = d.get("habit_name", "")
        habit_mins[name] = habit_mins.get(name, 0) + d.get("minutes_spent", 0)

    labels = []
    data = []
    for h in habits:
        hd = h.to_dict()
        name = hd.get("name", "")
        target_per_day = hd.get("target_minutes", 60)
        target_7 = target_per_day * 7
        done = habit_mins.get(name, 0)
        score = round(min(done / target_7 * 100, 100), 1) if target_7 > 0 else 0
        labels.append(name)
        data.append(score)

  
    summaries = list(
        db.collection("users").document(uid).collection("daily_summaries")
        .where("summary_date", ">=", week_start)
        .stream()
    )
    active_days = sum(
        1 for s in summaries if s.to_dict().get("total_completed_minutes", 0) > 0
    )
    consistency = round(active_days / days_in_range * 100, 1)
    labels.append("Consistency")
    data.append(consistency)

    return {"labels": labels, "data": data}
