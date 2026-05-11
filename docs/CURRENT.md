# SaveAny Current Context

Updated: 2026-05-07

## Product Goal

SaveAny is a polished web app for working with public video links.

The target experience is:

1. Paste a video URL.
2. Resolve video metadata and available download quality.
3. Download the video or audio.
4. Extract subtitles when available.
5. Generate a concise AI summary.
6. Create a mind map from the summary.
7. Ask questions about the video through AI chat.

This is the only product goal for the next development cycle.

## Current Direction

Use a lightweight two-part architecture:

```text
Next.js web app
-> thin API proxy / BFF
-> FastAPI backend
-> yt-dlp / ffmpeg / subtitles / ASR / DeepSeek / local cache
```

Next.js should own the user experience. FastAPI should own media, tasks, subtitles, ASR, AI, and files.

Avoid maintaining the same business feature in both TypeScript and Python. If a feature requires video resolution, download, subtitle extraction, local speech recognition, AI generation, or cached task state, put it in FastAPI first.

## Canonical Docs

Use these documents first:

- `docs/CURRENT.md`: current product and architecture context.
- `docs/TECH_STACK.md`: recommended lightweight technical stack.
- `design-system/saveany/MASTER.md`: UI Ux Pro Max design system baseline.
- `实践原则.md`: local development principles.
- `需求&思考.md`: early product notes.

Historical phase documents are archived in `docs/archive/`.

## Fixed Technical Decisions

- UI optimization uses UI Ux Pro Max first.
- Current UI baseline is `design-system/saveany/MASTER.md`.
- Subtitle extraction prefers official/platform subtitles first.
- If subtitles are unavailable, use ASR fallback.
- Local ASR must be small and fast for NVIDIA RTX 3050.
- AI summary uses `deepseek-v4-flash`.
- AI chat uses `deepseek-v4-flash`.

## Scope For Now

Build:

- beautiful landing and workspace UI
- video URL analysis
- video/audio download
- Bilibili local QR login for highest-quality downloads
- subtitle extraction from platform captions first
- local ASR fallback with small/fast models
- AI summary through DeepSeek V4 Flash
- mind map generation
- AI chat over generated summary/subtitles through DeepSeek V4 Flash
- local cache and task status

Defer:

- general multi-platform login
- payment
- quota system
- cloud storage
- multi-user database
- distributed task queue
- admin dashboard
- browser extension
- mobile app

## Development Rules

Prefer vertical slices over broad platform work. A new feature should usually touch:

```text
backend/app/services/*
backend/app/api/*
app/api/*
app/workspace/*
docs/CURRENT.md or docs/TECH_STACK.md when architecture changes
```

Keep feature files small enough to read quickly. Split UI components and hooks before a page grows into a long mixed file.

Use mock data for UI iteration so design work does not depend on real downloads, subtitles, ASR, or AI calls.

For UI work, use UI Ux Pro Max first. Check `design-system/saveany/MASTER.md`, then add page-specific overrides under `design-system/saveany/pages/` when a page needs different rules.

Pin package versions instead of using `latest` once the stack is finalized.

## Near-Term Refactor Plan

1. Make FastAPI the only implementation for media resolution, download, subtitles, ASR, summary, and chat.
2. Simplify Next.js route handlers into thin proxy routes.
3. Split `app/workspace/page.tsx` into a workspace hook and small UI panels.
4. Add mock fixtures for workspace states.
5. Implement subtitle priority: platform captions first, then ASR fallback.
6. Standardize summary and chat on DeepSeek V4 Flash.
7. Polish the first-screen product experience and workspace layout.
