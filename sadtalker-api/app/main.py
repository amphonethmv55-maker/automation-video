import logging
import os
import shutil
import subprocess
import threading
import uuid
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("sadtalker-api")

app = FastAPI(
    title="Automation Video SadTalker API",
    version="1.0.0",
)

STORAGE_ROOT = Path(
    os.getenv("STORAGE_ROOT", "/data/storage")
).resolve()
SADTALKER_ROOT = Path(
    os.getenv("SADTALKER_ROOT", "/opt/sadtalker")
).resolve()
CHECKPOINT_DIR = Path(
    os.getenv("SADTALKER_CHECKPOINT_DIR", str(SADTALKER_ROOT / "checkpoints"))
).resolve()
OUTPUT_DIR = (STORAGE_ROOT / "sadtalker").resolve()
JOBS_DIR = (STORAGE_ROOT / "sadtalker-jobs").resolve()
INFERENCE_SCRIPT = SADTALKER_ROOT / "inference.py"
PROCESS_TIMEOUT_SECONDS = int(
    os.getenv("SADTALKER_PROCESS_TIMEOUT_SECONDS", "3600")
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
JOBS_DIR.mkdir(parents=True, exist_ok=True)

# CPU inference is memory intensive. Serialize jobs to keep the container stable.
inference_lock = threading.Lock()


class SadTalkerRequest(BaseModel):
    scene_id: int = Field(ge=1)
    character_id: str = Field(min_length=1, max_length=100)
    image_path: str
    audio_path: str
    size: Literal[256, 512] = 256
    preprocess: Literal["crop", "extcrop", "resize", "full", "extfull"] = "full"
    still: bool = False
    pose_style: int = Field(default=0, ge=0, le=45)
    expression_scale: float = Field(default=1.0, ge=0.1, le=3.0)
    force: bool = False


def path_inside_storage(raw_path: str, label: str) -> Path:
    path = Path(raw_path).resolve()

    try:
        path.relative_to(STORAGE_ROOT)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{label} must be inside {STORAGE_ROOT}",
        ) from exc

    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"{label} was not found",
        )

    return path


def safe_character_id(character_id: str) -> str:
    value = "".join(
        char for char in character_id.lower()
        if char.isalnum() or char in {"-", "_"}
    ).strip("-_")

    if not value:
        raise HTTPException(
            status_code=400,
            detail="character_id contains no safe filename characters",
        )

    return value


def readiness() -> dict:
    checkpoint_256 = CHECKPOINT_DIR / "SadTalker_V0.0.2_256.safetensors"
    checkpoint_512 = CHECKPOINT_DIR / "SadTalker_V0.0.2_512.safetensors"

    return {
        "source_available": INFERENCE_SCRIPT.is_file(),
        "checkpoint_256_available": checkpoint_256.is_file(),
        "checkpoint_512_available": checkpoint_512.is_file(),
    }


def is_ready(checks: dict) -> bool:
    return bool(
        checks["source_available"]
        and (
            checks["checkpoint_256_available"]
            or checks["checkpoint_512_available"]
        )
    )


@app.get("/health")
def health():
    checks = readiness()
    return {
        "status": "ok" if is_ready(checks) else "degraded",
        "service": "sadtalker-api",
        "engine": "sadtalker-v0.0.2",
        "device": "cpu",
        "serialized_jobs": True,
        "process_timeout_seconds": PROCESS_TIMEOUT_SECONDS,
        **checks,
    }


@app.post("/animate-face")
def animate_face(request: SadTalkerRequest):
    checks = readiness()

    requested_checkpoint = CHECKPOINT_DIR / (
        f"SadTalker_V0.0.2_{request.size}.safetensors"
    )

    if not checks["source_available"] or not requested_checkpoint.is_file():
        raise HTTPException(
            status_code=503,
            detail="SadTalker source or checkpoints are not ready",
        )

    image_path = path_inside_storage(request.image_path, "image_path")
    audio_path = path_inside_storage(request.audio_path, "audio_path")
    character_id = safe_character_id(request.character_id)
    output_filename = f"{character_id}_scene_{request.scene_id}_sadtalker.mp4"
    output_path = OUTPUT_DIR / output_filename

    if (
        not request.force
        and output_path.is_file()
        and output_path.stat().st_size > 0
    ):
        return {
            "status": "cached",
            "engine": "sadtalker-v0.0.2",
            "device": "cpu",
            "scene_id": request.scene_id,
            "character_id": character_id,
            "animation_filename": output_filename,
            "animation_path": str(output_path),
            "size_bytes": output_path.stat().st_size,
        }

    job_id = uuid.uuid4().hex
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=False)

    command = [
        "python",
        str(INFERENCE_SCRIPT),
        "--driven_audio",
        str(audio_path),
        "--source_image",
        str(image_path),
        "--checkpoint_dir",
        str(CHECKPOINT_DIR),
        "--result_dir",
        str(job_dir),
        "--cpu",
        "--size",
        str(request.size),
        "--preprocess",
        request.preprocess,
        "--pose_style",
        str(request.pose_style),
        "--expression_scale",
        str(request.expression_scale),
    ]

    if request.still:
        command.append("--still")

    try:
        with inference_lock:
            result = subprocess.run(
                command,
                cwd=str(SADTALKER_ROOT),
                capture_output=True,
                text=True,
                timeout=PROCESS_TIMEOUT_SECONDS,
                check=False,
            )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=504,
            detail="SadTalker inference timed out",
        ) from exc

    if result.returncode != 0:
        logger.error(
            "SadTalker failed for scene %s: %s",
            request.scene_id,
            result.stderr[-4000:],
        )
        raise HTTPException(
            status_code=500,
            detail="SadTalker inference failed; check container logs",
        )

    generated_videos = sorted(
        job_dir.rglob("*.mp4"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not generated_videos:
        raise HTTPException(
            status_code=500,
            detail="SadTalker completed without an MP4 output",
        )

    shutil.copy2(generated_videos[0], output_path)
    shutil.rmtree(job_dir, ignore_errors=True)

    return {
        "status": "animated",
        "engine": "sadtalker-v0.0.2",
        "device": "cpu",
        "scene_id": request.scene_id,
        "character_id": character_id,
        "source_image_path": str(image_path),
        "audio_path": str(audio_path),
        "preprocess": request.preprocess,
        "still": request.still,
        "animation_filename": output_filename,
        "animation_path": str(output_path),
        "size_bytes": output_path.stat().st_size,
    }
