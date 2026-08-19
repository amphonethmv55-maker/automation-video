import subprocess
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


app = FastAPI(
    title="Automation Video TTS API",
    version="3.0.0"
)


VOICE_DIR = Path("/voices")
OUTPUT_DIR = Path("/data/storage/audio")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class TTSRequest(BaseModel):
    character_id: str
    voice: str
    emotion: str
    text: str
    scene_id: int


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "tts-api",
        "provider": "piper-local"
    }


def get_voice_model(character_id: str) -> Path:
    character_id = character_id.lower()

    if character_id in {"hacker", "switch", "access-point", "user", "lan-cable", "cloud"}:
        return VOICE_DIR / "en_US-ryan-medium.onnx"

    return VOICE_DIR / "en_US-lessac-medium.onnx"


@app.post("/generate-voice")
def generate_voice(request: TTSRequest):
    model_path = get_voice_model(request.character_id)

    if not model_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Voice model not found: {model_path}"
        )

    filename = f"{request.character_id}_scene_{request.scene_id}.wav"
    output_path = OUTPUT_DIR / filename

    command = [
        "python",
        "-m",
        "piper",
        "-m",
        str(model_path),
        "-f",
        str(output_path),
        "--",
        request.text
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        output_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=500,
            detail=f"Piper failed: {result.stderr[-2000:]}"
        )

    if not output_path.exists():
        raise HTTPException(
            status_code=500,
            detail="Audio file was not created"
        )

    return {
        "status": "generated",
        "provider": "piper-local",
        "scene_id": request.scene_id,
        "character_id": request.character_id,
        "voice": request.voice,
        "emotion": request.emotion,
        "text": request.text,
        "audio_filename": filename,
        "audio_path": str(output_path),
        "size_bytes": output_path.stat().st_size
    }
