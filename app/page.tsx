"use client";

import {
  ArrowDown,
  ArrowDownToLine,
  BadgeCheck,
  CheckCircle2,
  Download,
  FileVideo,
  Globe2,
  Layers3,
  Link2,
  Loader2,
  LogOut,
  MonitorDown,
  QrCode,
  Search,
  ShieldCheck,
  Sparkles,
  Zap
} from "lucide-react";
import Link from "next/link";
import { ChangeEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";

type Quality = "best" | "1080p" | "720p" | "audio";

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
  formats: Array<{
    id: string;
    ext?: string;
    resolution?: string;
    note?: string;
  }>;
};

type DownloadResult = {
  id: string;
  fileName: string;
  fileUrl: string;
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

const defaultQualities: QualityOption[] = [
  { value: "best", label: "最佳", hint: "自动选择当前可用最高质量", available: true },
  { value: "1080p", label: "1080p", hint: "解析后按真实可用性展示", available: false },
  { value: "720p", label: "720p", hint: "解析后按真实可用性展示", available: false },
  { value: "audio", label: "仅音频", hint: "导出音频文件", available: true }
];

const platforms = ["YouTube", "Bilibili", "TikTok", "X", "Instagram", "Vimeo", "小红书", "更多站点"];

export default function Home() {
  const [url, setUrl] = useState("");
  const [resolvedUrl, setResolvedUrl] = useState("");
  const [quality, setQuality] = useState<Quality>("best");
  const [info, setInfo] = useState<VideoInfo | null>(null);
  const [download, setDownload] = useState<DownloadResult | null>(null);
  const [status, setStatus] = useState<"idle" | "parsing" | "ready" | "downloading" | "done" | "error">("idle");
  const [message, setMessage] = useState("等待链接");
  const [bilibiliSession, setBilibiliSession] = useState<BilibiliSession | null>(null);
  const [bilibiliLogin, setBilibiliLogin] = useState<BilibiliLogin | null>(null);
  const [bilibiliLoginStatus, setBilibiliLoginStatus] = useState<BilibiliLoginStatus | null>(null);
  const [bilibiliAuthBusy, setBilibiliAuthBusy] = useState(false);
  const qualityRef = useRef<Quality>("best");

  const durationText = useMemo(() => formatDuration(info?.duration), [info?.duration]);
  const qualityOptions = info?.availableQualities?.length ? info.availableQualities : defaultQualities;
  const activeUrl = info?.webpageUrl || resolvedUrl || url.trim();
  const workspaceHref = activeUrl ? `/workspace?url=${encodeURIComponent(activeUrl)}` : "/workspace";

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

  function handleUrlChange(event: ChangeEvent<HTMLInputElement>) {
    setUrl(event.target.value);
    if (download) {
      setDownload(null);
      setStatus(info ? "ready" : "idle");
      setMessage(info ? "链接已变化，重新解析后再保存。" : "等待链接");
    }
  }

  async function handleAnalyze() {
    const cleanUrl = url.trim();
    if (!cleanUrl) {
      setStatus("error");
      setMessage("请先粘贴一个视频链接。");
      return;
    }

    setInfo(null);
    setDownload(null);
    setResolvedUrl("");
    setBilibiliLogin(null);
    setBilibiliLoginStatus(null);
    setStatus("parsing");
    setMessage("正在解析...");

    try {
      const response = await fetch("/api/video/info", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: cleanUrl })
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "解析失败，请换一个链接试试。");
      }

      setInfo(data.info);
      setResolvedUrl(cleanUrl);
      setQuality(data.info.recommendedQuality || "best");
      setStatus("ready");
      setMessage("解析完成，选择画质保存");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "解析失败，请换一个链接试试。");
    }
  }

  function handleUrlKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    if (status === "parsing" || status === "downloading") {
      return;
    }
    void handleAnalyze();
  }

  async function handleDownload() {
    const targetUrl = activeUrl.trim();
    if (!targetUrl || !info) {
      setStatus("error");
      setMessage("请先解析视频，再保存。");
      return;
    }

    setStatus("downloading");
    setDownload(null);
    setMessage("保存中...");

    try {
      const response = await fetch("/api/video/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: targetUrl, quality })
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "保存失败，请确认链接可访问。");
      }

      setDownload(data.download);
      setStatus("done");
      setMessage("文件已准备好。");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "保存失败，请确认链接可访问。");
    }
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
        message: error instanceof Error ? error.message : "登录二维码创建失败。",
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
        const loginStatus = await getJson<BilibiliLoginStatus>(`/api/platforms/bilibili/login/${loginId}`);
        setBilibiliLoginStatus(loginStatus);
        if (loginStatus.status === "success") {
          const selectedQuality = qualityRef.current;
          setBilibiliLogin(null);
          await loadBilibiliSession();
          await refreshInfoPreservingQuality(selectedQuality);
          return;
        }
        if (loginStatus.status === "expired" || loginStatus.status === "failed") {
          return;
        }
      } catch (error) {
        setBilibiliLoginStatus({
          loginId,
          status: "failed",
          message: error instanceof Error ? error.message : "登录状态查询失败。",
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
        throw new Error(data.error || "登录态清除失败。");
      }
      setBilibiliSession(data);
      setBilibiliLogin(null);
      setBilibiliLoginStatus(null);
      await refreshInfoPreservingQuality(qualityRef.current);
    } catch (error) {
      setBilibiliLoginStatus({
        loginId: "",
        status: "failed",
        message: error instanceof Error ? error.message : "登录态清除失败。",
        expiresAt: Date.now() / 1000,
        isLoggedIn: false
      });
    } finally {
      setBilibiliAuthBusy(false);
    }
  }

  async function refreshInfoPreservingQuality(preferredQuality: Quality) {
    const cleanUrl = activeUrl.trim();
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
        throw new Error(data.error || "画质状态刷新失败。");
      }

      setInfo(data.info);
      setQuality((current) => {
        const wanted = preferredQuality || current;
        const options = data.info.availableQualities as QualityOption[];
        return options.some((item) => item.value === wanted && item.available)
          ? wanted
          : data.info.recommendedQuality || "best";
      });
      setStatus("ready");
      setMessage("登录状态已刷新，选择画质保存");
    } catch {
      setMessage("登录状态已变化，保存时会给出准确提示。");
    }
  }

  return (
    <main className="home-immersive">
      <nav className="home-site-nav" aria-label="主导航">
        <Link className="brand" href="/">
          <span className="brand-mark">
            <ArrowDownToLine size={21} strokeWidth={2.6} />
          </span>
          <span>SaveAny</span>
        </Link>
        <div className="nav-links">
          <a href="#intro">首页</a>
          <a href="#saveany-workbench">保存</a>
          <Link href="/guide">使用说明</Link>
        </div>
        <Link className="nav-action" href={workspaceHref}>
          <Sparkles size={16} />
          AI 功能
        </Link>
      </nav>

      <section className="snap-section intro-stage" id="intro">
        <div className="intro-shell">
          <div className="intro-copy">
            <div className="eyebrow light">
              <BadgeCheck size={16} />
              视频保存助手
            </div>
            <h1>SaveAny</h1>
            <p>世间万物它皆为我所用</p>
            <div className="intro-actions">
              <a className="primary-cta" href="#saveany-workbench">
                开始保存
                <ArrowDown size={18} />
              </a>
              <Link className="secondary-cta" href="/guide">
                查看支持规则
              </Link>
            </div>
          </div>

          <div className="intro-showcase" aria-hidden="true">
            <div className="showcase-top">
              <span />
              <span />
              <span />
            </div>
            <div className="showcase-heading">快速使用</div>
            <div className="showcase-link">
              <Link2 size={22} />
              <span>https://www.bilibili.com/video/BV...</span>
            </div>
            <div className="showcase-preview">
              <div className="showcase-thumb">
                <FileVideo size={30} />
              </div>
              <div className="showcase-meta">
                <span>Bilibili</span>
                <strong>如何高效保存视频素材</strong>
                <p>已识别 Bilibili · 可选 1080p</p>
              </div>
            </div>
            <div className="showcase-quality">
              <span className="active">1080p</span>
              <span>720p</span>
              <span>音频</span>
            </div>
            <div className="showcase-save">
              <Download size={20} />
              保存
            </div>
          </div>

          <div className="intro-benefits" aria-label="核心优势">
            <div>
              <MonitorDown size={22} />
              <strong>多平台链接</strong>
              <span>YouTube、Bilibili、TikTok、X 等视频链接。</span>
            </div>
            <div>
              <Globe2 size={22} />
              <strong>画质可选</strong>
              <span>解析后展示可用清晰度，能选才显示为可保存。</span>
            </div>
            <div>
              <Layers3 size={22} />
              <strong>手动保存</strong>
              <span>不自动下载大文件，由你确认后生成保存链接。</span>
            </div>
          </div>

          <div className="platform-row" aria-label="支持平台">
            {platforms.map((platform) => (
              <span key={platform}>{platform}</span>
            ))}
          </div>
        </div>
      </section>

      <section className="snap-section workbench-stage" id="saveany-workbench">
        <div className="workbench-shell">
          <div className="workbench-heading">
            <div>
              <h2>把视频保存到本地</h2>
              <p>先解析链接，再选择画质保存。</p>
            </div>
            <StatusStrip status={status} message={message} />
          </div>

          <div className="workbench-search">
            <div className="url-box">
              <Link2 size={22} />
              <input
                value={url}
                onChange={handleUrlChange}
                onKeyDown={handleUrlKeyDown}
                placeholder="粘贴视频链接"
                aria-label="视频链接"
              />
              <button
                type="button"
                onClick={() => void handleAnalyze()}
                disabled={status === "parsing" || status === "downloading"}
              >
                {status === "parsing" ? <Loader2 className="spin" size={18} /> : <Search size={18} />}
                解析
              </button>
            </div>
          </div>

          {info ? (
            <div className="save-console">
              <div className="media-preview">
                {info.thumbnailUrl ? <img src={info.thumbnailUrl} alt={info.title} /> : <FileVideo size={54} />}
              </div>

              <div className="download-main">
                <div className="result-title-row">
                  <span>{platformLabel(info.platform)}</span>
                  {durationText ? <span>{durationText}</span> : null}
                </div>
                <h3>{info.title}</h3>
                <p>{info.uploader || "视频"}</p>

                {info.platform === "bilibili" ? (
                  <BilibiliAuthPanel
                    session={bilibiliSession}
                    login={bilibiliLogin}
                    loginStatus={bilibiliLoginStatus}
                    busy={bilibiliAuthBusy}
                    onLogin={() => void startBilibiliLogin()}
                    onClear={() => void clearBilibiliLogin()}
                  />
                ) : null}
              </div>

              <div className="download-controls">
                <div className="quality-picker" role="radiogroup" aria-label="下载质量">
                  {qualityOptions.map((item) => (
                    <button
                      className={quality === item.value ? "quality-choice active" : "quality-choice"}
                      key={item.value}
                      type="button"
                      onClick={() => item.available && setQuality(item.value)}
                      disabled={!item.available || status === "parsing" || status === "downloading"}
                      aria-checked={quality === item.value}
                      role="radio"
                    >
                      <strong>{item.label}</strong>
                      <span>{item.available ? item.hint : "暂不可用"}</span>
                    </button>
                  ))}
                </div>

                <div className="download-actions">
                  <button
                    className="download-button"
                    type="button"
                    onClick={handleDownload}
                    disabled={status === "downloading" || status === "parsing"}
                  >
                    {status === "downloading" ? <Loader2 className="spin" size={19} /> : <Download size={19} />}
                    {status === "downloading" ? "保存中..." : "保存"}
                  </button>
                  <Link className="ai-button" href={workspaceHref}>
                    <Sparkles size={18} />
                    更多 AI 功能
                  </Link>
                </div>

                {download ? (
                  <a className="file-link minimal-file-link" href={download.fileUrl}>
                    <ArrowDownToLine size={18} />
                    {download.fileName}
                  </a>
                ) : null}
              </div>
            </div>
          ) : (
            <div className="save-console empty-console">
              <div className="empty-art" aria-hidden="true">
                <span />
                <span />
                <span />
              </div>
              <div>
                <span className="section-kicker">准备开始</span>
                <h3>粘贴一个视频链接开始</h3>
                <p>解析完成后会显示封面、可用画质和保存入口。</p>
              </div>
              <div className="empty-platforms">
                {platforms.slice(0, 6).map((platform) => (
                  <span key={platform}>{platform}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}

function StatusStrip({
  status,
  message
}: {
  status: "idle" | "parsing" | "ready" | "downloading" | "done" | "error";
  message: string;
}) {
  const icon =
    status === "parsing" || status === "downloading" ? (
      <Loader2 className="spin" size={17} />
    ) : status === "done" || status === "ready" ? (
      <CheckCircle2 size={17} />
    ) : status === "error" ? (
      <ShieldCheck size={17} />
    ) : (
      <Zap size={17} />
    );

  return (
    <div className={`status-strip ${status}`}>
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

  return (
    <div className="home-auth-panel">
      <div className="home-auth-top">
        <ShieldCheck size={17} />
        <span>{isLoggedIn ? "B 站已登录" : "B 站高清"}</span>
      </div>
      {login?.qrImage && !isLoggedIn ? (
        <div className="home-qr">
          <img src={login.qrImage} alt="B 站扫码登录二维码" />
          <span>{loginStatus?.message || "等待扫码"}</span>
        </div>
      ) : null}
      {loginStatus?.status === "failed" ? <p>{loginStatus.message}</p> : null}
      <div className="home-auth-actions">
        <button type="button" onClick={onLogin} disabled={busy || isLoggedIn}>
          {busy ? <Loader2 className="spin" size={16} /> : <QrCode size={16} />}
          登录
        </button>
        <button type="button" onClick={onClear} disabled={busy || !isLoggedIn}>
          <LogOut size={16} />
          退出
        </button>
      </div>
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

function formatDuration(duration?: number) {
  if (!duration) {
    return "";
  }

  const minutes = Math.floor(duration / 60);
  const seconds = duration % 60;
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
