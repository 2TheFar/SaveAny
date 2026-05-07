# SaveAny 下载功能沉淀

生成时间：2026-05-06

## 当前结论

SaveAny 的下载功能已经完成 MVP 闭环，可以作为后续功能开发的稳定基础。

当前不是正式发行质量，但已经证明三类核心平台可用：

- YouTube：解析、下载、封面缓存可用。
- Bilibili：可下载 1080p。
- Douyin：抖音精选和抖音视频可通过专用 Resolver 下载。

## 核心链路

```text
用户提交 URL
-> 平台识别
-> Resolver 调度
   -> DouyinResolver
   -> YtDlpResolver
-> 返回标准化视频信息
-> 创建下载任务
-> 后端下载到临时目录
-> 浏览器通过文件接口下载
```

## 当前接口

Next.js BFF：

```text
POST /api/video/info
POST /api/video/download
GET  /api/video/file/:id
GET  /api/video/thumbnail/:id
```

FastAPI：

```text
GET  /health
GET  /api/system/check
POST /api/media/info
POST /api/tasks/download
GET  /api/tasks/{task_id}
GET  /api/files/{file_id}
GET  /api/thumbnails/{thumbnail_id}
```

## 技术实现

### 平台识别

已支持识别：

- YouTube
- Bilibili
- Douyin
- TikTok
- Vimeo
- X / Twitter
- Instagram
- Unknown

### Resolver 策略

`YtDlpResolver`：

- 负责 YouTube、Bilibili 和其他 `yt-dlp` 支持的平台。
- 获取标题、作者、时长、缩略图、格式列表。
- 下载时调用 `yt-dlp`。

`DouyinResolver`：

- 负责抖音精选和抖音视频。
- 不依赖 `yt-dlp` 直接解析抖音精选页。
- 从页面数据中提取视频信息和公开视频地址。
- 由后端代理下载，避免浏览器直连直链导致防盗链失败。

## 文件策略

下载目录：

```text
backend/storage/downloads/{taskId}
```

缩略图目录：

```text
backend/storage/thumbnails/{thumbnailId}
```

当前文件保留策略：

- MVP 阶段使用本地临时目录。
- 默认过期时间为 6 小时。
- 后续需要定时清理任务和临时文件。

安全边界：

- 文件接口只允许从任务目录返回文件。
- 下载输出模板限制在任务目录内。
- 使用安全文件名处理。
- 不开放任意 URL 图片代理。
- 不接收用户 Cookie。

## 错误类型

当前已沉淀的错误类型：

```text
INVALID_URL
UNSUPPORTED_PLATFORM
UNSUPPORTED_BY_YTDLP
NEEDS_LOGIN
NO_FORMAT
HOTLINK_BLOCKED
RATE_LIMITED
RESOLVER_FAILED
DOWNLOAD_FAILED
DOWNLOAD_TIMEOUT
DEPENDENCY_MISSING
TASK_NOT_FOUND
FILE_NOT_FOUND
```

这些错误类型后续应继续复用，不要在 AI 功能里重新发明一套错误模型。

## 已验证结果

验证命令：

```text
python -m compileall backend/app
npm run lint
```

验证结果：

- FastAPI `/health` 正常。
- FastAPI `/api/system/check` 正常。
- 检测到 `yt-dlp 2026.03.17`。
- 检测到 `ffmpeg 2026-04-30`。
- 空 URL 返回 `INVALID_URL`。
- 抖音精选解析成功，识别 27 个格式。
- 抖音 720p 下载成功，生成约 12MB 文件。
- 文件接口可正常返回下载文件。
- YouTube 解析成功。
- YouTube 缩略图缓存返回 `image/jpeg`。

## 部署注意事项

服务器必须具备：

```text
Python
FastAPI
yt-dlp
ffmpeg
可写临时目录
可访问目标视频平台的网络环境
```

正式部署建议：

- 使用 Docker 固化 `yt-dlp` 和 `ffmpeg`。
- 后端镜像启动时执行 `/api/system/check` 等价自检。
- 不依赖服务器手工安装 `yt-dlp`。
- 定期升级 `yt-dlp`，因为平台解析规则会变化。

## 后续不要轻易改动的约定

- Next.js 负责产品入口和 BFF。
- FastAPI 负责下载、AI 处理和任务管理。
- Resolver 负责平台差异。
- `yt-dlp` 是通用兜底，不是唯一方案。
- Cookie 默认不进入公网产品能力。
- 下载和 AI 功能统一走任务模型。

## 下一步承接

第四阶段将基于这套下载能力继续开发：

- 视频总结
- 字幕提取
- 字幕翻译
- 音频提取
- 批量任务

下载能力到这里先沉淀，不再作为下一阶段的主要开发对象，除非出现回归问题。
