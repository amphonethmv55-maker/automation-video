import json
import math
import struct
import subprocess
import wave
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Automation Video Animation API", version="3.0.0")
ANIMATION_DIR = Path("/data/storage/animation")
ANIMATION_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = Path("/app/config/characters.json")


class AnimationRequest(BaseModel):
    scene_id: int
    character_id: str
    image_path: str | None = None
    audio_path: str
    emotion: str = "neutral"
    movement: str = "idle"


@app.get("/health")
def health():
    return {"status": "ok", "service": "animation-api", "engine": "ffmpeg-2d-rig-v3", "gpu_required": False, "mouth_animation": True, "character_rigs": 10}


def load_config(character_id: str) -> dict | None:
    if not CONFIG_PATH.exists():
        return None
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8")).get(character_id.lower())


def audio_levels(audio_path: Path, fps: int = 30) -> list[float]:
    values: list[float] = []
    try:
        with wave.open(str(audio_path), "rb") as wav:
            if wav.getsampwidth() != 2:
                return values
            channels, rate = wav.getnchannels(), wav.getframerate()
            batch = max(1, int(rate / fps))
            while raw := wav.readframes(batch):
                samples = struct.unpack("<" + "h" * (len(raw) // 2), raw)
                if channels > 1:
                    samples = samples[::channels]
                rms = math.sqrt(sum(sample * sample for sample in samples) / max(1, len(samples)))
                values.append(min(1.0, rms / 2500.0))
    except (wave.Error, OSError, struct.error):
        return []
    return values


def enabled_periods(levels: list[float], lower: float, upper: float | None = None) -> str:
    clauses, start = [], None
    for index, level in enumerate(levels):
        active = level >= lower and (upper is None or level < upper)
        if active and start is None:
            start = index
        if start is not None and (not active or index == len(levels) - 1):
            end = index + 1 if active and index == len(levels) - 1 else index
            clauses.append(f"between(t,{start / 30:.3f},{end / 30:.3f})")
            start = None
    return "+".join(clauses) if clauses else "0"


def motion_filter(emotion: str, movement: str) -> str:
    emotion, movement = emotion.lower(), movement.lower()
    if movement == "shake_head" or emotion == "angry":
        return "rotate='0.012*sin(12*t)':ow=iw:oh=ih:fillcolor=black"
    if movement == "lean_forward" or emotion == "confident":
        return "zoompan=z='min(zoom+0.0015,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30"
    if movement == "look_left" or emotion == "alert":
        return "zoompan=z='1.03':x='max(0,iw/2-(iw/zoom/2)-25*sin(on/18))':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30"
    return "zoompan=z='min(zoom+0.0005,1.04)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30"


def build_filter(config: dict, levels: list[float], emotion: str, movement: str) -> str:
    mouth = config["mouth"]
    x, y = mouth["x"], mouth["y"]
    sprite_width = mouth.get("sprite_width", 180)
    small = enabled_periods(levels, 0.08, 0.45)
    wide = enabled_periods(levels, 0.45)
    return (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black[base];"
        f"[2:v]scale={sprite_width}:-1[smallmouth];[3:v]scale={sprite_width}:-1[widemouth];"
        f"[base][smallmouth]overlay=x='main_w*{x}-overlay_w/2':y='main_h*{y}-overlay_h/2':enable='{small}'[small];"
        f"[small][widemouth]overlay=x='main_w*{x}-overlay_w/2':y='main_h*{y}-overlay_h/2':enable='{wide}',{motion_filter(emotion, movement)},format=yuv420p[v]"
    )


@app.post("/animate")
def animate(request: AnimationRequest):
    config = load_config(request.character_id)
    if not config:
        raise HTTPException(status_code=404, detail=f"Rig config not found: {request.character_id}")
    image_path = Path(request.image_path or config["asset_path"])
    audio_path = Path(request.audio_path)
    mouth_small, mouth_wide = Path(config["mouth_small_path"]), Path(config["mouth_wide_path"])
    for label, path in {"Image": image_path, "Audio": audio_path, "Small mouth sprite": mouth_small, "Wide mouth sprite": mouth_wide}.items():
        if not path.exists():
            raise HTTPException(status_code=400, detail=f"{label} not found: {path}")
    levels = audio_levels(audio_path)
    filename, output_path = f"{request.character_id}_scene_{request.scene_id}.mp4", ANIMATION_DIR / f"{request.character_id}_scene_{request.scene_id}.mp4"
    command = ["ffmpeg", "-y", "-loop", "1", "-i", str(image_path), "-i", str(audio_path), "-loop", "1", "-i", str(mouth_small), "-loop", "1", "-i", str(mouth_wide), "-filter_complex", build_filter(config, levels, request.emotion, request.movement), "-map", "[v]", "-map", "1:a:0", "-c:v", "libx264", "-preset", "veryfast", "-r", "30", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(output_path)]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr[-5000:])
    return {"status": "animated", "engine": "ffmpeg-2d-rig-v3", "scene_id": request.scene_id, "character_id": request.character_id, "emotion": request.emotion, "movement": request.movement, "rig_config_found": True, "audio_envelope_frames": len(levels), "mouth_animation": True, "animation_filename": filename, "animation_path": str(output_path), "size_bytes": output_path.stat().st_size}
