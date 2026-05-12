# Bilibili 最高画质下载优化报告

日期：2026-05-12  
项目：SaveAny  
范围：B 站视频解析、登录态、最高画质下载、文件命名与系统检查

## 背景

SaveAny 原本主要依赖 `yt-dlp` 通用链路处理视频下载。B 站场景下，未登录或通用解析经常只能拿到 720p/1080p 的公开流，无法稳定使用账号权限内的 1080P 高码率、4K、HDR、杜比视界或 8K 等清晰度。

本次优化将 B 站下载链路迁移到开源下载器 BBDown，并增加本机扫码登录。登录态只存放在本机 FastAPI 后端，不上传、不打日志、不暴露 Cookie。登录并不绕过会员或版权限制，只用于访问用户账号本身已有权限的清晰度。

## 已解决的问题

1. B 站最高画质能力不足
   - B 站链接优先走 `BilibiliResolver(BBDown)`。
   - `best` 语义升级为账号权限内最高可用画质。
   - `1080p`、`720p` 仍保留为用户可选项，不会因登录后强制变成最高画质。

2. 登录后质量选项被错误限制
   - 原先 UI 质量可用性受 `yt-dlp` 公开格式列表影响，登录后仍可能显示 `1080p/720p` 不可选。
   - 现在 B 站固定展示 `best / 1080p / 720p / audio`，下载时由 BBDown 按账号权限和所选质量尝试拉取。
   - 扫码登录或清除登录后会刷新 B 站质量状态，但保留用户当前选择。

3. 已登录却下载到偏小文件
   - 发现 Next 下载 API 在 FastAPI 下载失败后会静默 fallback 到旧的 Next/yt-dlp 链路，可能绕过 BBDown 和本机 B 站 Cookie。
   - 已修正：B 站下载必须走 FastAPI + BBDown；后端失败时直接返回明确错误，不再回退到 yt-dlp。
   - 默认编码优先级从 `hevc,av1,avc` 改为 `avc,hevc,av1`，更接近 B 站客户端常见 1080p 缓存体积和兼容性。

4. 下载结果命名异常
   - 原先可能出现 `_.mp4`。
   - 现在 BBDown 文件模板为 `<videoTitle>_<dfn>_Bilibili`。
   - 后端下载完成后会做最终归一化，结果格式为：

```text
视频标题_清晰度_Bilibili.mp4
```

示例：

```text
又是中山大学，生科院副院长代表作，造假！_1080P 高清_Bilibili.mp4
```

## 关键实现

### 后端

- 新增 B 站专用 resolver：`backend/app/services/bilibili_resolver.py`
- 新增本机 B 站二维码登录服务：`backend/app/services/bilibili_auth_service.py`
- 新增平台登录 API：
  - `POST /api/platforms/bilibili/login`
  - `GET /api/platforms/bilibili/login/{login_id}`
  - `GET /api/platforms/bilibili/session`
  - `DELETE /api/platforms/bilibili/session`
- B 站下载命令使用 BBDown subprocess 单任务执行，不启用 BBDown `serve` 常驻服务。
- Cookie 通过 BBDown `-c` 参数传入，并在错误日志中统一脱敏。

### 前端

- 工作台增加 B 站权限面板：
  - 未登录状态提示
  - 扫码登录入口
  - 清除登录入口
  - 登录后刷新质量状态
- 下载 API 对 B 站禁用 Next/yt-dlp fallback，避免链路偏移。

### 配置

新增或使用以下配置：

```text
SAVEANY_BBDOWN_PATH=BBDown
SAVEANY_BBDOWN_ENCODING_PRIORITY=avc,hevc,av1
SAVEANY_BBDOWN_WORK_DIR=backend/storage/bilibili
SAVEANY_BILIBILI_AUTH_FILE=backend/storage/credentials/bilibili_session.json
```

Windows 下如果 PATH 识别不到 BBDown，后端会尝试：

```text
%USERPROFILE%\.dotnet\tools\BBDown.exe
```

系统检查已改为使用 `BBDown --help`，避免某些版本 `BBDown --version` 返回非零导致误判。

## 安全边界

- B 站登录态只保存在 `backend/storage/credentials/`。
- 登录态目录已加入 `.gitignore`。
- 只保存最小 Cookie 字符串，不保存二维码图片或完整登录响应。
- 日志脱敏字段包括：
  - `SESSDATA`
  - `bili_jct`
  - `DedeUserID`
  - `access_token`
  - `Cookie`
- 不支持云端账号同步、多用户隔离、会员绕过、版权绕过或远程 Cookie 上传。

## 验证结果

已通过自动化检查：

```text
python -m unittest discover -s tests
python -m compileall app
npm run lint
```

最近一次结果：

```text
Ran 11 tests in 0.059s
OK
```

系统检查确认：

- `yt-dlp` 可用
- `ffmpeg` 可用
- `BBDown 1.6.3` 可用
- `qrcode` 可用
- B 站登录态文件可识别
- B 站 resolver 与二维码登录功能已启用

## 手动验收结论

功能测试已通过：

- 普通 B 站视频可解析。
- 扫码登录可获得本机账号权限。
- 登录后仍可手动选择 `best / 1080p / 720p / audio`。
- B 站下载走 BBDown，不再静默回退 yt-dlp。
- 1080p 下载更接近 B 站客户端缓存表现。
- 下载文件命名符合 `视频标题_清晰度_Bilibili.mp4`。
- 抖音下载链路未受影响。

## 后续建议

1. 增加实际流信息展示
   - 下载完成后展示 BBDown 实际选中的清晰度、编码、码率和文件大小。

2. 增加编码偏好 UI
   - 提供“兼容优先 AVC”和“小体积优先 HEVC/AV1”切换。

3. 增加 B 站专用下载记录
   - 保存每次下载的目标质量、实际清晰度、编码、文件大小和时间，方便排查画质差异。

4. 增加更细分的质量选项
   - 后续可扩展为 `4K / HDR / 1080P 高码率 / 1080P 高清` 等显式选项。

5. 明确多用户边界
   - 当前设计是本机单用户。如果未来部署到多人环境，需要重新设计账号隔离、凭据加密和权限提示。
