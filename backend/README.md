# SaveAny Backend

FastAPI backend service for SaveAny stage 3.

## Install

```bash
pip install -r requirements.txt
```

The runtime environment also needs:

```bash
yt-dlp
ffmpeg
BBDown
```

BBDown is used for Bilibili highest-quality downloads. You can install it as a .NET tool:

```bash
dotnet tool install --global BBDown
```

Optional Bilibili settings:

```bash
SAVEANY_BBDOWN_PATH=BBDown
SAVEANY_BBDOWN_ENCODING_PRIORITY=avc,hevc,av1
SAVEANY_BBDOWN_WORK_DIR=backend/storage/bilibili
SAVEANY_BILIBILI_AUTH_FILE=backend/storage/credentials/bilibili_session.json
```

Bilibili QR login stores only local credentials under `backend/storage/credentials/`. The file is ignored by Git and can be cleared from the app UI.

## Run

```bash
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Then start Next.js with:

```bash
SAVEANY_BACKEND_URL=http://127.0.0.1:8000
npm run dev
```

On Windows PowerShell:

```powershell
$env:SAVEANY_BACKEND_URL="http://127.0.0.1:8000"
npm run dev
```

## APIs

- `GET /health`
- `GET /api/system/check`
- `POST /api/media/info`
- `POST /api/tasks/download`
- `GET /api/tasks/{task_id}`
- `POST /api/platforms/bilibili/login`
- `GET /api/platforms/bilibili/login/{login_id}`
- `GET /api/platforms/bilibili/session`
- `DELETE /api/platforms/bilibili/session`
- `GET /api/files/{file_id}`
- `GET /api/thumbnails/{thumbnail_id}`
