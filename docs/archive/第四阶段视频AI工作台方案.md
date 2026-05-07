# SaveAny 第四阶段视频 AI 工作台方案

更新时间：2026-05-06

## 已确认需求

本阶段目标从“在首页增加一个总结按钮”升级为“独立视频工作台”。用户点击解析后进入工作台，在同一个视频任务空间中完成：

- 下载视频。
- 查看 AI 总结。
- 查看思维导图。
- 查看带时间戳的字幕。
- 与 AI 对话，基于视频内容回答问题。

已确认边界：

- 只支持公开视频。
- 平台至少覆盖 YouTube、Bilibili、Douyin。
- 优先使用平台字幕；没有字幕时尝试用 `yt-dlp` 提取字幕/自动字幕。
- 如果 `yt-dlp` 仍提取不到字幕，第一版直接提示“该视频暂无可用字幕”，暂不引入 ASR。
- LLM 使用国内模型 DeepSeek API。
- DeepSeek 第一版固定使用 `deepseek-v4-flash`，暂不考虑 `deepseek-v4-pro`。
- 继续复用现有 Next.js + FastAPI + Resolver + 任务模型，不另起一套系统。

## 重要技术澄清

`yt-dlp` 能下载平台提供的字幕、自动字幕或相关元数据，但它不是语音识别引擎。也就是说：

```text
平台有字幕 / 自动字幕
-> yt-dlp 可以尝试提取

平台完全没有字幕
-> yt-dlp 不能把音频转成文字
-> 需要 ASR 能力，例如 Whisper 或其他语音转文字服务
```

因此建议第一版字幕链路为：

```text
Resolver / 平台字幕优先
-> yt-dlp --write-subs / --write-auto-subs 兜底
-> 仍无字幕则返回 SUBTITLE_NOT_FOUND
```

第一版已确认不引入 ASR。如果必须做到“无字幕视频也能总结”，后续需要额外引入 ASR 技术栈，这会增加开发量、成本和测试复杂度。

## DeepSeek API 方案

根据 Context7 获取的 DeepSeek API 文档，DeepSeek 当前提供 OpenAI-compatible Chat Completions 接口：

```text
base_url: https://api.deepseek.com
endpoint: /chat/completions 或 /v1/chat/completions
鉴权: Authorization: Bearer ${DEEPSEEK_API_KEY}
模型示例: deepseek-v4-flash / deepseek-v4-pro
支持 response_format: { "type": "json_object" }
```

后端建议使用 Python OpenAI SDK 调用 DeepSeek：

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
```

第一版固定：

- 默认模型：`deepseek-v4-flash`，用于摘要、章节、思维导图、问答，成本和速度更适合 MVP。
- 暂不开放 `deepseek-v4-pro` 切换。
- 输出格式：总结任务使用 JSON mode，要求模型返回结构化 JSON。
- 不在前端暴露 API Key，所有 DeepSeek 调用只放在 FastAPI 后端。

## 总体交互流程

```text
首页粘贴链接
-> 点击解析
-> Next.js 调用 /api/video/info
-> 解析成功后跳转 /workspace/{sessionId 或 encoded task}
-> 工作台展示视频信息、封面、平台、时长
-> 用户可在工作台发起下载 / 总结 / 字幕 / 问答
-> FastAPI 后台创建任务
-> 前端轮询任务状态
-> 成功后展示结构化结果
```

第一版可以简化路由：

```text
/workspace?url=encodeURIComponent(videoUrl)
```

后续引入数据库后再升级为：

```text
/workspace/{workspaceId}
```

## 前端工作台设计

### 页面结构

建议新增独立页面：

```text
app/workspace/page.tsx
```

首屏布局：

- 顶部：返回首页、SaveAny 标识、当前视频标题。
- 左侧：视频信息区，包含封面、标题、作者、平台、时长、下载质量、下载按钮。
- 右侧：功能 Tab。

Tab 建议：

```text
总结
思维导图
字幕
AI 对话
```

### Tab 内容

总结：

- 整体摘要。
- 核心要点。
- 章节摘要，带开始/结束时间。
- 字幕来源提示：平台字幕 / yt-dlp 字幕 / 无字幕。

思维导图：

- 第一版不引入复杂图编辑器。
- DeepSeek 返回 Markdown 层级大纲。
- 前端先渲染为可折叠树或简洁层级列表。
- 后续再接 Markmap。

字幕：

- 带时间戳列表。
- 支持点击时间戳复制。
- 第一版不要求视频内跳转，因为当前 SaveAny 是下载工具，不一定有内嵌播放器。

AI 对话：

- 输入问题。
- 后端基于当前视频字幕/摘要构造上下文。
- 返回回答，并尽量引用相关时间戳。
- 第一版可以不做多轮长期记忆，只保留当前页面会话历史。

## 后端接口设计

### 新增任务接口

```text
POST /api/tasks/summarize
GET  /api/tasks/{task_id}
```

请求：

```json
{
  "url": "https://www.bilibili.com/video/xxx",
  "language": "zh-CN",
  "includeTranscript": true,
  "includeMindMap": true
}
```

返回：

```json
{
  "taskId": "uuid",
  "status": "pending"
}
```

任务结果：

```json
{
  "summary": "整体摘要",
  "keyPoints": ["要点 1", "要点 2"],
  "chapters": [
    {
      "title": "章节标题",
      "startTime": 0,
      "endTime": 120,
      "summary": "章节摘要"
    }
  ],
  "mindMapMarkdown": "# 视频主题\n## 分支一\n- 要点",
  "transcript": [
    {
      "startTime": 0,
      "endTime": 8,
      "text": "字幕文本"
    }
  ],
  "source": {
    "platform": "bilibili",
    "subtitleSource": "platform|yt_dlp|none",
    "language": "zh-CN"
  }
}
```

### 新增问答接口

```text
POST /api/tasks/{task_id}/chat
```

请求：

```json
{
  "question": "这个视频讲了哪些核心概念？",
  "history": [
    {
      "role": "user",
      "content": "上一个问题"
    },
    {
      "role": "assistant",
      "content": "上一个回答"
    }
  ]
}
```

返回：

```json
{
  "answer": "回答内容",
  "references": [
    {
      "startTime": 120,
      "endTime": 150,
      "text": "相关字幕片段"
    }
  ]
}
```

第一版问答依赖总结任务已成功完成，因为需要复用字幕/摘要上下文。

## 后端模块拆分

建议新增：

```text
backend/app/models/ai.py
backend/app/services/subtitle_service.py
backend/app/services/deepseek_service.py
backend/app/services/summary_service.py
backend/app/api/ai.py 或继续放入 tasks.py
```

职责：

- `subtitle_service.py`：提取字幕，统一输出时间戳结构。
- `deepseek_service.py`：封装 DeepSeek API 调用、JSON 输出解析、错误转换。
- `summary_service.py`：编排“解析视频 -> 提取字幕 -> 调用 DeepSeek -> 写入任务结果”。
- `task_service.py`：继续承担任务创建、状态更新、过期控制。

## 字幕提取策略

### YouTube

优先：

- `yt-dlp` 读取 subtitles / automatic_captions。

建议命令策略：

```text
yt-dlp --skip-download --write-subs --write-auto-subs --sub-langs "zh.*,en.*" --sub-format vtt/json3
```

### Bilibili

优先：

- 尝试从 `yt-dlp` 信息中读取字幕。
- 再尝试 `yt-dlp` 写出字幕文件。

风险：

- Bilibili 并非所有视频都有字幕。
- 有些字幕可能需要额外接口或权限，公开视频也可能没有字幕。

### Douyin

优先：

- 通过现有 `DouyinResolver` 解析公开视频。
- 尝试 `yt-dlp` 或页面元数据是否有字幕。

风险：

- 抖音公开视频大概率没有标准字幕轨。
- 如果没有字幕且不引入 ASR，第一版可能只能提示“该视频暂无可提取字幕，无法总结”。

## 错误码建议

继续复用已有错误模型，同时补充 AI 相关错误：

```text
SUBTITLE_NOT_FOUND
AI_PROVIDER_NOT_CONFIGURED
AI_PROVIDER_FAILED
AI_RESPONSE_INVALID
AI_CONTEXT_TOO_LONG
CHAT_CONTEXT_NOT_READY
```

不要为 AI 功能另起一套错误响应格式，继续使用：

```json
{
  "error": "错误文案",
  "code": "ERROR_CODE"
}
```

## 开发分步建议

### 第一步：工作台页面骨架

目标：

- 首页解析成功后跳转工作台。
- 工作台可重新加载视频信息。
- 保留现有下载能力。
- UI 有总结、思维导图、字幕、AI 对话四个 Tab，但允许部分为空状态。

验收：

```text
粘贴 YouTube/Bilibili/Douyin 公开视频
-> 解析成功
-> 跳转工作台
-> 可看到视频信息
-> 可继续下载
```

### 第二步：字幕提取任务

目标：

- 后端新增字幕提取服务。
- 支持 YouTube / Bilibili / Douyin 尝试提取字幕。
- 前端字幕 Tab 展示时间戳列表。

验收：

```text
公开视频链接
-> 创建字幕/总结任务
-> 成功提取字幕时展示时间戳字幕
-> 无字幕时给出明确错误
```

### 第三步：DeepSeek 总结任务

目标：

- 配置 `DEEPSEEK_API_KEY`。
- 后端调用 DeepSeek 生成结构化摘要。
- 返回摘要、章节、要点、思维导图 Markdown。

验收：

```text
有字幕的视频
-> 创建总结任务
-> DeepSeek 返回结构化 JSON
-> 前端总结和思维导图 Tab 可展示
```

### 第四步：基于视频内容的 AI 对话

目标：

- 新增视频问答接口。
- 基于字幕片段和摘要构造上下文。
- 回答中附带相关时间戳引用。

验收：

```text
总结任务成功后
-> 用户提问
-> AI 基于视频内容回答
-> 返回相关时间戳引用
```

### 第五步：自主测试与回归

必须验证：

```text
python -m compileall backend/app
npm run lint
FastAPI /health
FastAPI /api/system/check
YouTube 工作台链路
Bilibili 工作台链路
Douyin 工作台链路
无字幕失败提示
DeepSeek 未配置错误提示
```

如果配置了真实 `DEEPSEEK_API_KEY`，再跑真实总结与问答测试。

## 已完成开发前确认

- 如果 `yt-dlp` 也提取不到字幕，第一版直接提示“该视频暂无可用字幕”。
- DeepSeek 第一版固定使用 `deepseek-v4-flash`，暂不考虑使用 Pro 模型。

接下来按“第一步：工作台页面骨架”开始开发，再逐步接入字幕、总结、问答。

## 参考来源

- SaveAny 项目计划书
- SaveAny 技术架构方案
- SaveAny 下载功能沉淀
- SaveAny 第四阶段竞品调研
- DeepSeek API 文档（Context7）：`/websites/api-docs_deepseek_zh-cn`
