FROM python:3.10-slim

WORKDIR /app

RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' \
        /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       ca-certificates \
       ffmpeg \
       libgl1 \
       libglib2.0-0 \
       libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir \
      torch==2.0.1+cpu \
      torchvision==0.15.2+cpu \
      torchaudio==2.0.2+cpu \
      --extra-index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# SadTalker/librosa still imports pkg_resources, which setuptools 81+ removed.
RUN pip install --no-cache-dir setuptools==80.9.0

COPY app ./app

# SadTalker resolves these model folders relative to its working directory,
# while FFmpeg also needs that directory to be writable for a temporary MP4.
RUN ln -s /opt/sadtalker/gfpgan /app/gfpgan \
    && ln -s /opt/sadtalker/checkpoints /app/checkpoints

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
