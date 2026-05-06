import json
import re
from urllib.parse import parse_qs, unquote, urlparse

import requests

from app.core.config import BROWSER_USER_AGENT
from app.core.errors import SaveAnyBackendError
from app.models.media import MediaFormat, ResolvedMediaInfo
from app.services.quality_service import build_quality_options, pick_recommended_quality
from app.services.thumbnail_service import cache_thumbnail


def resolve_with_douyin(url: str) -> ResolvedMediaInfo:
    video_id = extract_douyin_video_id(url)
    detail = None
    source_page = url

    for page in candidate_pages(url, video_id):
        html = fetch_douyin_page(page)
        if not html:
            continue
        detail = extract_video_detail_from_pace_data(html, video_id) or extract_video_detail_from_legacy_html(html, video_id)
        if detail and detail.get("video"):
            source_page = page
            break

    if not detail or not detail.get("video"):
        raise SaveAnyBackendError("RESOLVER_FAILED", "抖音公开解析失败：链接可能失效、需要登录，或页面签名策略已变化。")

    formats = normalize_douyin_formats(detail)
    if not formats:
        raise SaveAnyBackendError("NO_FORMAT", "已识别抖音视频，但没有找到可下载的公开视频地址。")

    video = detail.get("video") or {}
    thumbnail = first_string(
        [
            video.get("cover"),
            *(video.get("coverUrlList") or []),
            video.get("originCover"),
            *(video.get("originCoverUrlList") or []),
        ]
    )

    try:
        thumbnail_url = cache_thumbnail(thumbnail, source_page)
    except Exception:
        thumbnail_url = "/api/thumbnails/placeholder"

    options = build_quality_options(formats, disable_audio=True)
    return ResolvedMediaInfo(
        title=detail.get("desc") or f"douyin_{detail.get('awemeId') or video_id or 'video'}",
        uploader=(detail.get("authorInfo") or {}).get("nickname"),
        thumbnail=thumbnail,
        thumbnailUrl=thumbnail_url,
        duration=round(video["duration"] / 1000) if isinstance(video.get("duration"), int) else None,
        webpageUrl=source_page,
        platform="douyin",
        resolverUsed="DouyinResolver",
        requiresCookie=False,
        availableQualities=options,
        recommendedQuality=pick_recommended_quality(options),
        formats=formats,
    )


def fetch_douyin_page(url: str) -> str:
    headers = {
        "User-Agent": BROWSER_USER_AGENT,
        "Accept": "text/html,application/json,*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.douyin.com/",
    }
    try:
        response = requests.get(url, headers=headers, timeout=(10, 30), allow_redirects=True)
        response.raise_for_status()
        response.encoding = "utf-8"
        return response.text
    except Exception:
        return ""


def candidate_pages(url: str, video_id: str | None) -> list[str]:
    pages = [url]
    if video_id:
        pages.append(f"https://www.douyin.com/jingxuan?modal_id={video_id}")
        pages.append(f"https://www.iesdouyin.com/share/video/{video_id}/")
    return list(dict.fromkeys(pages))


def extract_douyin_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for key in ("modal_id", "item_ids", "group_id", "aweme_id"):
        values = query.get(key)
        if values:
            match = re.search(r"\d{8,24}", values[0])
            if match:
                return match.group(0)

    path_match = re.search(r"/(?:video|note)/(\d{8,24})", parsed.path) or re.search(r"/(\d{8,24})(?:/|$)", parsed.path)
    if path_match:
        return path_match.group(1)

    fallback = re.search(r"(?<!\d)(\d{8,24})(?!\d)", url)
    return fallback.group(1) if fallback else None


def extract_video_detail_from_pace_data(html: str, video_id: str | None) -> dict | None:
    pattern = re.compile(r"self\.__pace_f\.push\(\[1,(\"(?:\\.|[^\"\\])*\")\]\)</script>")
    for match in pattern.finditer(html):
        try:
            raw = json.loads(match.group(1))
        except Exception:
            continue
        text = unquote(raw) if raw.startswith("%") else raw
        if "videoDetail" not in text and "awemeId" not in text:
            continue
        try:
            parsed = json.loads(text)
        except Exception:
            continue
        details = collect_video_details(parsed)
        exact = next((item for item in details if item.get("awemeId") == video_id), None)
        usable = exact or next((item for item in details if (item.get("video") or {}).get("bitRateList")), None)
        if usable:
            return usable
    return None


def extract_video_detail_from_legacy_html(html: str, video_id: str | None) -> dict | None:
    body = html.replace("\\u002F", "/")
    match = re.search(r'"video":\{"play_addr":\{"uri":"([a-z0-9]+)"', body, re.I)
    if not match:
        return None
    video_uri = match.group(1)
    play_url = f"https://www.iesdouyin.com/aweme/v1/play/?video_id={video_uri}&ratio=1080p&line=0"
    desc = re.search(r'"desc":\s*"([^"]+)"', body)
    nickname = re.search(r'"nickname":\s*"([^"]+)"', body)
    return {
        "awemeId": video_id,
        "desc": desc.group(1) if desc else None,
        "authorInfo": {"nickname": nickname.group(1) if nickname else None},
        "video": {
            "playApi": play_url,
            "bitRateList": [{"gearName": "1080p", "height": 1080, "videoFormat": "mp4", "playApi": play_url}],
        },
    }


def collect_video_details(value: object, output: list[dict] | None = None) -> list[dict]:
    if output is None:
        output = []
    if not isinstance(value, dict):
        if isinstance(value, list):
            for item in value:
                collect_video_details(item, output)
        return output

    video_detail = value.get("videoDetail")
    if isinstance(video_detail, dict):
        output.append(video_detail)
    if value.get("awemeId") and isinstance(value.get("video"), dict):
        output.append(value)

    for child in value.values():
        collect_video_details(child, output)
    return output


def normalize_douyin_formats(detail: dict) -> list[MediaFormat]:
    video = detail.get("video") or {}
    formats: list[MediaFormat] = []
    for index, item in enumerate(video.get("bitRateList") or []):
        url = first_string([*(addr.get("src") for addr in item.get("playAddr") or [] if isinstance(addr, dict)), item.get("playApi")])
        if not url:
            continue
        height = item.get("height") if isinstance(item.get("height"), int) else None
        formats.append(
            MediaFormat(
                id=str(item.get("gearName") or item.get("qualityType") or index),
                ext="mp4",
                resolution=f"{height}p" if height else None,
                note=item.get("gearName"),
                height=height,
                vcodec="unknown",
                acodec="unknown",
                url=url,
            )
        )

    if formats:
        return sorted(formats, key=lambda item: item.height or 0, reverse=True)

    url = first_string([*(addr.get("src") for addr in video.get("playAddr") or [] if isinstance(addr, dict)), video.get("playApi")])
    return [MediaFormat(id="play", ext="mp4", vcodec="unknown", acodec="unknown", url=url)] if url else []


def select_douyin_format(formats: list[MediaFormat], quality: str) -> MediaFormat:
    candidates = sorted([item for item in formats if item.url], key=lambda item: item.height or 0, reverse=True)
    if not candidates:
        raise SaveAnyBackendError("NO_FORMAT", "没有找到匹配当前清晰度的抖音视频地址。")
    if quality == "1080p":
        return next((item for item in candidates if (item.height or 0) <= 1080), candidates[0])
    if quality == "720p":
        return next((item for item in candidates if (item.height or 0) <= 720), candidates[-1])
    return candidates[0]


def first_string(values) -> str | None:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return None
