from fastapi import APIRouter, Depends, HTTPException
from backend.database import get_db
from backend.auth import get_uid

router = APIRouter()


def _get_bots_enabled(db) -> bool:
    doc = db.collection("config").document("leaderboard_settings").get()
    if doc.exists:
        return doc.to_dict().get("bots_enabled", True)
    return True


@router.post("/leaderboard/opt-in")
def leaderboard_opt_in(uid: str = Depends(get_uid), db=Depends(get_db)):
    from backend.routers.analytics import xp_progress

    user_doc = db.collection("users").document(uid).get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="user not found")

    user_data = user_doc.to_dict()
    display_name = user_data.get("display_name") or user_data.get("email", "Anonymous")

    xp_data = xp_progress(uid, db)
    xp = xp_data["xp"]
    streak = user_data.get("streak", 0)

    db.collection("leaderboard").document(uid).set({
        "uid": uid,
        "display_name": display_name,
        "xp": xp,
        "streak": streak,
        "is_dummy": False,
    })
    return {"status": "joined", "display_name": display_name, "xp": xp, "streak": streak}


@router.post("/leaderboard/opt-out")
def leaderboard_opt_out(uid: str = Depends(get_uid), db=Depends(get_db)):
    db.collection("leaderboard").document(uid).delete()
    return {"status": "left"}


@router.get("/leaderboard")
def get_leaderboard(uid: str = Depends(get_uid), db=Depends(get_db)):
    from backend.routers.analytics import xp_progress

    bots_enabled = _get_bots_enabled(db)

    entries = db.collection("leaderboard").order_by("xp", direction="DESCENDING").stream()

    result = []
    for doc in entries:
        data = doc.to_dict()
        if not bots_enabled and data.get("is_dummy", False):
            continue

        if not data.get("is_dummy", False):
            try:
                xp_data = xp_progress(doc.id, db)
                user_doc = db.collection("users").document(doc.id).get()
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    data["xp"] = xp_data["xp"]
                    data["streak"] = user_data.get("streak", 0)
                    db.collection("leaderboard").document(doc.id).update({
                        "xp": data["xp"],
                        "streak": data["streak"]
                    })
            except Exception:
                pass

        result.append({
            "display_name": data.get("display_name", "Anonymous"),
            "xp": data.get("xp", 0),
            "streak": data.get("streak", 0),
            "is_current_user": doc.id == uid,
        })
    return result


@router.get("/leaderboard/status")
def leaderboard_status(uid: str = Depends(get_uid), db=Depends(get_db)):
    doc = db.collection("leaderboard").document(uid).get()
    return {"joined": doc.exists}
