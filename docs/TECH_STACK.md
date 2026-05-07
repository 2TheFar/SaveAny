# SaveAny Lightweight Technical Stack

Updated: 2026-05-07

## Decision

Use this stack for the next implementation cycle:

```text
Frontend:  Next.js 16 App Router + React + TypeScript
UI:        UI Ux Pro Max design system + CSS Modules / scoped CSS + lucide-react
Backend:   FastAPI + Pydantic + Uvicorn
Media:     yt-dlp + ffmpeg
Subtitles: platform subtitles first, faster-whisper ASR fallback
Tasks:     FastAPI BackgroundTasks for MVP
AI:        DeepSeek V4 Flash through an OpenAI-compatible adapter
Mind map:  markmap-lib + markmap-view
Storage:   local filesystem cache + JSON metadata
Testing:   TypeScript check + focused Python service tests when logic grows
```

Context7 check: Next.js official docs for `/vercel/next.js/v16.2.2` describe using Route Handlers as a Backend-for-Frontend proxy to another backend. That matches this project: Next.js should be the polished product shell and thin API boundary, while FastAPI should own long-running media and AI work.

## Why This Stack

The product needs a beautiful, fast web UI and several backend-heavy workflows. The simplest strong split is:

- Next.js for interface, routing, rendering, and a small API proxy.
- FastAPI for subprocess work, task state, subtitles, AI calls, and file responses.

This avoids forcing Next.js route handlers to manage long downloads and external tools, while also avoiding a heavy distributed backend before the product needs it.

## Frontend

Use Next.js App Router as the main app framework.

Recommended structure:

```text
app/page.tsx
app/workspace/page.tsx
app/workspace/useWorkspace.ts
app/workspace/components/UrlInput.tsx
app/workspace/components/VideoPreview.tsx
app/workspace/components/DownloadPanel.tsx
app/workspace/components/SummaryPanel.tsx
app/workspace/components/MindMapPanel.tsx
app/workspace/components/SubtitlesPanel.tsx
app/workspace/components/ChatPanel.tsx
app/api/proxy routes
```

UI rules:

- Use UI Ux Pro Max before major UI work. Generate or refresh the design system with `--design-system`, then check `design-system/saveany/MASTER.md` before editing UI.
- Keep the first screen as the actual product entry, not a marketing-only page.
- Use `lucide-react` for icons.
- Use CSS variables for theme tokens.
- Use CSS Modules or tightly scoped component classes.
- Avoid importing a large component system unless the UI starts repeating enough patterns to justify it.
- Add mock workspace fixtures so visual polish can happen without backend calls.

Current design baseline from UI Ux Pro Max:

```text
Pattern:     Video-First Hero
Style:       Glassmorphism, used with restraint
Colors:      Teal primary (#0D9488), teal secondary (#14B8A6), orange CTA (#F97316)
Typography:  Plus Jakarta Sans
Source:      design-system/saveany/MASTER.md
```

Do not add Tailwind, shadcn/ui, Zustand, Redux, Prisma, or a component framework yet. They are useful tools, but right now they would increase project surface area faster than they increase shipping speed.

## Backend

Use FastAPI as the source of truth for product behavior.

Recommended structure:

```text
backend/app/main.py
backend/app/api/media.py
backend/app/api/tasks.py
backend/app/api/files.py
backend/app/services/media_resolver.py
backend/app/services/download_service.py
backend/app/services/subtitle_service.py
backend/app/services/summary_service.py
backend/app/services/chat_service.py
backend/app/services/task_service.py
backend/app/services/storage_service.py
backend/app/models/*.py
```

Keep the service layer boring and explicit. A little duplication is acceptable when it keeps the workflow readable.

Use `yt-dlp` as the default resolver/downloader. Add platform-specific resolvers only when `yt-dlp` cannot produce the needed result.

Use `ffmpeg` for audio extraction or media conversion only when required by a feature.

## Subtitle And ASR Layer

Subtitle extraction should follow this priority:

```text
1. Platform-provided subtitles or captions
2. yt-dlp subtitle extraction
3. Platform-specific subtitle scraping when reliable
4. Local ASR fallback
```

Use local ASR only when no usable subtitle exists. The user's GPU is an NVIDIA RTX 3050, so the fallback must favor small and fast models over maximum accuracy.

Recommended ASR stack:

```text
Library:      faster-whisper
Default:      small or base model
GPU mode:     device=cuda, compute_type=int8_float16
CPU fallback: device=cpu, compute_type=int8
Input:        audio extracted by ffmpeg
Output:       timestamped transcript segments
```

Do not default to large Whisper models. Use `medium`, `large-v3`, or `distil-large-v3` only as an explicit quality mode after the fast path works.

## API Shape

Frontend-facing Next.js routes should mirror the backend and mostly proxy:

```text
POST /api/media/info
POST /api/tasks/download
POST /api/tasks/subtitles
POST /api/tasks/summarize
GET  /api/tasks/:id
POST /api/tasks/:id/chat
GET  /api/files/:id
```

Avoid separate fallback implementations in Next.js. If the backend is unavailable, show a clear dependency error.

## Task Model

Use one task model:

```text
pending
running
success
failed
expired
```

Task types:

```text
download
subtitle_extract
summarize
chat
```

For MVP, in-memory task state plus local JSON cache is acceptable. Move to SQLite only when users need history after backend restart. Move to Redis/RQ or Celery only when tasks must survive process restarts or run concurrently at production scale.

## AI Layer

Use one adapter module for AI calls. The default model for both summary and chat is:

```text
deepseek-v4-flash
```

DeepSeek's current API supports OpenAI-compatible Chat Completions at `/v1/chat/completions`, with `deepseek-v4-flash` as the model name. Keep the provider behind backend code and never expose API keys to the browser.

Recommended files:

```text
backend/app/services/ai_provider.py
backend/app/services/summary_service.py
backend/app/services/chat_service.py
```

Recommended defaults:

```text
Summary: response_format=json_object when possible, thinking disabled for speed
Chat:    concise answer mode, use summary + subtitle segments as context
Model:   deepseek-v4-flash
Env:     DEEPSEEK_API_KEY
```

The summary output should be structured:

```text
summary
keyPoints
chapters
keywords
mindMapMarkdown
```

The chat endpoint should use generated summary plus subtitle segments as context. Do not build a vector database until plain transcript-window retrieval is not enough.

## Storage

Use local cache first:

```text
backend/storage/downloads
backend/storage/thumbnails
backend/storage/cache
```

Store small metadata and AI outputs as JSON. Store media files directly on disk with task IDs. Add cleanup by expiration before adding a database.

## What To Remove Or Avoid

Remove over time:

- duplicate TypeScript media resolver logic
- duplicate TypeScript download logic
- large all-in-one workspace page
- broad future-facing architecture docs in the root directory

Avoid for now:

- account system
- payment system
- database-first architecture
- distributed queue
- object storage
- large UI kit
- multi-provider AI abstraction beyond one clean adapter
- large local ASR models as the default path

## Implementation Order

1. Archive old docs and keep this document as the technical baseline.
2. Use UI Ux Pro Max design system as the UI baseline.
3. Convert Next API routes into thin backend proxies.
4. Remove or quarantine TypeScript media/download fallback code.
5. Split the workspace page into hook plus panels.
6. Add mock fixtures for UI development.
7. Stabilize platform subtitles, ASR fallback, DeepSeek summary, mind map, and chat.
8. Polish landing and workspace UI with browser verification.
