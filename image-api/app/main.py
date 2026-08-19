import os
import time
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from google import genai
from google.genai import types


app = FastAPI(
    title="Automation Video Image API",
    version="3.0.0"
)

# ---------- Providers ----------
IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "cloudflare").lower()

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_IMAGE_MODEL = os.getenv(
    "GEMINI_IMAGE_MODEL",
    "gemini-2.5-flash-image"
)

# Cloudflare
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_IMAGE_MODEL = os.getenv(
    "CLOUDFLARE_IMAGE_MODEL",
    "@cf/black-forest-labs/flux-2-dev"
)
CLOUDFLARE_REQUEST_TIMEOUT = int(
    os.getenv("CLOUDFLARE_REQUEST_TIMEOUT", "300")
)
CLOUDFLARE_MAX_ATTEMPTS = int(
    os.getenv("CLOUDFLARE_MAX_ATTEMPTS", "3")
)

OUTPUT_DIR = Path("/data/storage/images")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class ImageRequest(BaseModel):
    prompt: str
    filename: str
    character_id: str
    scene_id: int
    force: bool = False


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "image-api",
        "provider": IMAGE_PROVIDER,
        "gemini_model": GEMINI_IMAGE_MODEL,
        "cloudflare_model": CLOUDFLARE_IMAGE_MODEL,
        "gemini_configured": bool(GEMINI_API_KEY),
        "cloudflare_configured": bool(CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID),
        "cloudflare_timeout_seconds": CLOUDFLARE_REQUEST_TIMEOUT,
        "cloudflare_max_attempts": CLOUDFLARE_MAX_ATTEMPTS,
    }


def get_output_path(filename: str) -> Path:
    safe_filename = Path(filename).name
    if not safe_filename.lower().endswith(".png"):
        safe_filename += ".png"

    return OUTPUT_DIR / safe_filename


def save_image_bytes(filename: str, image_bytes: bytes) -> Path:
    output_path = get_output_path(filename)

    with open(output_path, "wb") as f:
        f.write(image_bytes)

    return output_path


def generate_with_gemini(prompt: str) -> bytes:
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY is not configured"
        )

    client = genai.Client(api_key=GEMINI_API_KEY)

    response = client.models.generate_content(
        model=GEMINI_IMAGE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"]
        )
    )

    image_bytes = None

    for candidate in response.candidates or []:
        if not candidate.content:
            continue

        for part in candidate.content.parts or []:
            if part.inline_data and part.inline_data.data:
                image_bytes = part.inline_data.data
                break

        if image_bytes:
            break

    if not image_bytes:
        raise HTTPException(
            status_code=502,
            detail="Gemini returned no image"
        )

    return image_bytes


def generate_with_cloudflare(prompt: str) -> bytes:
    import base64

    if not CLOUDFLARE_API_TOKEN or not CLOUDFLARE_ACCOUNT_ID:
        raise HTTPException(
            status_code=500,
            detail="CLOUDFLARE_API_TOKEN or CLOUDFLARE_ACCOUNT_ID is not configured"
        )

    url = (
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{CLOUDFLARE_ACCOUNT_ID}/ai/run/{CLOUDFLARE_IMAGE_MODEL}"
    )

    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Accept": "application/json",
    }

    files = {
        "prompt": (None, prompt),
    }

    response = None

    for attempt in range(1, CLOUDFLARE_MAX_ATTEMPTS + 1):
        try:
            response = requests.post(
                url,
                headers=headers,
                files=files,
                timeout=(10, CLOUDFLARE_REQUEST_TIMEOUT)
            )
        except requests.Timeout:
            if attempt == CLOUDFLARE_MAX_ATTEMPTS:
                raise HTTPException(
                    status_code=504,
                    detail=(
                        "Cloudflare image generation timed out after "
                        f"{CLOUDFLARE_MAX_ATTEMPTS} attempts"
                    )
                )

            time.sleep(min(2 ** attempt, 10))
            continue
        except requests.RequestException as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Cloudflare connection failed: {exc.__class__.__name__}"
            )

        if response.status_code == 200:
            break

        if (
            response.status_code in {429, 500, 502, 503, 504}
            and attempt < CLOUDFLARE_MAX_ATTEMPTS
        ):
            time.sleep(min(2 ** attempt, 10))
            continue

        raise HTTPException(
            status_code=502,
            detail=(
                "Cloudflare image generation failed with status "
                f"{response.status_code}"
            )
        )

    if response is None:
        raise HTTPException(
            status_code=502,
            detail="Cloudflare image generation returned no response"
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Cloudflare image generation failed with status {response.status_code}"
        )

    content_type = response.headers.get("content-type", "").lower()

    # FLUX may return:
    # {"result":{"image":"BASE64..."}}
    if "application/json" in content_type or response.content.lstrip().startswith(b"{"):
        try:
            payload = response.json()
        except ValueError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Cloudflare returned invalid JSON: {exc}"
            )

        image_b64 = payload.get("result", {}).get("image")

        if not image_b64:
            raise HTTPException(
                status_code=502,
                detail=f"Cloudflare response does not contain result.image: {payload}"
            )

        # Support possible data:image/...;base64,... format
        if image_b64.startswith("data:") and "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]

        try:
            return base64.b64decode(image_b64)
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to decode Cloudflare image Base64: {exc}"
            )

    # Fallback in case a model returns raw image bytes directly
    return response.content


@app.post("/generate-image")
def generate_image(request: ImageRequest):
    try:
        existing_path = get_output_path(request.filename)

        if (
            not request.force
            and existing_path.exists()
            and existing_path.stat().st_size > 0
        ):
            return {
                "status": "cached",
                "provider": IMAGE_PROVIDER,
                "model": (
                    CLOUDFLARE_IMAGE_MODEL
                    if IMAGE_PROVIDER == "cloudflare"
                    else GEMINI_IMAGE_MODEL
                ),
                "scene_id": request.scene_id,
                "character_id": request.character_id,
                "image_filename": existing_path.name,
                "image_path": str(existing_path),
                "size_bytes": existing_path.stat().st_size
            }

        if IMAGE_PROVIDER == "cloudflare":
            image_bytes = generate_with_cloudflare(request.prompt)
            provider_used = "cloudflare"
            model_used = CLOUDFLARE_IMAGE_MODEL

        elif IMAGE_PROVIDER == "gemini":
            image_bytes = generate_with_gemini(request.prompt)
            provider_used = "gemini"
            model_used = GEMINI_IMAGE_MODEL

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported IMAGE_PROVIDER: {IMAGE_PROVIDER}"
            )

        output_path = save_image_bytes(request.filename, image_bytes)

        return {
            "status": "generated",
            "provider": provider_used,
            "model": model_used,
            "scene_id": request.scene_id,
            "character_id": request.character_id,
            "image_filename": output_path.name,
            "image_path": str(output_path),
            "size_bytes": output_path.stat().st_size
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Image generation failed: {str(e)}"
        )
