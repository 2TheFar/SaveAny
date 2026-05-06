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
```

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
- `GET /api/files/{file_id}`
- `GET /api/thumbnails/{thumbnail_id}`
