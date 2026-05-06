# SaveAny 技术架构方案

更新时间：2026-05-06

## 当前架构结论

SaveAny 当前采用：

```text
Next.js 产品入口 + BFF
FastAPI 下载与任务后端
Resolver 平台解析层
yt-dlp / ffmpeg 外部处理工具
本地临时文件存储
```

这个架构已经支撑下载功能 MVP，后续视频总结、字幕翻译等 Pro 功能也应继续沿用这套任务模型扩展。

## 分层职责

### Next.js

负责：

- 产品页面。
- 工作台 UI。
- 用户交互。
- BFF API。
- 未来登录、支付、Pro 权益入口。

当前 BFF 接口：

```text
POST /api/video/info
POST /api/video/download
```

配置 `SAVEANY_BACKEND_URL` 后优先调用 FastAPI；FastAPI 不可用时回落原有 Next.js 内置能力。

### FastAPI

负责：

- 系统自检。
- 视频解析。
- 下载任务。
- 任务状态。
- 文件返回。
- 缩略图缓存。
- 后续 AI/Pro 任务。

当前接口：

```text
GET  /health
GET  /api/system/check
POST /api/media/info
POST /api/tasks/download
GET  /api/tasks/{task_id}
GET  /api/files/{file_id}
GET  /api/thumbnails/{thumbnail_id}
```

### Resolver 层

负责处理平台差异。

当前 Resolver：

- `YtDlpResolver`：YouTube、Bilibili 和其他通用平台。
- `DouyinResolver`：抖音精选和抖音视频。

后续可扩展：

- `BilibiliResolver`
- `TikTokResolver`
- `InstagramResolver`

## 任务模型

统一任务状态：

```text
pending
running
success
failed
expired
```

当前任务类型：

```text
download
thumbnail_cache
subtitle_extract
audio_extract
transcribe
summarize
batch_download
```

第四阶段会围绕这些任务类型扩展 Pro 功能，不再另起一套任务系统。

## AI/Pro 功能扩展方向

第四阶段优先开发：

- 视频总结。
- 字幕提取。
- 字幕翻译。
- 音频提取。

建议链路：

```text
视频链接
-> 解析媒体信息
-> 创建 AI 任务
-> 获取字幕或提取音频
-> 转写 / 翻译 / 总结
-> 结构化结果返回
```

## 存储策略

当前：

```text
backend/storage/downloads
backend/storage/thumbnails
```

MVP 阶段使用本地临时目录。

未来：

- 数据库保存用户、任务、额度、订单和历史。
- 对象存储保存下载文件、音频、字幕和总结结果。
- Redis/RQ 或 Celery 承载后台任务。

## 部署策略

正式部署前应 Docker 化：

```text
Next.js
FastAPI
yt-dlp
ffmpeg
```

不要依赖服务器手工安装 `yt-dlp`，因为这会让部署不可控。推荐在后端镜像中固定安装，并提供升级路径。

## 安全边界

- 公网版本默认不接收用户 Cookie。
- 不开放任意 URL 代理。
- 文件接口只返回任务目录中的文件。
- 缩略图缓存限制体积和超时。
- 下载文件和 AI 结果后续需要过期清理。

## 当前优先级

1. 下载功能沉淀。
2. 第四阶段开发视频总结、字幕提取、字幕翻译等 Pro 功能。
3. 功能跑通后再做前端体验精修。
4. 最后进入账号、额度、支付、部署正式化。
