from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pathlib import Path
import subprocess
import json
import wave
import math
import struct


app = FastAPI(
    title="Automation Video Animation API",
    version="2.2.0"
)

ANIMATION_DIR = Path("/data/storage/animation")
ANIMATION_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = Path("/app/config/characters.json")


class AnimationRequest(BaseModel):
    scene_id: int
    character_id: str
    image_path: str
    audio_path: str
    emotion: str
    movement: str


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "animation-api",
        "engine": "ffmpeg-2d-rig-v2",
        "gpu_required": False,
        "mouth_animation": True,
        "blink": True
    }


def load_character_config(character_id: str):
    if not CONFIG_PATH.exists():
        return None

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get(character_id.lower())


def get_audio_envelope(audio_path: Path, fps: int = 30):
    values = []

    try:
        with wave.open(str(audio_path), "rb") as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            total_frames = wav.getnframes()

            if sample_width != 2:
                return values

            samples_per_video_frame = max(
                1,
                int(sample_rate / fps)
            )

            while wav.tell() < total_frames:
                raw = wav.readframes(samples_per_video_frame)

                if not raw:
                    break

                count = len(raw) // 2

                samples = struct.unpack(
                    "<" + "h" * count,
                    raw
                )

                if channels > 1:
                    samples = samples[::channels]

                if not samples:
                    values.append(0.0)
                    continue

                rms = math.sqrt(
                    sum(float(s) * float(s) for s in samples)
                    / len(samples)
                )

                normalized = min(
                    1.0,
                    rms / 2500.0
                )

                values.append(normalized)

    except Exception:
        return []

    return values


def make_mouth_expression(envelope):
    if not envelope:
        return "0"

    sections = []

    for i, level in enumerate(envelope):
        start = i / 30.0
        end = (i + 1) / 30.0

        level = max(
            0.0,
            min(1.0, level)
        )

        if level > 0.08:
            sections.append(
                f"if(between(t,{start:.3f},{end:.3f}),"
                f"{level:.3f},"
            )

    if not sections:
        return "0"

    return (
        "".join(sections)
        + "0"
        + ")" * len(sections)
    )


def build_base_motion(emotion: str, movement: str):
    emotion = (emotion or "").lower()
    movement = (movement or "").lower()

    if movement == "shake_head" or emotion == "angry":
        return (
            "rotate='0.015*sin(12*t)':"
            "ow=iw:oh=ih:"
            "fillcolor=black"
        )

    if movement == "lean_forward" or emotion == "confident":
        return (
            "zoompan="
            "z='min(zoom+0.0015,1.10)':"
            "x='iw/2-(iw/zoom/2)':"
            "y='ih/2-(ih/zoom/2)':"
            "d=1:s=1080x1920:fps=30"
        )

    if movement == "look_left":
        return (
            "zoompan="
            "z='1.04':"
            "x='max(0,iw/2-(iw/zoom/2)-40*sin(on/20))':"
            "y='ih/2-(ih/zoom/2)':"
            "d=1:s=1080x1920:fps=30"
        )

    if emotion == "alert":
        return (
            "zoompan="
            "z='1.03+0.01*sin(on/8)':"
            "x='iw/2-(iw/zoom/2)':"
            "y='ih/2-(ih/zoom/2)':"
            "d=1:s=1080x1920:fps=30"
        )

    return (
        "zoompan="
        "z='min(zoom+0.0005,1.04)':"
        "x='iw/2-(iw/zoom/2)':"
        "y='ih/2-(ih/zoom/2)':"
        "d=1:s=1080x1920:fps=30"
    )


def build_filter(
    emotion: str,
    movement: str,
    character_config,
    envelope
):
    filters = []

    #
    # RIG FIRST — coordinates are based on source image
    #

    if character_config:
        mouth = character_config.get("mouth")

        if mouth:
            mouth_expr = make_mouth_expression(envelope)

            x = mouth["x"]
            y = mouth["y"]
            w = mouth["w"]
            h = mouth["h"]

            max_open = max(
                12,
                int(h * 0.70)
            )

            filters.append(
                "drawbox="
                f"x={x}:"
                f"y='{y}+({h}/2)-(({max_open})*({mouth_expr})/2)':"
                f"w={w}:"
                f"h='max(2,{max_open}*({mouth_expr}))':"
                "color=black@0.85:"
                "t=fill"
            )

        #
        # Blink = short horizontal eyelid lines
        #
        for eye_name in ["left_eye", "right_eye"]:
            eye = character_config.get(eye_name)

            if not eye:
                continue

            x = eye["x"]
            y = eye["y"]
            w = eye["w"]
            h = eye["h"]

            line_h = max(
                5,
                int(h * 0.06)
            )

            filters.append(
                "drawbox="
                f"x={x}:"
                f"y={y + int(h / 2)}:"
                f"w={w}:"
                f"h={line_h}:"
                "color=black@0.90:"
                "t=fill:"
                "enable='lt(mod(t,3.4),0.10)'"
            )

    #
    # THEN scale / crop / motion
    #
    filters.append(
        "scale="
        "1200:2134:"
        "force_original_aspect_ratio=increase"
    )

    filters.append(
        "crop=1080:1920"
    )

    filters.append(
        build_base_motion(
            emotion,
            movement
        )
    )

    filters.append(
        "format=yuv420p"
    )

    return ",".join(filters)


@app.post("/animate")
def animate(request: AnimationRequest):
    image_path = Path(request.image_path)
    audio_path = Path(request.audio_path)

    if not image_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Image not found: {request.image_path}"
        )

    if not audio_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Audio not found: {request.audio_path}"
        )

    character_config = load_character_config(
        request.character_id
    )

    envelope = get_audio_envelope(
        audio_path,
        fps=30
    )

    video_filter = build_filter(
        request.emotion,
        request.movement,
        character_config,
        envelope
    )

    filename = (
        f"{request.character_id}_scene_"
        f"{request.scene_id}.mp4"
    )

    output_path = ANIMATION_DIR / filename

    cmd = [
        "ffmpeg",
        "-y",

        "-loop", "1",
        "-i", str(image_path),

        "-i", str(audio_path),

        "-vf", video_filter,

        "-c:v", "libx264",
        "-preset", "veryfast",
        "-r", "30",
        "-pix_fmt", "yuv420p",

        "-c:a", "aac",
        "-b:a", "128k",

        "-shortest",
        "-movflags", "+faststart",

        str(output_path)
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=result.stderr[-5000:]
        )

    return {
        "status": "animated",
        "engine": "ffmpeg-2d-rig-v2",
        "scene_id": request.scene_id,
        "character_id": request.character_id,
        "emotion": request.emotion,
        "movement": request.movement,
        "rig_config_found": character_config is not None,
        "audio_envelope_frames": len(envelope),
        "mouth_animation": (
            character_config is not None
            and character_config.get("mouth") is not None
        ),
        "blink": (
            character_config is not None
        ),
        "animation_filename": filename,
        "animation_path": str(output_path),
        "size_bytes": output_path.stat().st_size
    }
