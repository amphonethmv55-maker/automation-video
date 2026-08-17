from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel


app = FastAPI(
    title="Automation Video Subtitle API",
    version="2.0.0"
)


OUTPUT_DIR = Path("/data/storage/subtitles")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class SubtitleRequest(BaseModel):
    scene_id: int
    text: str
    duration: float


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "subtitle-api"
    }


def format_srt_time(seconds: float) -> str:
    total_ms = int(seconds * 1000)

    hours = total_ms // 3_600_000
    total_ms %= 3_600_000

    minutes = total_ms // 60_000
    total_ms %= 60_000

    secs = total_ms // 1000
    millis = total_ms % 1000

    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


@app.post("/generate-subtitle")
def generate_subtitle(request: SubtitleRequest):
    filename = f"scene_{request.scene_id}.srt"
    output_path = OUTPUT_DIR / filename

    start_time = "00:00:00,000"
    end_time = format_srt_time(request.duration)

    srt_content = (
        "1\n"
        f"{start_time} --> {end_time}\n"
        f"{request.text}\n"
    )

    output_path.write_text(
        srt_content,
        encoding="utf-8"
    )

    return {
        "status": "generated",
        "scene_id": request.scene_id,
        "text": request.text,
        "duration": request.duration,
        "subtitle_filename": filename,
        "subtitle_path": str(output_path),
        "size_bytes": output_path.stat().st_size
    }