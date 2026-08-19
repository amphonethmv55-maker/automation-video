# Automation Video

ระบบสร้างวิดีโออัตโนมัติแบบ microservices โดยใช้ FastAPI, FFmpeg, Piper TTS, n8n, PostgreSQL และ Redis แต่ละขั้นตอนของการสร้างวิดีโอแยกเป็น API และใช้โฟลเดอร์ `storage/` ร่วมกันสำหรับส่งต่อไฟล์ระหว่างบริการ

## ภาพรวมการทำงาน

```text
หัวข้อ
  -> Script API สร้างฉากและบทพูด
  -> Character API เลือกข้อมูลตัวละคร
  -> Image API สร้างภาพ
  -> TTS API สร้างเสียงพูด
  -> Animation API สร้างภาพเคลื่อนไหว
  -> Subtitle API สร้างคำบรรยาย
  -> Media API รวมภาพ เสียง และคำบรรยาย
  -> วิดีโอสำเร็จใน storage/final/
```

n8n ทำหน้าที่ควบคุมลำดับงานและเรียก API แต่ละบริการ

## โครงสร้างโปรเจกต์

```text
automation-video/
├── animation-api/       สร้าง animation ด้วย FFmpeg
├── character-api/       จัดการข้อมูลตัวละคร
├── image-api/           สร้างภาพผ่าน Cloudflare AI หรือ Gemini
├── script-api/          สร้างโครงเรื่องและฉาก
├── tts-api/             สร้างเสียงด้วย Piper TTS
├── subtitle-api/        สร้างไฟล์ SRT
├── media-api/           render และรวมวิดีโอ
├── publish-api/         พื้นที่สำหรับระบบเผยแพร่ในอนาคต
├── prompts/             prompt templates
├── characters/          ข้อมูลและ asset ของตัวละคร
├── infrastructure/      infrastructure configuration
├── n8n/                 ข้อมูล n8n และ workflow exports
├── storage/             ไฟล์ที่ระบบสร้างระหว่างทำงาน (ไม่เข้า Git)
├── docker-compose.yml   รายการ services
├── .env                 ค่าลับของเครื่อง (ไม่เข้า Git)
└── .gitignore
```

## Services และ Ports

| Service | URL | หน้าที่ |
|---|---|---|
| n8n | `http://localhost:5678` | จัดการ workflow |
| script-api | `http://localhost:8000` | สร้าง script |
| character-api | `http://localhost:8001` | ข้อมูลตัวละคร |
| image-api | `http://localhost:8002` | สร้างภาพ |
| tts-api | `http://localhost:8003` | สร้างเสียง |
| animation-api | `http://localhost:8004` | สร้าง animation |
| subtitle-api | `http://localhost:8005` | สร้าง subtitle |
| media-api | `http://localhost:8006` | render และรวมวิดีโอ |
| sadtalker-api | `http://localhost:8007` | สร้าง talking-face animation ด้วย SadTalker |

PostgreSQL และ Redis ใช้งานภายใน Docker network และไม่ได้เปิด port ออกสู่ host

## สิ่งที่ต้องติดตั้ง

- Windows 10/11 พร้อม PowerShell
- Docker Desktop ที่เปิดใช้งาน Docker Compose
- RAM อย่างน้อย 8 GB
- พื้นที่ว่างสำหรับ Docker images, AI models และวิดีโอ

ไม่จำเป็นต้องติดตั้ง Python หรือ FFmpeg บน Windows เพราะแต่ละ service ติดตั้ง dependency ภายใน Docker image

## การตั้งค่า

1. Clone repository และเข้าโฟลเดอร์โปรเจกต์

```powershell
git clone <repository-url>
cd automation-video
```

2. สร้างไฟล์ `.env` และกรอกค่าที่ใช้กับ environment ของเครื่อง

```powershell
notepad .env
```

3. กำหนดค่า PostgreSQL, n8n และผู้ให้บริการสร้างภาพ ห้าม commit ไฟล์ `.env` หรือค่าลับขึ้น Git

## Development และ Production

โปรเจกต์ใช้ GitHub เป็นตัวกลางสำหรับนำโค้ดจาก Development ไป Production:

```text
Development Server (192.168.126.128)
VS Code + Docker + n8n สำหรับพัฒนาและทดสอบ
        |
        | git push origin develop
        v
GitHub: amphonethmv55-maker/automation-video
        |
        | merge develop -> main
        | git pull origin main
        v
Production Server (192.168.20.193)
Docker Compose + n8n + APIs สำหรับใช้งานจริง
```

กำหนดหน้าที่ branch ดังนี้:

- `develop` ใช้สำหรับพัฒนาและทดสอบบน `192.168.126.128`
- `main` ใช้สำหรับ version ที่ผ่านการทดสอบและพร้อม deploy ไป `192.168.20.193`

ไฟล์ `.env` ไม่ถูกส่งผ่าน GitHub แต่ละ Server ต้องมีไฟล์ของตัวเอง:

```dotenv
# Development Server
N8N_HOST=192.168.126.128
N8N_PROTOCOL=http
N8N_SECURE_COOKIE=false
```

```dotenv
# Production Server (ใช้ HTTP ภายใน LAN เท่านั้น)
N8N_HOST=192.168.20.193
N8N_PROTOCOL=http
N8N_SECURE_COOKIE=false
```

### Development workflow

```powershell
git switch develop
git pull origin develop

# แก้โค้ดและทดสอบให้ผ่านก่อน
docker compose up -d --build
docker compose ps

git add .
git commit -m "Describe the development change"
git push origin develop
```

### Production deployment

หลังจาก review และ merge `develop` เข้า `main` แล้ว ให้รันบน Production Server:

```powershell
git switch main
git pull origin main
docker compose up -d --build
docker compose ps
```

ห้ามแก้ source code โดยตรงบน Production Server เพราะการแก้จะไม่ถูกบันทึกกลับ GitHub และอาจถูกเขียนทับในการ deploy ครั้งต่อไป

ค่าหลักที่ระบบใช้ประกอบด้วย:

```dotenv
TZ=Asia/Bangkok
POSTGRES_DB=automation
POSTGRES_USER=automation
POSTGRES_PASSWORD=change-me

N8N_ENCRYPTION_KEY=change-me-to-a-long-random-value
N8N_HOST=localhost
N8N_PORT=5678
N8N_PROTOCOL=http
N8N_SECURE_COOKIE=false

REDIS_HOST=redis
REDIS_PORT=6379

IMAGE_PROVIDER=cloudflare
CLOUDFLARE_ACCOUNT_ID=
CLOUDFLARE_API_TOKEN=
CLOUDFLARE_IMAGE_MODEL=@cf/black-forest-labs/flux-2-dev
```

## TTS Voice Models

ไฟล์ `.onnx` เป็น model binary และไม่ถูกเก็บใน Git ต้องวางไฟล์ต่อไปนี้ไว้ใน `tts-api/voices/` ก่อนใช้งาน TTS:

```text
tts-api/voices/en_US-lessac-medium.onnx
tts-api/voices/en_US-lessac-medium.onnx.json
tts-api/voices/en_US-ryan-medium.onnx
tts-api/voices/en_US-ryan-medium.onnx.json
```

ไฟล์ metadata `.json` เข้า Git ได้ แต่ไฟล์ model `.onnx` ต้องสำรองหรือดาวน์โหลดแยกต่างหาก

## เปิดระบบ

เปิด Docker Desktop ก่อน จากนั้นรัน:

```powershell
docker compose up -d --build
docker compose ps
```

ดู log ของทุก service:

```powershell
docker compose logs -f
```

ดู log เฉพาะ service:

```powershell
docker compose logs -f image-api
```

## ตรวจสุขภาพระบบ

```powershell
8000..8006 | ForEach-Object {
    Invoke-RestMethod "http://localhost:$_/health"
}
```

เปิดหน้า API documentation ได้ที่ `/docs` เช่น:

```text
http://localhost:8000/docs
http://localhost:8002/docs
http://localhost:8006/docs
```

## ปิดระบบ

ปิด containers โดยเก็บข้อมูลไว้:

```powershell
docker compose down
```

อย่าใช้ `docker compose down -v` โดยไม่สำรองข้อมูล เพราะ volume หรือข้อมูลฐานข้อมูลอาจถูกลบ

## ข้อมูลที่ไม่เก็บใน Git

- `.env` และ `secrets/`
- PostgreSQL และ Redis runtime data
- `n8n/data/` ซึ่งอาจมี credentials และสถานะการทำงาน
- `storage/`, `logs/` และ `backups/`
- SadTalker, Wav2Lip และ AI model weights
- วิดีโอ เสียง cache และไฟล์ชั่วคราว

workflow ที่ต้องการเก็บใน Git ควร export จาก n8n เป็น JSON แล้ววางใน `n8n/workflow-export/`

## สถานะปัจจุบัน

- API หลักมี health endpoint และ Python syntax ผ่านการตรวจแล้ว
- Script API ปัจจุบันคืนค่า script ตัวอย่างแบบคงที่
- Publish API, prompts, infrastructure และ workflow exports ยังรอการพัฒนา
- SadTalker และ Wav2Lip มีไฟล์อยู่ในเครื่องบาง environment แต่ยังไม่ได้เชื่อมกับ Dockerfile หรือ Animation API ปัจจุบัน
- SadTalker API ใช้ CPU เป็นค่าเริ่มต้นและทำงานทีละ job เพื่อควบคุมการใช้หน่วยความจำ

## SadTalker API

SadTalker เป็น service แยกที่พอร์ต `8007` เพื่อสร้างการเคลื่อนไหวใบหน้าและริมฝีปากจากภาพกับเสียง โดยเก็บ `animation-api` เดิมไว้เป็น FFmpeg fallback

Source และ model weights ของ SadTalker ไม่เข้า Git เพราะมีขนาดหลาย GB แต่ต้องมีอยู่ในตำแหน่งนี้บนแต่ละเครื่องก่อน build/run:

```text
animation-api/sadtalker/inference.py
animation-api/sadtalker/checkpoints/SadTalker_V0.0.2_256.safetensors
animation-api/sadtalker/checkpoints/SadTalker_V0.0.2_512.safetensors
animation-api/sadtalker/checkpoints/mapping_00109-model.pth.tar
animation-api/sadtalker/checkpoints/mapping_00229-model.pth.tar
```

Build และเปิดเฉพาะ SadTalker:

```powershell
docker compose up -d --build sadtalker-api
Invoke-RestMethod "http://localhost:8007/health"
```

ตัวอย่าง request:

```json
{
  "scene_id": 1,
  "character_id": "firewall",
  "image_path": "/data/storage/images/firewall_scene_1.png",
  "audio_path": "/data/storage/audio/firewall_scene_1.wav",
  "size": 256,
  "preprocess": "full",
  "still": false,
  "pose_style": 0,
  "expression_scale": 1.0,
  "force": false
}
```

CPU inference อาจใช้เวลาหลายนาทีต่อฉาก ควรทดสอบหนึ่งฉากก่อน และใช้ GPU worker แยกเมื่อขึ้น Production

## หมายเหตุด้านความปลอดภัย

การตั้งค่าปัจจุบันเหมาะสำหรับการพัฒนาภายในเครื่อง API ยังไม่มี authentication จึงไม่ควรเปิด ports `5678` และ `8000-8006` สู่ Internet โดยตรง หากนำขึ้น production ควรเพิ่ม reverse proxy, HTTPS, authentication, request limits และจำกัดการเข้าถึงไฟล์ใน `storage/`
