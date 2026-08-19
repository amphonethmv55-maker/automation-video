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
        "animation_style": "firm",
        "asset_path": "/data/characters/firewall/base.png"
    },
    "switch": {
        "id": "switch",
        "name": "Switch",
        "personality": "organized, fast, helpful",
        "voice": "male_bright",
        "main_color": "gray",
        "animation_style": "energetic",
        "asset_path": "/data/characters/switch/base.png"
    },
    "access-point": {
        "id": "access-point",
        "name": "Access Point",
        "personality": "friendly, wireless, curious",
        "voice": "female_bright",
        "main_color": "white",
        "animation_style": "bouncy",
        "asset_path": "/data/characters/access-point/base.png"
    },
    "router": {
        "id": "router",
        "name": "Router",
        "personality": "wise, adventurous, reliable",
        "voice": "male_warm",
        "main_color": "black",
        "animation_style": "steady",
        "asset_path": "/data/characters/router/base.png"
    },
    "hacker": {
        "id": "hacker",
        "name": "Hacker",
        "personality": "sneaky, clever, playful",
        "voice": "male_sly",
        "main_color": "black",
        "animation_style": "sneaky",
        "asset_path": "/data/characters/hacker/base.png"
    },
    "sysadmin": {
        "id": "sysadmin",
        "name": "SysAdmin",
        "personality": "smart, calm, helpful",
        "voice": "male_clear",
        "main_color": "black",
        "animation_style": "calm",
        "asset_path": "/data/characters/sysadmin/base.png"
    },
    "user": {
        "id": "user",
        "name": "User",
        "personality": "curious, friendly, learning",
        "voice": "male_young",
        "main_color": "green",
        "animation_style": "curious",
        "asset_path": "/data/characters/user/base.png"
    },
    "lan-cable": {
        "id": "lan-cable",
        "name": "LAN Cable",
        "personality": "quiet, dependable, supportive",
        "voice": "male_bright",
        "main_color": "blue",
        "animation_style": "wavy",
        "asset_path": "/data/characters/lan-cable/base.png"
    },
    "server": {
        "id": "server",
        "name": "Server",
        "personality": "hardworking, stable, patient",
        "voice": "male_deep",
        "main_color": "dark_gray",
        "animation_style": "steady",
        "asset_path": "/data/characters/server/base.png"
    },
    "cloud": {
        "id": "cloud",
        "name": "Cloud",
        "personality": "cool, flexible, generous",
        "voice": "male_sly",
        "main_color": "white",
        "animation_style": "floaty",
        "asset_path": "/data/characters/cloud/base.png"
    }
}

class CharacterRequest(BaseModel):
    character: str


def character_key(value: str) -> str:
    return value.strip().lower().replace("_", "-").replace(" ", "-")

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "character-api"
    }

@app.post("/character")
def get_character(request: CharacterRequest):
    key = character_key(request.character)

    if key not in CHARACTERS:
        raise HTTPException(
            status_code=404,
            detail=f"Character '{request.character}' not found"
        )

    return CHARACTERS[key]


@app.get("/characters")
def list_characters():
    """Return the canonical roster used by scripts and workflows."""
    return {"status": "ok", "characters": list(CHARACTERS.values())}


@app.post("/character-asset")
def get_character_asset(request: CharacterRequest):
    """Resolve the checked-in PNG asset for one character.

    This is intentionally separate from the AI image service: Character Sheet
    assets are stable, so every scene keeps the same recognizable character.
    """
    key = character_key(request.character)
    character = CHARACTERS.get(key)
    if not character:
        raise HTTPException(status_code=404, detail=f"Character '{request.character}' not found")

    asset_path = character["asset_path"]
    from pathlib import Path
    if not Path(asset_path).exists():
        raise HTTPException(status_code=500, detail=f"Character asset is missing: {asset_path}")

    return {
        "status": "ready",
        "provider": "character-sheet",
        "scene_character": character["name"],
        "character_id": character["id"],
        "image_filename": Path(asset_path).name,
        "image_path": asset_path,
        "size_bytes": Path(asset_path).stat().st_size,
    }
