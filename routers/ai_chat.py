from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import date
import logging
import httpx

from backend.database import get_db
from backend import config
from backend.auth import get_uid

logger = logging.getLogger(__name__)

router = APIRouter()

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "arcee-ai/trinity-large-preview:free"


class ChatIn(BaseModel):
    message: str


def _build_prompt(habit_names: list, target_mins: int, done_mins: int, message: str) -> str:
    return f"""You are Kaizen AI, a friendly productivity assistant.
Today's user data:
- Habits: {habit_names}
- Target time: {target_mins} minutes
- Time completed so far: {done_mins} minutes

User question: {message}

Give a helpful and encouraging response."""


def _try_openrouter(prompt: str) -> str:
    logger.info("Attempting OpenRouter API call (model: %s)", OPENROUTER_MODEL)
    try:
        resp = httpx.post(
            OPENROUTER_API_URL,
            headers={
                "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENROUTER_MODEL,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info("OpenRouter API call succeeded")
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning("OpenRouter API error: %s", str(e))
        raise


@router.get("/ai/providers")
def ai_providers():
    logger.info("AI providers check - OpenRouter: %s", bool(config.OPENROUTER_API_KEY))
    return {
        "openrouter": bool(config.OPENROUTER_API_KEY),
    }


@router.post("/ai/chat")
def chat_with_ai(data: ChatIn, uid: str = Depends(get_uid), db=Depends(get_db)):
    logger.info("AI chat request from user %s", uid)

    if not config.OPENROUTER_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="No AI provider configured. Set OPENROUTER_API_KEY in your .env file.",
        )

    today = date.today()

    logs = list(
        db.collection("users").document(uid).collection("activity_logs")
        .where("log_date", "==", str(today)).stream()
    )
    habits = list(db.collection("users").document(uid).collection("habits").stream())

    target_mins = sum(h.to_dict().get("target_minutes", 0) for h in habits)
    done_mins = sum(l.to_dict().get("minutes_spent", 0) for l in logs)
    habit_names = [h.to_dict().get("name") for h in habits]
    logger.debug("Context: %d habits, %d target mins, %d done mins", len(habit_names), target_mins, done_mins)

    prompt = _build_prompt(habit_names, target_mins, done_mins, data.message)

    try:
        text = _try_openrouter(prompt)
        return {"response": text, "provider": "openrouter"}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OpenRouter API error: {str(e)}")