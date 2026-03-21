from fastapi import APIRouter, Depends
from datetime import date, timedelta
from collections import defaultdict
import math
from firebase_admin import firestore

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
    start_date = today - timedelta(days=6)
    start = str(start_date)
    docs = (
        db.collection("users").document(uid).collection("daily_summaries")
        .where("summary_date", ">=", start)
        .order_by("summary_date")
        .stream()
    )
    score_map = {
        d.to_dict()["summary_date"]: d.to_dict()
        for d in docs
        if "summary_date" in d.to_dict()
    }
    return [
        {
            "date": str(start_date + timedelta(days=i)),
            "score": score_map.get(str(start_date + timedelta(days=i)), {}).get("productivity_score", 0),
            "completed_minutes": score_map.get(str(start_date + timedelta(days=i)), {}).get("total_completed_minutes", 0),
        }
        for i in range(7)
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
    days_in_range = (today - week_start_date).days + 1

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


# ── Advanced Analytics (any available data, best day, longest streak, habit streaks) ──

@router.get("/analytics/advanced")
def advanced_stats(uid: str = Depends(get_uid), db=Depends(get_db)):
    today = date.today()

    one_year_ago = today - timedelta(days=364)
    summaries = list(
        db.collection("users").document(uid).collection("daily_summaries")
        .where("summary_date", ">=", str(one_year_ago))
        .order_by("summary_date")
        .stream()
    )
    score_map = {
        s.to_dict().get("summary_date"): s.to_dict().get("productivity_score", 0)
        for s in summaries
    }

    if score_map:
        earliest = min(score_map.keys())
        start_date = date.fromisoformat(earliest)
    else:
        start_date = today - timedelta(days=6)

    total_days = (today - start_date).days + 1
    daily = [
        {
            "date": str(start_date + timedelta(days=i)),
            "pct": score_map.get(str(start_date + timedelta(days=i)), 0),
        }
        for i in range(total_days)
    ]
    days_with_data = sum(1 for d in daily if d["pct"] > 0)
    completion_rate = round(sum(d["pct"] for d in daily) / max(total_days, 1), 1)

    day_scores: dict = defaultdict(list)
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for d in daily:
        day_obj = date.fromisoformat(d["date"])
        day_scores[day_obj.weekday()].append(d["pct"])

    best_day, best_day_pct = "N/A", 0
    worst_day, worst_day_pct = "N/A", float('inf')
    for idx, scores in day_scores.items():
        avg = sum(scores) / len(scores)
        if avg > best_day_pct:
            best_day_pct, best_day = round(avg, 1), day_names[idx]
        if avg < worst_day_pct:
            worst_day_pct, worst_day = round(avg, 1), day_names[idx]
    if worst_day_pct == float('inf'):
        worst_day_pct = 0

    longest_streak = cur = 0
    for d in daily:
        if d["pct"] > 0:
            cur += 1
            longest_streak = max(longest_streak, cur)
        else:
            cur = 0

    user_doc = db.collection("users").document(uid).get()
    if user_doc.exists:
        longest_streak = max(longest_streak, user_doc.to_dict().get("longest_streak", 0))

    habits = list(db.collection("users").document(uid).collection("habits").stream())
    habit_streaks = []
    for h in habits:
        name = h.to_dict().get("name", "")
        streak = 0
        for i in range(365):
            day = str(today - timedelta(days=i))
            logs = list(
                db.collection("users").document(uid).collection("activity_logs")
                .where("log_date", "==", day).where("habit_name", "==", name).limit(1).stream()
            )
            if logs:
                streak += 1
            elif i == 0:
                continue
            else:
                break
        habit_streaks.append({"name": name, "streak": streak})
    habit_streaks.sort(key=lambda x: x["streak"], reverse=True)

    consistency_score = round(days_with_data / max(total_days, 1) * 100, 1)

    active_scores = [d["pct"] for d in daily if d["pct"] > 0]
    performance_score = round(sum(active_scores) / max(len(active_scores), 1), 1)

    top_habit = habit_streaks[0]["name"] if habit_streaks else None
    needs_improvement = habit_streaks[-1]["name"] if len(habit_streaks) > 1 else None

    last7 = daily[-7:] if len(daily) >= 7 else daily
    prev7 = daily[-14:-7] if len(daily) >= 14 else []
    last7_avg = round(sum(d["pct"] for d in last7) / max(len(last7), 1), 1)
    prev7_avg = round(sum(d["pct"] for d in prev7) / max(len(prev7), 1), 1) if prev7 else None
    trend = "up" if prev7_avg is not None and last7_avg > prev7_avg + 5 else \
            "down" if prev7_avg is not None and last7_avg < prev7_avg - 5 else "stable"

    date_range_label = (
        f"Last {total_days} day{'s' if total_days != 1 else ''}"
        if total_days <= 30
        else f"All-time ({total_days} days)"
    )

    return {
        "completion_rate": completion_rate,
        "best_day": best_day,
        "best_day_pct": best_day_pct,
        "worst_day": worst_day,
        "worst_day_pct": worst_day_pct,
        "longest_streak": longest_streak,
        "daily": daily,
        "habit_streaks": habit_streaks[:8],
        "consistency_score": consistency_score,
        "performance_score": performance_score,
        "top_habit": top_habit,
        "needs_improvement": needs_improvement,
        "trend": trend,
        "last7_avg": last7_avg,
        "prev7_avg": prev7_avg,
        "date_range_label": date_range_label,
        "total_days": total_days,
        "start_date": str(start_date),
        "end_date": str(today),
    }



@router.get("/analytics")
def enhanced_analytics(uid: str = Depends(get_uid), db=Depends(get_db)):
    today = date.today()

    four_weeks_ago = str(today - timedelta(days=27))
    weekly_summaries = list(
        db.collection("users").document(uid).collection("daily_summaries")
        .where("summary_date", ">=", four_weeks_ago)
        .order_by("summary_date")
        .stream()
    )
    score_map = {s.to_dict()["summary_date"]: s.to_dict() for s in weekly_summaries if "summary_date" in s.to_dict()}

    weeks = []
    for w in range(4):
        week_start = today - timedelta(days=27 - w * 7)
        week_scores = []
        week_minutes = 0
        for d in range(7):
            day_str = str(week_start + timedelta(days=d))
            entry = score_map.get(day_str, {})
            week_scores.append(entry.get("productivity_score", 0))
            week_minutes += entry.get("total_completed_minutes", 0)
        weeks.append({
            "week": f"Week {w + 1}",
            "start": str(week_start),
            "avg_score": round(sum(week_scores) / 7, 1),
            "total_minutes": week_minutes,
        })

    thirty_ago = str(today - timedelta(days=29))
    habits = list(db.collection("users").document(uid).collection("habits").stream())
    logs = list(
        db.collection("users").document(uid).collection("activity_logs")
        .where("log_date", ">=", thirty_ago).stream()
    )
    habit_targets = {h.to_dict().get("name"): h.to_dict().get("target_minutes", 60) for h in habits}
    habit_minutes: dict = {}
    for log in logs:
        d = log.to_dict()
        name = d.get("habit_name", "")
        habit_minutes[name] = habit_minutes.get(name, 0) + d.get("minutes_spent", 0)

    habit_ranking = []
    for name, target in habit_targets.items():
        done = habit_minutes.get(name, 0)
        score = round(min(done / max(target * 30, 1) * 100, 100), 1)
        habit_ranking.append({"name": name, "minutes": done, "score": score})
    habit_ranking.sort(key=lambda x: x["score"], reverse=True)

    last7_start = str(today - timedelta(days=6))
    last7_summaries = [score_map[d] for d in score_map if d >= last7_start]
    productivity_score = round(
        sum(s.get("productivity_score", 0) for s in last7_summaries) / max(len(last7_summaries), 1), 1
    )

    active_days = sum(1 for d, v in score_map.items() if v.get("total_completed_minutes", 0) > 0)
    window_days = min(len(score_map), 30) or 30
    consistency_score = round(active_days / window_days * 100, 1)

    return {
        "productivity_score": productivity_score,
        "consistency_score": consistency_score,
        "weekly_trends": weeks,
        "habit_ranking": habit_ranking,
        "active_days_last30": active_days,
    }



def calculate_xp_from_logs(uid: str, db, days_back: int = 90):
    """Calculate XP based on new gamification rules:
    - +10 XP per habit completed
    - +5 XP per partial progress
    - Additional XP from streaks and perfect days calculated separately
    """
    today = date.today()
    start_date = str(today - timedelta(days=days_back - 1))

    logs = list(
        db.collection("users").document(uid).collection("activity_logs")
        .where("log_date", ">=", start_date).stream()
    )

    habits = list(db.collection("users").document(uid).collection("habits").stream())
    habit_targets = {h.to_dict().get("name"): h.to_dict().get("target_minutes", 60) for h in habits}

    # Group logs by date and habit
    daily_progress = defaultdict(lambda: defaultdict(int))
    for log in logs:
        d = log.to_dict()
        log_date = d.get("log_date")
        habit_name = d.get("habit_name")
        minutes = d.get("minutes_spent", 0)
        daily_progress[log_date][habit_name] += minutes

    total_xp = 0

    # Calculate XP for each day
    for day_str, habits_done in daily_progress.items():
        day_xp = 0
        completed_count = 0
        partial_count = 0

        for habit_name, minutes in habits_done.items():
            target = habit_targets.get(habit_name, 60)
            if minutes >= target:
                day_xp += 10  # +10 XP for completed habit
                completed_count += 1
            elif minutes > 0:
                day_xp += 5  # +5 XP for partial progress
                partial_count += 1

        total_xp += day_xp

    return total_xp


@router.get("/analytics/xp-progress")
def xp_progress(uid: str = Depends(get_uid), db=Depends(get_db)):
    """XP based on new gamification rules. Level = floor(sqrt(XP / 50))."""

    xp = calculate_xp_from_logs(uid, db, days_back=90)

    # Get user streak data
    user_doc = db.collection("users").document(uid).get()
    streak, longest_streak = 0, 0
    if user_doc.exists:
        ud = user_doc.to_dict()
        streak = ud.get("streak", 0)
        longest_streak = ud.get("longest_streak", 0)

        # Add bonus XP from stored achievements if they exist
        achievements = ud.get("achievements", {})
        if achievements:
            xp += achievements.get("bonus_xp", 0)

    # Calculate level using new formula: level = floor(sqrt(XP / 50))
    level = int(math.floor(math.sqrt(xp / 50))) if xp > 0 else 0

    # Calculate XP needed for next level
    next_level = level + 1
    next_level_xp = next_level * next_level * 50
    xp_to_next = next_level_xp - xp

    return {
        "xp": xp,
        "level": level,
        "xp_to_next": xp_to_next,
        "next_level_xp": next_level_xp,
        "current_level_xp": level * level * 50,
        "streak": streak,
        "longest_streak": longest_streak
    }




ACHIEVEMENT_DEFINITIONS = [
    {
        "id": "first_habit",
        "name": "First Steps",
        "description": "Complete your first habit",
        "icon": "🌱",
        "xp_bonus": 20
    },
    {
        "id": "streak_3",
        "name": "Building Momentum",
        "description": "Maintain a 3-day streak",
        "icon": "🔥",
        "xp_bonus": 30
    },
    {
        "id": "streak_7",
        "name": "Week Warrior",
        "description": "Maintain a 7-day streak",
        "icon": "⚡",
        "xp_bonus": 50
    },
    {
        "id": "perfect_day",
        "name": "Perfect Day",
        "description": "Complete all habits in a single day",
        "icon": "⭐",
        "xp_bonus": 50
    },
    {
        "id": "xp_1000",
        "name": "XP Master",
        "description": "Reach 1000 XP",
        "icon": "💎",
        "xp_bonus": 100
    },
    {
        "id": "streak_30",
        "name": "Monthly Champion",
        "description": "Maintain a 30-day streak",
        "icon": "👑",
        "xp_bonus": 200
    },
]


def check_achievements(uid: str, db):
    """Check and unlock achievements for a user."""
    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()

    if not user_doc.exists:
        return []

    user_data = user_doc.to_dict()
    unlocked = user_data.get("achievements_unlocked", [])
    newly_unlocked = []

  
    xp_data = xp_progress(uid, db)
    xp = xp_data["xp"]
    streak = xp_data["streak"]

    if "first_habit" not in unlocked:
        logs = list(
            db.collection("users").document(uid).collection("activity_logs").limit(1).stream()
        )
        if logs:
            newly_unlocked.append("first_habit")


    if "streak_3" not in unlocked and streak >= 3:
        newly_unlocked.append("streak_3")
    if "streak_7" not in unlocked and streak >= 7:
        newly_unlocked.append("streak_7")
    if "streak_30" not in unlocked and streak >= 30:
        newly_unlocked.append("streak_30")


    if "xp_1000" not in unlocked and xp >= 1000:
        newly_unlocked.append("xp_1000")


    if "perfect_day" not in unlocked:
        today = str(date.today())
        logs = list(
            db.collection("users").document(uid).collection("activity_logs")
            .where("log_date", "==", today).stream()
        )
        habits = list(db.collection("users").document(uid).collection("habits").stream())

        if habits:
            habit_targets = {h.to_dict().get("name"): h.to_dict().get("target_minutes", 60) for h in habits}
            habit_progress = defaultdict(int)
            for log in logs:
                d = log.to_dict()
                habit_progress[d.get("habit_name")] += d.get("minutes_spent", 0)

            all_completed = all(
                habit_progress.get(name, 0) >= target
                for name, target in habit_targets.items()
            )
            if all_completed and len(habit_targets) > 0:
                newly_unlocked.append("perfect_day")

   
    if newly_unlocked:
        all_unlocked = list(set(unlocked + newly_unlocked))
        bonus_xp = sum(
            ach["xp_bonus"]
            for ach in ACHIEVEMENT_DEFINITIONS
            if ach["id"] in newly_unlocked
        )
        current_bonus = user_data.get("achievements", {}).get("bonus_xp", 0)

        user_ref.update({
            "achievements_unlocked": all_unlocked,
            "achievements": {
                "bonus_xp": current_bonus + bonus_xp,
                "last_checked": firestore.SERVER_TIMESTAMP
            }
        })

    return newly_unlocked


@router.get("/analytics/achievements")
def get_achievements(uid: str = Depends(get_uid), db=Depends(get_db)):
    """Get all achievements with unlock status."""
    user_doc = db.collection("users").document(uid).get()
    unlocked = []

    if user_doc.exists:
        unlocked = user_doc.to_dict().get("achievements_unlocked", [])

    achievements = []
    for ach in ACHIEVEMENT_DEFINITIONS:
        achievements.append({
            **ach,
            "unlocked": ach["id"] in unlocked
        })

    return {"achievements": achievements}


@router.post("/analytics/check-achievements")
def check_and_unlock_achievements(uid: str = Depends(get_uid), db=Depends(get_db)):
    """Check and unlock any new achievements for the user."""
    newly_unlocked = check_achievements(uid, db)

    unlocked_details = [
        ach for ach in ACHIEVEMENT_DEFINITIONS
        if ach["id"] in newly_unlocked
    ]

    return {
        "newly_unlocked": unlocked_details,
        "count": len(newly_unlocked)
    }
