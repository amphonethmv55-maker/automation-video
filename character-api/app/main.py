from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="Automation Video Character API",
    version="1.0.0"
)

CHARACTERS = {
    "firewall": {
        "id": "firewall",
        "name": "Firewall",
        "personality": "strict, protective, confident",
        "voice": "male_deep",
        "main_color": "red",
        "animation_style": "firm"
    },
    "hacker": {
        "id": "hacker",
        "name": "Hacker",
        "personality": "sneaky, clever, playful",
        "voice": "male_sly",
        "main_color": "black",
        "animation_style": "sneaky"
    }
}

class CharacterRequest(BaseModel):
    character: str

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "character-api"
    }

@app.post("/character")
def get_character(request: CharacterRequest):
    key = request.character.strip().lower()

    if key not in CHARACTERS:
        raise HTTPException(
            status_code=404,
            detail=f"Character '{request.character}' not found"
        )

    return CHARACTERS[key]
