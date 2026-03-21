import random
from fastapi import APIRouter, Depends
from backend.database import get_db
from backend.auth import get_admin_uid

router = APIRouter()

BOT_NAMES = [
    "Shadow_bot", "NightOwl_x", "ZenMaster99", "PixelPunk",
    "StarGazer_7", "CodeNinja_v2", "MoonWalker", "TurboHabit",
    "IronStreak", "PhoenixRise",
]


@router.get("/admin/bots/settings")
def get_bot_settings(uid: str = Depends(get_admin_uid), db=Depends(get_db)):
    doc = db.collection("config").document("leaderboard_settings").get()
    if doc.exists:
        return {"bots_enabled": doc.to_dict().get("bots_enabled", True)}
    return {"bots_enabled": True}


@router.put("/admin/bots/toggle")
def toggle_bots(uid: str = Depends(get_admin_uid), db=Depends(get_db)):
    ref = db.collection("config").document("leaderboard_settings")
    doc = ref.get()
    current = True
    if doc.exists:
        current = doc.to_dict().get("bots_enabled", True)
    new_val = not current
    ref.set({"bots_enabled": new_val}, merge=True)
    return {"bots_enabled": new_val}


@router.get("/admin/bots")
def list_bots(uid: str = Depends(get_admin_uid), db=Depends(get_db)):
    docs = db.collection("leaderboard").where("is_dummy", "==", True).stream()
    bots = []
    for d in docs:
        data = d.to_dict()
        bots.append({
            "uid": data.get("uid", d.id),
            "display_name": data.get("display_name", ""),
            "xp": data.get("xp", 0),
            "streak": data.get("streak", 0),
        })
    return bots


@router.post("/admin/bots/seed")
def seed_bots(uid: str = Depends(get_admin_uid), db=Depends(get_db)):
    created = []
    for i, name in enumerate(BOT_NAMES, start=1):
        bot_uid = f"bot_{i}"
        entry = {
            "uid": bot_uid,
            "display_name": name,
            "xp": random.randint(200, 3000),
            "streak": random.randint(1, 50),
            "is_dummy": True,
        }
        db.collection("leaderboard").document(bot_uid).set(entry)
        created.append(entry)
    return {"created": len(created), "bots": created}
