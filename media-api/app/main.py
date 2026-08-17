import subprocess
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


app = FastAPI(
    title="Automation Video Media API",
    version="1.4.0"
)


FINAL_DIR = Path("/data/storage/final")
FINAL_DIR.mkdir(parents=True, exist_ok=True)


class MediaRequest(BaseModel):
    scene_id: int
    image_path: str
    animation_path: str
    audio_path: str
    subtitle_path: str
    duration: float


class ConcatRequest(BaseModel):
    title: str
    scenes: List[str]


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "media-api",
        "ffmpeg": True,
        "audio": True,
        "subtitles": True,
        "animation_input": True
    }


def get_duration(path: Path) -> float:
    command = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        return 0.0

    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


@app.post("/render-scene")
def render_scene(request: MediaRequest):
    animation_path = Path(request.animation_path)
    audio_path = Path(request.audio_path)
    subtitle_path = Path(request.subtitle_path)

    if not animation_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Animation not found: {animation_path}"
        )

    if not audio_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Audio not found: {audio_path}"
        )

    if not subtitle_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Subtitle not found: {subtitle_path}"
        )

    filename = f"scene_{request.scene_id}_final.mp4"
    output_path = FINAL_DIR / filename

    animation_duration = get_duration(animation_path)
    audio_duration = get_duration(audio_path)

    effective_duration = max(
        request.duration,
        animation_duration,
        audio_duration + 0.2
    )

    subtitle_filter = (
        f"subtitles={subtitle_path}:"
        "force_style='"
        "FontName=DejaVu Sans,"
        "FontSize=18,"
        "PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,"
        "BorderStyle=1,"
        "Outline=2,"
        "Shadow=1,"
        "Alignment=2,"
        "MarginV=100"
        "'"
    )

    video_filter = (
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,"
        f"{subtitle_filter},"
        "format=yuv420p"
    )

    command = [
        "ffmpeg",
        "-y",
        
        "-stream_loop", "-1",
        "-i", str(animation_path),
        "-i", str(audio_path),

        "-map", "0:v:0",
        "-map", "1:a:0",

        "-vf", video_filter,

        "-c:v", "libx264",
        "-preset", "veryfast",
        "-r", "30",
        "-pix_fmt", "yuv420p",

        "-c:a", "aac",
        "-b:a", "192k",
        "-af", "apad",

        "-t", str(effective_duration),
        "-movflags", "+faststart",

        str(output_path)
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"FFmpeg render failed: {result.stderr[-4000:]}"
        )

    if not output_path.exists():
        raise HTTPException(
            status_code=500,
            detail="FFmpeg completed but output file was not created"
        )

    return {
        "status": "rendered",
        "scene_id": request.scene_id,
        "animation_path": str(animation_path),
        "audio_path": str(audio_path),
        "subtitle_path": str(subtitle_path),
        "requested_duration": request.duration,
        "animation_duration": round(animation_duration, 3),
        "audio_duration": round(audio_duration, 3),
        "final_duration": round(effective_duration, 3),
        "render_filename": filename,
        "render_path": str(output_path),
        "size_bytes": output_path.stat().st_size
    }


@app.post("/concat-scenes")
def concat_scenes(request: ConcatRequest):
    filename = "final_video.mp4"
    output_path = FINAL_DIR / filename
    concat_file = FINAL_DIR / "concat_list.txt"

    if not request.scenes:
        raise HTTPException(
            status_code=400,
            detail="No scenes provided"
        )

    for scene in request.scenes:
        scene_path = Path(scene)

        if not scene_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Scene not found: {scene}"
            )

    with open(concat_file, "w", encoding="utf-8") as f:
        for scene in request.scenes:
            f.write(f"file '{scene}'\n")

    command = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        "-movflags", "+faststart",
        str(output_path)
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"FFmpeg concat failed: {result.stderr[-4000:]}"
        )

    return {
        "status": "rendered",
        "title": request.title,
        "scene_count": len(request.scenes),
        "scenes": request.scenes,
        "final_filename": filename,
        "final_path": str(output_path),
        "size_bytes": output_path.stat().st_size
    }
