import json
import os
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(
    title="Automation Video Script API",
    version="2.0.0"
)

CHARACTERS = ["Firewall", "Switch", "Access Point", "Router", "Hacker", "SysAdmin", "User", "LAN Cable", "Server", "Cloud"]


class Scene(BaseModel):
    scene_id: int
    character: str
    dialogue: str
    emotion: str = "neutral"
    camera: str = "medium_shot"
    movement: str = "idle"
    duration: int = Field(default=4, ge=2, le=12)

class ScriptRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=300)
    language: Literal["th", "en"] = "th"
    scene_count: int = Field(default=3, ge=2, le=10)


def fallback_script(request: ScriptRequest) -> list[dict]:
    """Useful offline fallback; dynamic, but deliberately not labelled as AI."""
    topic = request.topic.strip()
    pool = ["SysAdmin", "Firewall", "Router", "Switch", "Access Point", "Server", "Cloud", "LAN Cable", "User", "Hacker"]
    lines = ([
        f"วันนี้เราจะอธิบายเรื่อง {topic} แบบเข้าใจง่ายครับ",
        f"ถ้าเข้าใจ {topic} เราจะแก้ปัญหาระบบได้เร็วขึ้น",
        f"{topic} ต้องทำงานร่วมกันอย่างเป็นระบบครับ",
        "ตรวจสอบทีละขั้น แล้วระบบจะปลอดภัยและเสถียรขึ้นครับ",
    ] if request.language == "th" else [
        f"Let's explain {topic} in a simple way.",
        f"Understanding {topic} helps solve problems faster.",
        f"Every part of {topic} must work together.",
        "Check each step and keep the system secure and stable.",
    ])
    movements = ["look_left", "lean_forward", "idle", "shake_head"]
    emotions = ["alert", "confident", "happy", "serious"]
    return [Scene(
        scene_id=index + 1,
        character=pool[index % len(pool)],
        dialogue=lines[index % len(lines)],
        emotion=emotions[index % len(emotions)],
        camera="close_up" if index % 2 else "medium_shot",
        movement=movements[index % len(movements)],
        duration=4,
    ).model_dump() for index in range(request.scene_count)]


def gemini_script(request: ScriptRequest) -> list[dict]:
    from google import genai
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    prompt = f'''Create exactly {request.scene_count} concise educational cartoon scenes about: {request.topic}.
Language: {request.language}. Allowed characters: {", ".join(CHARACTERS)}.
Return JSON only: an array of objects with scene_id, character, dialogue, emotion,
camera (medium_shot or close_up), movement (idle, look_left, lean_forward, shake_head), duration (2-12).'''
    response = client.models.generate_content(
        model=os.getenv("GEMINI_SCRIPT_MODEL", "gemini-2.0-flash"),
        contents=prompt,
        config={"response_mime_type": "application/json"},
    )
    payload = json.loads(response.text)
    if not isinstance(payload, list) or len(payload) != request.scene_count:
        raise ValueError("Gemini returned an invalid scene list")
    return [Scene(**scene).model_dump() for scene in payload]


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "script-api",
        "ai_provider": "gemini" if os.getenv("GEMINI_API_KEY") else "offline-dynamic-fallback",
        "ai_configured": bool(os.getenv("GEMINI_API_KEY")),
    }


@app.post("/generate")
def generate_script(request: ScriptRequest):
    provider = "offline-dynamic-fallback"
    note = "GEMINI_API_KEY is not configured"
    scenes = fallback_script(request)
    if os.getenv("GEMINI_API_KEY"):
        try:
            scenes = gemini_script(request)
            provider, note = "gemini", None
        except Exception as exc:
            note = f"Gemini unavailable; using offline fallback: {str(exc)[:250]}"

    result = {
        "topic": request.topic.strip(),
        "status": "ready",
        "title": request.topic.strip(),
        "provider": provider,
        "scenes": scenes,
    }
    if note:
        result["provider_note"] = note
    return result
