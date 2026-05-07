# SaveAny 字幕链路重构执行报告

- 生成时间：2026-05-07 19:54:34
- 执行范围：平台字幕优先、ASR 兜底、DeepSeek 连通性、总结回归

## 依赖环境

```json
{
  "ok": true,
  "checkedAt": 1778154874.760829,
  "dependencies": {
    "ytDlp": {
      "ok": true,
      "version": "2026.03.17",
      "error": null
    },
    "ffmpeg": {
      "ok": true,
      "version": "ffmpeg version 2026-04-30-git-cc3ca17127-full_build-www.gyan.dev Copyright (c) 2000-2026 the FFmpeg developers",
      "error": null
    },
    "fasterWhisper": {
      "ok": true,
      "module": "faster_whisper",
      "error": null
    }
  },
  "storage": {
    "downloadDir": {
      "ok": true,
      "path": "D:\\Codex_Project\\SaveAny\\backend\\storage\\downloads",
      "error": null
    },
    "thumbnailDir": {
      "ok": true,
      "path": "D:\\Codex_Project\\SaveAny\\backend\\storage\\thumbnails",
      "error": null
    },
    "modelDir": {
      "ok": true,
      "path": "D:\\Codex_Project\\SaveAny\\backend\\storage\\models",
      "error": null
    }
  },
  "runtime": {
    "cuda": {
      "ok": true,
      "deviceCount": 1
    },
    "asr": {
      "model": "base",
      "preferredDevice": "cuda",
      "configuredDevice": "auto",
      "preferredComputeType": "int8_float16",
      "defaultModelPresent": true
    }
  },
  "env": {
    "deepseekApiKey": {
      "ok": true
    }
  },
  "features": {
    "mediaInfo": true,
    "downloadTasks": true,
    "douyinResolver": true,
    "asrFallback": true,
    "deepseekConnectivity": true,
    "futureTaskTypes": [
      "subtitle_extract",
      "audio_extract",
      "transcribe",
      "summarize",
      "batch_download"
    ]
  }
}
```

## DeepSeek 连通性

```json
{
  "ok": true,
  "model": "deepseek-v4-flash",
  "latencyMs": 768.19,
  "message": "",
  "error": null
}
```

## 自动测试结果

| URL | Platform | Attempt Path | Final Source | Segments | ASR | Summary | DeepSeek | Elapsed(s) |
| --- | --- | --- | --- | ---: | --- | --- | --- | ---: |
| https://www.bilibili.com/video/BV1fEdwBVEqJ/?spm_id_from=333.1365.list.card_archive.click | bilibili | platform_api | bilibili_ai_caption | 219 | no | success | yes | 17.82 |
| https://www.bilibili.com/video/BV1wGdwBEEQf/?spm_id_from=333.1365.list.card_archive.click | bilibili | platform_api | bilibili_ai_caption | 62 | no | success | yes | 12.91 |
| https://www.bilibili.com/video/BV1Ck9EYvEzk/?p=8&spm_id_from=333.1365.top_right_bar_window_history.content.click&vd_source=678b327a2c9d2de9fd219b4ae4c738da | bilibili | platform_api->asr | asr_faster_whisper | 1779 | yes | success | yes | 17.63 |
| https://www.douyin.com/jingxuan | douyin | platform_none->asr | failed:RESOLVER_FAILED | 0 | no | skipped | no | 2.49 |
| https://www.youtube.com/watch?v=Z5xczbxykpo | youtube | platform_api->asr | asr_faster_whisper | 3 | yes | failed:AI_RESPONSE_INVALID | no | 7.97 |

## 失败案例与原因

- `https://www.douyin.com/jingxuan` 字幕失败：RESOLVER_FAILED: 抖音公开解析失败：链接可能失效、需要登录，或页面签名策略已变化。
- `https://www.youtube.com/watch?v=Z5xczbxykpo` 总结失败：AI_RESPONSE_INVALID: DeepSeek 返回内容不是有效 JSON。

## 后续风险与建议

- Bilibili AI/自动字幕字段在不同接口上的暴露并不稳定，因此实现中保留了多路平台字幕探测与 ASR 兜底。
- Douyin 当前实现默认直接走 ASR，不依赖创作端自动字幕能力。
- DeepSeek 连通性测试依赖运行脚本时的环境变量或 `backend/.env` 注入。
- `faster-whisper small` 为默认模型，若 CPU fallback 过慢，可通过 `.env` 下调模型。
