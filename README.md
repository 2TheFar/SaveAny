# SaveAny

SaveAny 是一个“公开视频保存 + 内容整理”的本地开发版项目。

当前这版已经不只是下载 MVP。按历史阶段文档来看：

- 第 1 阶段：基础下载 MVP，已完成。
- 第 2 阶段：平台识别 + Resolver 架构重整，已完成。
- 第 3 阶段：FastAPI 下载后端雏形，已完成。
- 第 4 阶段：Pro 核心能力开发，已经进入实现，且不是纯计划状态。

结合 `docs/CURRENT.md`、`docs/TECH_STACK.md` 和现有代码，当前实际进度可以概括为：

- 下载基础链路已经沉淀完成。
- 前端已有首页和工作台两套界面。
- 后端已有任务模型、字幕提取、视频总结、AI 问答相关接口。
- 第 4 阶段已经做出了首版闭环，但还没有全部做完。

## 当前实现了什么

### 1. 首页与工作台 UI

- 首页：`app/page.tsx`
- 工作台：`app/workspace/page.tsx`

当前交互路径：

1. 粘贴公开视频链接。
2. 解析视频信息。
3. 进入工作台。
4. 自动跑字幕任务。
5. 字幕成功后自动跑总结任务。
6. 在工作台中查看：
   - 下载
   - 字幕
   - 总结
   - 思维导图
   - AI 对话

### 2. 视频解析与下载

前端 BFF 路由：

- `POST /api/video/info`
- `POST /api/video/download`
- `GET /api/video/file/:id`
- `GET /api/video/thumbnail/:id`

后端接口：

- `POST /api/media/info`
- `POST /api/tasks/download`
- `GET /api/tasks/{task_id}`
- `GET /api/files/{file_id}`
- `GET /api/thumbnails/{thumbnail_id}`

实现状态：

- 支持公开视频解析。
- 支持质量选择：`best / 1080p / 720p / audio`。
- 支持缩略图缓存/代理。
- 支持任务式下载。
- Next.js 在配置了 `SAVEANY_BACKEND_URL` 时优先走 FastAPI。
- 若未配置后端，首页解析/下载仍保留本地 TypeScript fallback。

### 3. Resolver 与平台策略

当前已经有：

- 平台识别：`lib/platform.ts`、`backend/app/services/platform_service.py`
- 通用解析器：`yt-dlp`
- 抖音专用 Resolver：
  - `lib/resolvers/douyin.ts`
  - `backend/app/services/douyin_resolver.py`

这说明项目已经完成了“不能只靠 yt-dlp”的第二阶段目标。

### 4. 字幕提取

前端 BFF：

- `POST /api/tasks/subtitles`

后端：

- `POST /api/tasks/subtitles`
- `backend/app/services/subtitle_service.py`

当前实现：

- 优先读平台字幕。
- Bilibili 有专门网页字幕提取逻辑。
- 通用情况走 `yt-dlp --write-subs --write-auto-subs`。
- 字幕结果会缓存到本地 JSON。

这部分已经属于第 4 阶段 P0，而且不是只写了文档，代码已经接上了。

### 5. 视频总结

前端 BFF：

- `POST /api/tasks/summarize`

后端：

- `POST /api/tasks/summarize`
- `backend/app/services/task_service.py`
- `backend/app/services/deepseek_service.py`

当前实现：

- 总结任务依赖字幕任务结果。
- 用 `DeepSeek` 生成结构化总结。
- 返回结构包含：
  - `summary`
  - `keyPoints`
  - `chapters`
  - `keywords`
  - `mindMapMarkdown`

这说明第 4 阶段的“视频总结闭环”已经做出首版。

### 6. 思维导图

前端工作台已实现：

- `markmap-lib`
- `markmap-view`

总结成功后，工作台可以直接把 `mindMapMarkdown` 渲染成思维导图。

### 7. AI 对话

前端 BFF：

- `POST /api/tasks/:id/chat`

后端：

- `POST /api/tasks/{task_id}/chat`

当前实现：

- 基于“总结结果 + 字幕内容”进行问答。
- 返回 `answer` 和 `references`。
- 工作台已能显示问答记录和时间引用。

## 目前走到哪一步

如果按“阶段计划”来判断，当前项目最准确的表述是：

- 第 3 阶段已经完成。
- 第 4 阶段已经开始并落地了首版核心能力。

如果按“功能闭环”来判断，当前状态更接近：

- 下载链路：已完成。
- 字幕提取：已完成首版。
- 视频总结：已完成首版。
- 思维导图：已完成首版。
- AI 对话：已完成首版。
- 字幕翻译：未实现。
- 独立音频提取 API：未实现。
- 批量任务：未实现。
- Bilibili 本机扫码登录：已完成首版，仅用于账号权限内最高画质下载。
- 支付/额度/数据库/队列：未实现。

所以，当前并不是“还停留在第三阶段”，而是已经进入第四阶段，并完成了其中最核心的一部分。

## 项目结构

```text
app/                    Next.js 页面与 BFF 路由
backend/                FastAPI 后端
design-system/          设计系统文档
docs/                   当前文档
docs/archive/           历史阶段文档
lib/                    前端侧工具、fallback、resolvers
.saveany-cache/         前端 fallback 下载缓存
backend/storage/        后端下载、缩略图、AI 缓存
```

## 运行方式

## 1. 前端依赖

在项目根目录：

```powershell
npm install
```

启动前端：

```powershell
npm run dev
```

默认地址：

```text
http://127.0.0.1:3000
```

## 2. 后端依赖

在项目根目录或 `backend/` 目录安装：

```powershell
pip install -r backend\requirements.txt
```

系统运行时还需要：

- `yt-dlp`
- `ffmpeg`
- `BBDown`（用于 Bilibili 最高画质下载）

BBDown 可通过 .NET tool 安装：

```powershell
dotnet tool install --global BBDown
```

默认 B 站编码优先级为 `avc,hevc,av1`，更接近 B 站客户端常见 1080p 缓存体积；如需优先小体积，可设置 `SAVEANY_BBDOWN_ENCODING_PRIORITY=hevc,av1,avc`。

Bilibili 扫码登录态只保存在本机 `backend/storage/credentials/`，可在工作台清除。

启动后端：

```powershell
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## 3. 前后端联动

要启用完整工作台能力，前端需要指向 FastAPI：

```powershell
$env:SAVEANY_BACKEND_URL="http://127.0.0.1:8000"
npm run dev
```

如果要测试“总结 / 思维导图 / AI 问答”，还需要：

```powershell
$env:DEEPSEEK_API_KEY="你的 Key"
```

说明：

- 不配 `SAVEANY_BACKEND_URL` 时：首页解析/下载仍可能可用。
- 但工作台里的字幕任务、总结任务、AI 对话依赖 FastAPI，不能只靠前端 fallback。

## 手动测试清单

建议准备 1 个公开可访问的视频链接，优先选：

- YouTube 公开视频
- Bilibili 公开视频
- 抖音公开视频

不要用：

- 会员视频
- 私密视频
- 非 Bilibili 的登录/私密视频
- 账号本身无权限观看的会员高清视频

## A. 基础启动检查

1. 启动 FastAPI。
2. 启动 Next.js。
3. 打开 `http://127.0.0.1:3000`。
4. 确认首页正常显示。

可选检查：

- 打开 `http://127.0.0.1:8000/health`
- 期望返回：`{"status":"ok"}`

## B. 视频解析

1. 在首页粘贴公开视频链接。
2. 点击“解析”。
3. 期望结果：
   - 能跳转到 `/workspace`
   - 能看到标题、封面、平台、解析器
   - 能看到可用质量选项

重点验证：

- YouTube / Bilibili 应能正常解析。
- 抖音链接应走专用 Resolver，而不是直接失败在通用 `yt-dlp` 上。

## C. 下载功能

1. 在工作台选择一个质量。
2. 点击“下载当前质量”。
3. 期望结果：
   - 状态变为下载中
   - 成功后出现下载链接
   - 点击后能拿到文件

重点验证：

- 文件能实际下载。
- 文件名正常。
- 后端下载模式下，任务状态会轮询到 `success`。

## D. 字幕提取

1. 进入工作台后等待自动处理。
2. 打开“字幕”标签。
3. 期望结果：
   - 能看到“处理中”
   - 成功后能看到字幕列表
   - 有时间戳和字幕文本

重点验证：

- Bilibili 视频优先尝试平台字幕。
- 通用平台可走 `yt-dlp` 自动字幕/字幕提取。
- 无字幕时应给出清晰失败提示。

## E. 视频总结

前提：

- 已配置 `DEEPSEEK_API_KEY`
- 字幕任务成功

步骤：

1. 等待工作台自动触发总结任务。
2. 打开“总结”标签。
3. 期望结果：
   - 有整体摘要
   - 有核心要点
   - 有章节摘要
   - 有关键词

## F. 思维导图

前提：

- 总结任务成功

步骤：

1. 打开“思维导图”标签。
2. 期望结果：
   - 页面渲染出 Markmap 导图
   - 可缩放、平移

## G. AI 对话

前提：

- 总结任务成功

步骤：

1. 打开“AI 对话”标签。
2. 输入一个和视频内容相关的问题。
3. 期望结果：
   - 返回回答
   - 回答下方可带引用时间点

推荐测试问题：

- “这段视频的核心观点是什么？”
- “作者在前半段讲了哪些重点？”
- “请按章节复述这段内容。”

## 当前未完成项

以下能力仍属于未完成或未独立交付状态：

- 字幕翻译
- 独立音频提取 API
- 批量任务
- 用户体系
- 支付/额度
- 持久化数据库
- Redis / Celery 等正式任务队列
- 云端存储

## 文档索引

当前优先读：

- `docs/CURRENT.md`
- `docs/TECH_STACK.md`
- `实践原则.md`
- `需求&思考.md`

历史阶段文档：

- `docs/archive/SaveAny项目计划书.md`
- `docs/archive/第二阶段目标.md`
- `docs/archive/第三阶段执行报告.md`
- `docs/archive/第四阶段目标.md`

## 一句话结论

当前这版最准确的定位是：

“下载底座已完成，第 4 阶段核心功能已经做出首版闭环，可手动验证下载、字幕、总结、导图和 AI 问答，但翻译、批量、账号和正式化能力还没进入完成态。”
