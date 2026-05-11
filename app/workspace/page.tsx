"use client";

import {
  ArrowDownToLine,
  Bot,
  CheckCircle2,
  Clock3,
  Download,
  FileText,
  FileVideo,
  Home,
  Layers3,
  Link2,
  LogOut,
  Loader2,
  Map,
  MessageSquareText,
  QrCode,
  Send,
  ShieldCheck,
  Sparkles,
  Subtitles
} from "lucide-react";
import Link from "next/link";
import type { FormEvent } from "react";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

type Quality = "best" | "1080p" | "720p" | "audio";
type WorkspaceTab = "summary" | "mindmap" | "subtitles" | "chat";
type TaskStatus = "pending" | "running" | "success" | "failed" | "expired";

type QualityOption = {
  value: Quality;
  label: string;
  hint: string;
  available: boolean;
};

type VideoInfo = {
  title: string;
  uploader?: string;
  thumbnail?: string;
  thumbnailUrl?: string;
  duration?: number;
  webpageUrl: string;
  platform: string;
  resolverUsed: string;
  requiresCookie: boolean;
  availableQualities: QualityOption[];
  recommendedQuality: Quality;
};

type DownloadResult = {
  id: string;
  fileName: string;
  fileUrl: string;
};

type TranscriptSegment = {
  startTime: number;
  endTime?: number | null;
  text: string;
};

type SubtitleResult = {
  transcript: TranscriptSegment[];
  source: {
    platform: string;
    subtitleSource:
      | "yt_dlp"
      | "bilibili_web"
      | "platform_caption"
      | "bilibili_ai_caption"
      | "bilibili_auto_caption"
      | "youtube_caption"
      | "asr_faster_whisper";
    language: string;
  };
};

type SummaryChapter = {
  title: string;
  startTime: number;
  endTime?: number | null;
  summary: string;
};

type SummaryResult = {
  summary: string;
  keyPoints: string[];
  chapters: SummaryChapter[];
  keywords: string[];
  mindMapMarkdown: string;
  source: {
    platform: string;
    subtitleSource: string;
    language: string;
  };
};

type TaskSnapshot<T = unknown> = {
  taskId: string;
  type: string;
  status: TaskStatus;
  progress: number;
  error?: string | null;
  code?: string | null;
  result?: T | null;
};

type TaskCreatePayload = {
  taskId: string;
  status: TaskStatus;
};

type BilibiliSession = {
  isLoggedIn: boolean;
  createdAt?: number | null;
  expiresAt?: number | null;
};

type BilibiliLogin = {
  loginId: string;
  qrImage: string;
  loginUrl: string;
  expiresAt: number;
  status: "pending" | "scanned" | "success" | "expired" | "failed";
};

type BilibiliLoginStatus = {
  loginId: string;
  status: "pending" | "scanned" | "success" | "expired" | "failed";
  message: string;
  expiresAt: number;
  isLoggedIn: boolean;
};

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  references?: Array<{ startTime: number; endTime?: number | null }>;
};

const defaultQualities: QualityOption[] = [
  { value: "best", label: "最佳", hint: "自动选择当前可用最高质量", available: true },
  { value: "1080p", label: "1080p", hint: "解析后按真实可用性展示", available: false },
  { value: "720p", label: "720p", hint: "解析后按真实可用性展示", available: false },
  { value: "audio", label: "仅音频", hint: "导出 MP3 音频", available: true }
];

const tabs: Array<{ value: WorkspaceTab; label: string; icon: typeof FileText }> = [
  { value: "summary", label: "总结", icon: Sparkles },
  { value: "mindmap", label: "思维导图", icon: Map },
  { value: "subtitles", label: "字幕", icon: Subtitles },
  { value: "chat", label: "AI 对话", icon: MessageSquareText }
];

export default function WorkspacePage() {
  return (
    <Suspense fallback={<WorkspaceLoading />}>
      <WorkspaceContent />
    </Suspense>
  );
}

function WorkspaceContent() {
  const searchParams = useSearchParams();
  const initialUrl = searchParams.get("url") || "";
  const [url, setUrl] = useState(initialUrl);
  const [quality, setQuality] = useState<Quality>("best");
  const [info, setInfo] = useState<VideoInfo | null>(null);
  const [download, setDownload] = useState<DownloadResult | null>(null);
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("summary");
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "downloading" | "done" | "error">(
    initialUrl ? "loading" : "idle"
  );
  const [message, setMessage] = useState(initialUrl ? "正在载入工作台..." : "请输入公开视频链接。");
  const [subtitleTask, setSubtitleTask] = useState<TaskSnapshot<SubtitleResult> | null>(null);
  const [summaryTask, setSummaryTask] = useState<TaskSnapshot<SummaryResult> | null>(null);
  const [bilibiliSession, setBilibiliSession] = useState<BilibiliSession | null>(null);
  const [bilibiliLogin, setBilibiliLogin] = useState<BilibiliLogin | null>(null);
  const [bilibiliLoginStatus, setBilibiliLoginStatus] = useState<BilibiliLoginStatus | null>(null);
  const [bilibiliAuthBusy, setBilibiliAuthBusy] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const runIdRef = useRef(0);
  const qualityRef = useRef<Quality>("best");

  const durationText = useMemo(() => formatDuration(info?.duration), [info?.duration]);
  const qualityOptions = info?.availableQualities?.length ? info.availableQualities : defaultQualities;
  const subtitles = subtitleTask?.status === "success" ? subtitleTask.result ?? null : null;
  const summary = summaryTask?.status === "success" ? summaryTask.result ?? null : null;

  useEffect(() => {
    if (!initialUrl) {
      return;
    }

    setUrl(initialUrl);
    void loadInfo(initialUrl);
  }, [initialUrl]);

  useEffect(() => {
    qualityRef.current = quality;
  }, [quality]);

  useEffect(() => {
    if (info?.platform === "bilibili") {
      void loadBilibiliSession();
      return;
    }

    setBilibiliSession(null);
    setBilibiliLogin(null);
    setBilibiliLoginStatus(null);
  }, [info?.platform]);

  async function loadInfo(targetUrl = url) {
    const cleanUrl = targetUrl.trim();
    if (!cleanUrl) {
      setStatus("error");
      setMessage("请输入公开视频链接。");
      return;
    }

    const runId = runIdRef.current + 1;
    runIdRef.current = runId;
    setStatus("loading");
    setInfo(null);
    setDownload(null);
    setSubtitleTask(null);
    setSummaryTask(null);
    setChatMessages([]);
    setMessage("正在解析视频信息...");

    try {
      const response = await fetch("/api/video/info", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: cleanUrl })
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "解析失败，请换一个公开视频链接。");
      }

      if (runIdRef.current !== runId) {
        return;
      }
      setInfo(data.info);
      setQuality(data.info.recommendedQuality || "best");
      setStatus("ready");
      setMessage(`工作台已就绪：${platformLabel(data.info.platform)} · ${data.info.resolverUsed}`);
      void startSubtitleTask(cleanUrl, runId);
    } catch (error) {
      if (runIdRef.current !== runId) {
        return;
      }
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "解析失败，请换一个公开视频链接。");
    }
  }

  async function startSubtitleTask(targetUrl: string, runId: number) {
    try {
      const created = await postJson<TaskCreatePayload>("/api/tasks/subtitles", {
        url: targetUrl,
        languagePriority: ["zh", "en"]
      });
      const task = await pollTask<SubtitleResult>(created.taskId, runId, setSubtitleTask);
      if (task?.status === "success" && task.result) {
        void startSummaryTask(targetUrl, task.taskId, runId);
      }
    } catch (error) {
      if (runIdRef.current !== runId) {
        return;
      }
      setSubtitleTask({
        taskId: "",
        type: "subtitle_extract",
        status: "failed",
        progress: 100,
        error: error instanceof Error ? error.message : "字幕提取失败。",
        code: "RESOLVER_FAILED"
      });
    }
  }

  async function startSummaryTask(targetUrl: string, subtitleTaskId: string, runId: number) {
    try {
      const created = await postJson<TaskCreatePayload>("/api/tasks/summarize", {
        url: targetUrl,
        subtitleTaskId,
        language: "zh-CN"
      });
      await pollTask<SummaryResult>(created.taskId, runId, setSummaryTask);
    } catch (error) {
      if (runIdRef.current !== runId) {
        return;
      }
      setSummaryTask({
        taskId: "",
        type: "summarize",
        status: "failed",
        progress: 100,
        error: error instanceof Error ? error.message : "视频总结失败。",
        code: "AI_PROVIDER_FAILED"
      });
    }
  }

  async function pollTask<T>(
    taskId: string,
    runId: number,
    setter: (task: TaskSnapshot<T>) => void
  ): Promise<TaskSnapshot<T> | null> {
    const deadline = Date.now() + 5 * 60_000;
    while (Date.now() < deadline) {
      if (runIdRef.current !== runId) {
        return null;
      }
      const task = await getJson<TaskSnapshot<T>>(`/api/tasks/${taskId}`);
      setter(task);
      if (task.status === "success" || task.status === "failed" || task.status === "expired") {
        return task;
      }
      await delay(1_000);
    }
    throw new Error("任务处理超时，请稍后重试。");
  }

  async function loadBilibiliSession() {
    try {
      const session = await getJson<BilibiliSession>("/api/platforms/bilibili/session");
      setBilibiliSession(session);
    } catch {
      setBilibiliSession({ isLoggedIn: false });
    }
  }

  async function startBilibiliLogin() {
    setBilibiliAuthBusy(true);
    setBilibiliLoginStatus(null);
    try {
      const login = await postJson<BilibiliLogin>("/api/platforms/bilibili/login", {});
      setBilibiliLogin(login);
      setBilibiliLoginStatus({
        loginId: login.loginId,
        status: login.status,
        message: "等待扫码",
        expiresAt: login.expiresAt,
        isLoggedIn: false
      });
      void pollBilibiliLogin(login.loginId);
    } catch (error) {
      setBilibiliLoginStatus({
        loginId: "",
        status: "failed",
        message: error instanceof Error ? error.message : "B 站登录二维码创建失败。",
        expiresAt: Date.now() / 1000,
        isLoggedIn: false
      });
    } finally {
      setBilibiliAuthBusy(false);
    }
  }

  async function pollBilibiliLogin(loginId: string) {
    const deadline = Date.now() + 3 * 60_000;
    while (Date.now() < deadline) {
      try {
        const status = await getJson<BilibiliLoginStatus>(`/api/platforms/bilibili/login/${loginId}`);
        setBilibiliLoginStatus(status);
        if (status.status === "success") {
          const selectedQuality = qualityRef.current;
          setBilibiliLogin(null);
          await loadBilibiliSession();
          await refreshInfoPreservingQuality(selectedQuality);
          return;
        }
        if (status.status === "expired" || status.status === "failed") {
          return;
        }
      } catch (error) {
        setBilibiliLoginStatus({
          loginId,
          status: "failed",
          message: error instanceof Error ? error.message : "B 站登录状态查询失败。",
          expiresAt: Date.now() / 1000,
          isLoggedIn: false
        });
        return;
      }
      await delay(1_200);
    }
  }

  async function clearBilibiliLogin() {
    setBilibiliAuthBusy(true);
    try {
      const response = await fetch("/api/platforms/bilibili/session", { method: "DELETE" });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "B 站登录态清除失败。");
      }
      setBilibiliSession(data);
      setBilibiliLogin(null);
      setBilibiliLoginStatus(null);
      await refreshInfoPreservingQuality(qualityRef.current);
    } catch (error) {
      setBilibiliLoginStatus({
        loginId: "",
        status: "failed",
        message: error instanceof Error ? error.message : "B 站登录态清除失败。",
        expiresAt: Date.now() / 1000,
        isLoggedIn: false
      });
    } finally {
      setBilibiliAuthBusy(false);
    }
  }

  async function handleDownload() {
    setStatus("downloading");
    setDownload(null);
    setMessage("正在保存视频，稍大的文件需要多等一会儿...");

    try {
      const response = await fetch("/api/video/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, quality })
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "下载失败，请确认链接可公开访问。");
      }

      setDownload(data.download);
      setStatus("done");
      setMessage("文件已准备好，可以下载到本地。");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "下载失败，请确认链接可公开访问。");
    }
  }

  async function refreshInfoPreservingQuality(preferredQuality: Quality) {
    const cleanUrl = url.trim();
    if (!cleanUrl || info?.platform !== "bilibili") {
      return;
    }

    try {
      const response = await fetch("/api/video/info", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: cleanUrl })
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "B 站质量状态刷新失败。");
      }

      setInfo(data.info);
      setQuality((current) => {
        const wanted = preferredQuality || current;
        const options = data.info.availableQualities as QualityOption[];
        return options.some((item) => item.value === wanted && item.available)
          ? wanted
          : data.info.recommendedQuality || "best";
      });
    } catch {
      // 登录态刷新失败不打断当前工作台，下载时后端仍会给出准确错误。
    }
  }

  async function handleChatSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = chatInput.trim();
    if (!question) {
      return;
    }
    setChatInput("");
    setChatMessages((current) => [...current, { role: "user", content: question }]);

    if (!summaryTask || summaryTask.status !== "success") {
      setChatMessages((current) => [
        ...current,
        { role: "assistant", content: "请等待视频总结完成后再提问。" }
      ]);
      return;
    }

    try {
      const payload = await postJson<{ answer: string; references: ChatMessage["references"] }>(
        `/api/tasks/${summaryTask.taskId}/chat`,
        {
          question,
          history: chatMessages.map(({ role, content }) => ({ role, content }))
        }
      );
      setChatMessages((current) => [
        ...current,
        { role: "assistant", content: payload.answer, references: payload.references }
      ]);
    } catch (error) {
      setChatMessages((current) => [
        ...current,
        { role: "assistant", content: error instanceof Error ? error.message : "视频问答失败。" }
      ]);
    }
  }

  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <Link className="workspace-home" href="/">
          <Home size={18} />
          SaveAny
        </Link>
        <div className="workspace-title">
          <span>{info ? platformLabel(info.platform) : "视频工作台"}</span>
          <strong>{info?.title || "解析后整理视频内容"}</strong>
        </div>
      </header>

      <section className="workspace-url">
        <div className="workspace-url-box">
          <Link2 size={20} />
          <input
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="粘贴 YouTube / Bilibili / Douyin 公开视频链接"
            aria-label="视频链接"
          />
          <button type="button" onClick={() => loadInfo()} disabled={status === "loading" || status === "downloading"}>
            {status === "loading" ? <Loader2 className="spin" size={18} /> : <Sparkles size={18} />}
            解析
          </button>
        </div>
        <StatusLine status={status} message={message} />
      </section>

      <section className="workspace-layout">
        <aside className="media-panel">
          <div className="workspace-section-title">
            <FileVideo size={19} />
            <span>视频素材</span>
          </div>

          <div className="workspace-thumb">
            {info?.thumbnailUrl ? <img src={info.thumbnailUrl} alt={info.title} /> : <FileVideo size={52} />}
          </div>

          <div className="workspace-meta">
            <h1>{info?.title || "等待解析公开视频"}</h1>
            <p>
              {info?.uploader || "公开视频"}
              {durationText ? ` · ${durationText}` : ""}
              {info ? ` · ${info.resolverUsed}` : ""}
            </p>
          </div>

          <TaskPills subtitleTask={subtitleTask} summaryTask={summaryTask} />

          {info?.platform === "bilibili" ? (
            <BilibiliAuthPanel
              session={bilibiliSession}
              login={bilibiliLogin}
              loginStatus={bilibiliLoginStatus}
              busy={bilibiliAuthBusy}
              onLogin={() => void startBilibiliLogin()}
              onClear={() => void clearBilibiliLogin()}
            />
          ) : null}

          <div className="workspace-quality" role="radiogroup" aria-label="下载质量">
            {qualityOptions.map((item) => (
              <button
                className={quality === item.value ? "workspace-quality-option active" : "workspace-quality-option"}
                key={item.value}
                type="button"
                onClick={() => item.available && setQuality(item.value)}
                disabled={!item.available || status === "loading" || status === "downloading"}
              >
                <strong>{item.label}</strong>
                <span>{item.available ? item.hint : "当前链接暂不可用"}</span>
              </button>
            ))}
          </div>

          <button
            className="workspace-download"
            type="button"
            onClick={handleDownload}
            disabled={!info || status === "loading" || status === "downloading"}
          >
            {status === "downloading" ? <Loader2 className="spin" size={19} /> : <Download size={19} />}
            下载当前质量
          </button>

          {download ? (
            <a className="workspace-file" href={download.fileUrl}>
              <ArrowDownToLine size={18} />
              {download.fileName}
            </a>
          ) : null}
        </aside>

        <section className="ai-panel">
          <div className="workspace-tabs" role="tablist" aria-label="视频 AI 工作台">
            {tabs.map((tab) => (
              <button
                className={activeTab === tab.value ? "workspace-tab active" : "workspace-tab"}
                key={tab.value}
                type="button"
                role="tab"
                aria-selected={activeTab === tab.value}
                onClick={() => setActiveTab(tab.value)}
              >
                <tab.icon size={18} />
                {tab.label}
              </button>
            ))}
          </div>

          <div className="workspace-tab-body">
            {activeTab === "summary" ? <SummaryPanel task={summaryTask} /> : null}
            {activeTab === "mindmap" ? <MindMapPanel task={summaryTask} /> : null}
            {activeTab === "subtitles" ? <SubtitlesPanel task={subtitleTask} subtitles={subtitles} /> : null}
            {activeTab === "chat" ? (
              <ChatPanel
                value={chatInput}
                messages={chatMessages}
                ready={Boolean(summary)}
                onChange={setChatInput}
                onSubmit={handleChatSubmit}
              />
            ) : null}
          </div>
        </section>
      </section>
    </main>
  );
}

function WorkspaceLoading() {
  return (
    <main className="workspace-shell">
      <div className="workspace-loading">
        <Loader2 className="spin" size={22} />
        正在打开视频工作台...
      </div>
    </main>
  );
}

function StatusLine({
  status,
  message
}: {
  status: "idle" | "loading" | "ready" | "downloading" | "done" | "error";
  message: string;
}) {
  const icon =
    status === "loading" || status === "downloading" ? (
      <Loader2 className="spin" size={17} />
    ) : status === "done" || status === "ready" ? (
      <CheckCircle2 size={17} />
    ) : status === "error" ? (
      <Clock3 size={17} />
    ) : (
      <Layers3 size={17} />
    );

  return (
    <div className={`workspace-status ${status}`}>
      {icon}
      <span>{message}</span>
    </div>
  );
}

function BilibiliAuthPanel({
  session,
  login,
  loginStatus,
  busy,
  onLogin,
  onClear
}: {
  session: BilibiliSession | null;
  login: BilibiliLogin | null;
  loginStatus: BilibiliLoginStatus | null;
  busy: boolean;
  onLogin: () => void;
  onClear: () => void;
}) {
  const isLoggedIn = Boolean(session?.isLoggedIn || loginStatus?.isLoggedIn);
  const statusText = isLoggedIn
    ? "已登录：可尝试账号权限内最高画质"
    : loginStatus?.message || "未登录：公开视频可下载，登录可解锁更高清晰度";

  return (
    <div className="bilibili-auth-panel">
      <div className="bilibili-auth-head">
        <ShieldCheck size={18} />
        <span>B 站权限</span>
      </div>
      <p>{statusText}</p>
      {login?.qrImage && !isLoggedIn ? (
        <div className="bilibili-qr-box">
          <img src={login.qrImage} alt="B 站扫码登录二维码" />
          <span>使用哔哩哔哩 App 扫码确认</span>
        </div>
      ) : null}
      <div className="bilibili-auth-actions">
        <button type="button" onClick={onLogin} disabled={busy || isLoggedIn}>
          {busy ? <Loader2 className="spin" size={16} /> : <QrCode size={16} />}
          扫码登录
        </button>
        <button type="button" onClick={onClear} disabled={busy || !isLoggedIn}>
          <LogOut size={16} />
          清除登录
        </button>
      </div>
    </div>
  );
}

function TaskPills({
  subtitleTask,
  summaryTask
}: {
  subtitleTask: TaskSnapshot<SubtitleResult> | null;
  summaryTask: TaskSnapshot<SummaryResult> | null;
}) {
  return (
    <div className="task-pills">
      <span className={taskClass(subtitleTask)}>字幕：{taskLabel(subtitleTask, "等待")}</span>
      <span className={taskClass(summaryTask)}>总结：{taskLabel(summaryTask, "等待字幕")}</span>
    </div>
  );
}

function SummaryPanel({ task }: { task: TaskSnapshot<SummaryResult> | null }) {
  if (!task || task.status === "pending" || task.status === "running") {
    return <LoadingPanel icon={Sparkles} title="正在生成视频总结" text="字幕成功后会自动调用 DeepSeek 生成学习笔记。" />;
  }

  if (task.status !== "success" || !task.result) {
    return <ErrorPanel icon={Sparkles} title="总结暂不可用" text={task.error || "视频总结失败。"} />;
  }

  const result = task.result;
  return (
    <div className="summary-panel">
      <div className="workspace-section-title">
        <Sparkles size={19} />
        <span>学习笔记</span>
      </div>
      <article className="summary-block">
        <h2>整体摘要</h2>
        <p>{result.summary}</p>
      </article>
      <article className="summary-block">
        <h2>核心要点</h2>
        <ul>
          {result.keyPoints.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </article>
      <article className="summary-block">
        <h2>章节摘要</h2>
        <div className="chapter-list">
          {result.chapters.map((chapter) => (
            <section className="chapter-item" key={`${chapter.startTime}-${chapter.title}`}>
              <span>{formatTimestamp(chapter.startTime)}</span>
              <div>
                <h3>{chapter.title}</h3>
                <p>{chapter.summary}</p>
              </div>
            </section>
          ))}
        </div>
      </article>
      <div className="keyword-row">
        {result.keywords.map((item) => (
          <span key={item}>{item}</span>
        ))}
      </div>
    </div>
  );
}

function MindMapPanel({ task }: { task: TaskSnapshot<SummaryResult> | null }) {
  if (!task || task.status === "pending" || task.status === "running") {
    return <LoadingPanel icon={Map} title="正在准备思维导图" text="总结完成后会自动渲染 Markmap 可视化导图。" />;
  }

  if (task.status !== "success" || !task.result?.mindMapMarkdown) {
    return <ErrorPanel icon={Map} title="思维导图暂不可用" text={task.error || "没有生成可展示的思维导图。"} />;
  }

  return <MarkmapViewer markdown={task.result.mindMapMarkdown} />;
}

function MarkmapViewer({ markdown }: { markdown: string }) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const instanceRef = useRef<{ fit?: () => void; destroy?: () => void } | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function render() {
      const svg = svgRef.current;
      if (!svg) {
        return;
      }
      const [{ Transformer }, { Markmap }] = await Promise.all([import("markmap-lib"), import("markmap-view")]);
      if (cancelled) {
        return;
      }
      instanceRef.current?.destroy?.();
      svg.innerHTML = "";
      const transformer = new Transformer();
      const { root } = transformer.transform(markdown);
      instanceRef.current = Markmap.create(
        svg,
        {
          zoom: true,
          pan: true,
          duration: 250,
          initialExpandLevel: 3,
          maxWidth: 320,
          spacingHorizontal: 80,
          spacingVertical: 8
        },
        root
      );
      window.setTimeout(() => instanceRef.current?.fit?.(), 80);
    }
    void render();
    return () => {
      cancelled = true;
      instanceRef.current?.destroy?.();
      instanceRef.current = null;
    };
  }, [markdown]);

  return (
    <div className="markmap-panel">
      <div className="workspace-section-title">
        <Map size={19} />
        <span>思维导图</span>
      </div>
      <svg ref={svgRef} className="markmap-svg" />
    </div>
  );
}

function SubtitlesPanel({
  task,
  subtitles
}: {
  task: TaskSnapshot<SubtitleResult> | null;
  subtitles: SubtitleResult | null;
}) {
  if (!task || task.status === "pending" || task.status === "running") {
    return <LoadingPanel icon={Subtitles} title="正在提取字幕" text="优先提取中文字幕，没有中文时回退英文字幕。" />;
  }

  if (task.status !== "success" || !subtitles) {
    return <ErrorPanel icon={Subtitles} title="字幕暂不可用" text={task.error || "该视频暂无可用字幕。"} />;
  }

  return (
    <div className="subtitle-panel">
      <div className="workspace-section-title">
        <Subtitles size={19} />
        <span>字幕展示</span>
      </div>
      <p className="source-line">
        {platformLabel(subtitles.source.platform)} · {subtitles.source.language} · {subtitles.transcript.length} 条字幕
      </p>
      <div className="subtitle-list">
        {subtitles.transcript.map((segment, index) => (
          <div className="subtitle-row" key={`${segment.startTime}-${index}`}>
            <span>{formatTimestamp(segment.startTime)}</span>
            <p>{segment.text}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function ChatPanel({
  value,
  messages,
  ready,
  onChange,
  onSubmit
}: {
  value: string;
  messages: ChatMessage[];
  ready: boolean;
  onChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <div className="chat-panel">
      <div className="chat-stream">
        {messages.length ? (
          messages.map((item, index) => (
            <div className={`chat-bubble ${item.role}`} key={`${item.role}-${index}`}>
              {item.role === "assistant" ? <Bot size={17} /> : <MessageSquareText size={17} />}
              <span>
                {item.content}
                {item.references?.length ? (
                  <small>{item.references.map((ref) => formatTimestamp(ref.startTime)).join(" · ")}</small>
                ) : null}
              </span>
            </div>
          ))
        ) : (
          <div className="workspace-empty-state compact">
            <Bot size={32} />
            <h2>向视频提问</h2>
            <p>{ready ? "可以基于字幕和总结继续提问。" : "请等待视频总结完成后再提问。"}</p>
          </div>
        )}
      </div>
      <form className="chat-input-row" onSubmit={onSubmit}>
        <input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="针对视频内容提问"
          aria-label="针对视频内容提问"
          disabled={!ready}
        />
        <button type="submit" disabled={!ready}>
          <Send size={17} />
          发送
        </button>
      </form>
    </div>
  );
}

function LoadingPanel({
  icon: Icon,
  title,
  text
}: {
  icon: typeof FileText;
  title: string;
  text: string;
}) {
  return (
    <div className="workspace-empty-state">
      <Loader2 className="spin" size={34} />
      <h2>{title}</h2>
      <p>{text}</p>
    </div>
  );
}

function ErrorPanel({
  icon: Icon,
  title,
  text
}: {
  icon: typeof FileText;
  title: string;
  text: string;
}) {
  return (
    <div className="workspace-empty-state">
      <Icon size={34} />
      <h2>{title}</h2>
      <p>{text}</p>
    </div>
  );
}

function platformLabel(platform?: string) {
  const labels: Record<string, string> = {
    youtube: "YouTube",
    bilibili: "Bilibili",
    douyin: "抖音",
    tiktok: "TikTok",
    vimeo: "Vimeo",
    x: "X",
    instagram: "Instagram",
    unknown: "通用平台"
  };

  return labels[platform || "unknown"] || "通用平台";
}

function taskLabel(task: TaskSnapshot | null, empty: string) {
  if (!task) {
    return empty;
  }
  if (task.status === "success") {
    return "完成";
  }
  if (task.status === "failed") {
    return "失败";
  }
  if (task.status === "expired") {
    return "已过期";
  }
  return "处理中";
}

function taskClass(task: TaskSnapshot | null) {
  if (!task) {
    return "";
  }
  return task.status;
}

function formatDuration(duration?: number) {
  if (!duration) {
    return "";
  }

  const minutes = Math.floor(duration / 60);
  const seconds = duration % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function formatTimestamp(value: number) {
  const total = Math.max(0, Math.floor(value));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  if (hours) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "请求失败，请稍后重试。");
  }
  return data;
}

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { cache: "no-store" });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "请求失败，请稍后重试。");
  }
  return data;
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
