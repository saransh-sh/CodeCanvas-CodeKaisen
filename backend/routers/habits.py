from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from firebase_admin import firestore

from backend.database import get_db
from backend.auth import get_uid

router = APIRouter()


class HabitIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    category: Optional[str] = Field(None, max_length=50)
    target_minutes: int = Field(60, ge=1, le=1440)


class HabitEdit(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = Field(None, max_length=50)
    target_minutes: Optional[int] = Field(None, ge=1, le=1440)


@router.get("/habits")
def get_habits(uid: str = Depends(get_uid), db=Depends(get_db)):
    docs = db.collection("users").document(uid).collection("habits").stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


@router.post("/habits", status_code=201)
def add_habit(data: HabitIn, uid: str = Depends(get_uid), db=Depends(get_db)):
    habit_data = {
        "name": data.name,
        "category": data.category,
        "target_minutes": data.target_minutes,
        "created_at": firestore.SERVER_TIMESTAMP,
    }
    ref = db.collection("users").document(uid).collection("habits").add(habit_data)
    _, doc_ref = ref
    return {"id": doc_ref.id, "name": data.name, "category": data.category, "target_minutes": data.target_minutes}


@router.put("/habits/{hid}")
def edit_habit(hid: str, data: HabitEdit, uid: str = Depends(get_uid), db=Depends(get_db)):
    habit_ref = db.collection("users").document(uid).collection("habits").document(hid)
    if not habit_ref.get().exists:
        raise HTTPException(status_code=404, detail="habit not found")
    updates = data.model_dump(exclude_none=True)
    habit_ref.update(updates)
    updated = habit_ref.get().to_dict()
    return {"id": hid, **updated}


@router.delete("/habits/{hid}", status_code=204)
def remove_habit(hid: str, uid: str = Depends(get_uid), db=Depends(get_db)):
    habit_ref = db.collection("users").document(uid).collection("habits").document(hid)
    if not habit_ref.get().exists:
        raise HTTPException(status_code=404, detail="habit not found")
    habit_ref.delete()
