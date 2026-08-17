from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="Automation Video Script API",
    version="1.0.0"
)


class ScriptRequest(BaseModel):
    topic: str


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "script-api"
    }


@app.post("/generate")
def generate_script(request: ScriptRequest):
    return {
        "topic": request.topic,
        "status": "ready",
        "title": request.topic,
        "scenes": [
            {
                "scene_id": 1,
                "character": "Firewall",
                "dialogue": "Stop! This traffic looks suspicious.",
                "emotion": "alert",
                "camera": "medium_shot",
                "movement": "look_left",
                "duration": 4
            },
            {
                "scene_id": 2,
                "character": "Hacker",
                "dialogue": "Let's see if I can get through.",
                "emotion": "confident",
                "camera": "close_up",
                "movement": "lean_forward",
                "duration": 4
            },
            {
                "scene_id": 3,
                "character": "Firewall",
                "dialogue": "Access denied!",
                "emotion": "angry",
                "camera": "close_up",
                "movement": "shake_head",
                "duration": 3
            }
        ]
    }