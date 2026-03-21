from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from datetime import date
from firebase_admin import firestore

from backend.database import get_db
from backend.auth import get_uid

router = APIRouter()


class NoteIn(BaseModel):
    content: str = Field(..., max_length=10000)
    note_date: date


@router.get("/notes")
def get_notes(uid: str = Depends(get_uid), db=Depends(get_db)):
    docs = (
        db.collection("users").document(uid).collection("notes")
        .order_by("note_date", direction=firestore.Query.DESCENDING)
        .stream()
    )
    return [{"id": doc.id, "note_date": doc.id, **doc.to_dict()} for doc in docs]


@router.post("/notes", status_code=201)
def save_note(data: NoteIn, uid: str = Depends(get_uid), db=Depends(get_db)):
    note_ref = db.collection("users").document(uid).collection("notes").document(str(data.note_date))
    note_ref.set(
        {"content": data.content, "note_date": str(data.note_date), "updated_at": firestore.SERVER_TIMESTAMP},
        merge=True,
    )
    return {"id": str(data.note_date), "note_date": str(data.note_date), "content": data.content}


@router.delete("/notes/{nid}", status_code=204)
def delete_note(nid: str, uid: str = Depends(get_uid), db=Depends(get_db)):
    note_ref = db.collection("users").document(uid).collection("notes").document(nid)
    if note_ref.get().exists:
        note_ref.delete()
