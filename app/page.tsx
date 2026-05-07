"use client";

import {
  ArrowDownToLine,
  BadgeCheck,
  CheckCircle2,
  Cloud,
  Crown,
  Download,
  FileVideo,
  Languages,
  Link2,
  ListVideo,
  Loader2,
  Lock,
  Search,
  Sparkles,
  Subtitles,
  Wand2,
  Zap
} from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

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

const defaultQualities: QualityOption[] = [
  { value: "best", label: "最佳", hint: "自动选择当前可用最高质量", available: true },
  { value: "1080p", label: "1080p", hint: "解析后按真实可用性展示", available: false },
  { value: "720p", label: "720p", hint: "解析后按真实可用性展示", available: false },
  { value: "audio", label: "仅音频", hint: "导出 MP3 音频", available: true }
];

const proItems = [
  { icon: ListVideo, title: "批量下载", text: "一次提交多个链接，自动排队保存。" },
  { icon: Subtitles, title: "字幕提取", text: "自动收集字幕并生成可编辑文件。" },
  { icon: Languages, title: "字幕翻译", text: "把外语内容转成中文资料库。" },
  { icon: Cloud, title: "云端空间", text: "重要素材保存到专属空间。" }
];

const platformCards = [
  "YouTube",
  "Bilibili",
  "TikTok",
  "X",
  "Instagram",
  "Vimeo",
  "小红书",
  "更多站点"
];

export default function Home() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [quality, setQuality] = useState<Quality>("best");
  const [info, setInfo] = useState<VideoInfo | null>(null);
  const [download, setDownload] = useState<DownloadResult | null>(null);
  const [status, setStatus] = useState<"idle" | "parsing" | "ready" | "downloading" | "done" | "error">("idle");
  const [message, setMessage] = useState("粘贴公开视频链接，先解析再保存。");

  const durationText = useMemo(() => formatDuration(info?.duration), [info?.duration]);
  const qualityOptions = info?.availableQualities?.length ? info.availableQualities : defaultQualities;

  async function handleAnalyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setInfo(null);
    setDownload(null);
    setStatus("parsing");
    setMessage("正在解析视频信息...");

    try {
      const response = await fetch("/api/video/info", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url })
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "解析失败，请换一个链接试试。");
      }

      setInfo(data.info);
      setQuality(data.info.recommendedQuality || "best");
      setStatus("ready");
      setMessage(`解析完成：${platformLabel(data.info.platform)} · ${data.info.resolverUsed}`);
      router.push(`/workspace?url=${encodeURIComponent(url.trim())}`);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "解析失败，请换一个链接试试。");
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

  return (
    <main>
      <nav className="topbar">
        <a className="brand" href="#">
          <span className="brand-mark">
            <ArrowDownToLine size={21} strokeWidth={2.6} />
          </span>
          <span>SaveAny</span>
        </a>
        <div className="nav-links" aria-label="主导航">
          <a href="#features">功能</a>
          <a href="#pro">Pro</a>
          <a href="#guide">使用说明</a>
        </div>
        <a className="nav-action" href="#pro">
          <Crown size={16} />
          升级 Pro
        </a>
      </nav>

      <section className="hero">
        <div className="hero-copy">
          <div className="eyebrow">
            <BadgeCheck size={16} />
            多解析器架构的视频保存助手
          </div>
          <h1>
            复制链接，<span>SaveAny</span>
            <br />
            帮你保存重要视频
          </h1>
          <p>跨平台保存公开视频，少一步复制，多一份备份。无需安装插件，手机电脑都能用。</p>
        </div>

        <form className="search-panel" onSubmit={handleAnalyze}>
          <div className="url-box">
            <Link2 size={22} />
            <input
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="粘贴 YouTube / Bilibili / TikTok 等公开视频链接"
              aria-label="视频链接"
            />
            <button type="submit" disabled={status === "parsing" || status === "downloading"}>
              {status === "parsing" ? <Loader2 className="spin" size={18} /> : <Search size={18} />}
              解析
            </button>
          </div>

          <div className="quality-grid" role="radiogroup" aria-label="下载质量">
            {qualityOptions.map((item) => (
              <button
                className={quality === item.value ? "quality-card active" : "quality-card"}
                key={item.value}
                type="button"
                onClick={() => item.available && setQuality(item.value)}
                disabled={!item.available || status === "parsing" || status === "downloading"}
              >
                <span>{item.label}</span>
                <small>{item.available ? item.hint : "当前链接暂不可用"}</small>
              </button>
            ))}
          </div>
        </form>

        <div className={`status-strip ${status}`}>
          {status === "parsing" || status === "downloading" ? (
            <Loader2 className="spin" size={18} />
          ) : status === "done" ? (
            <CheckCircle2 size={18} />
          ) : status === "error" ? (
            <Lock size={18} />
          ) : (
            <Zap size={18} />
          )}
          <span>{message}</span>
        </div>
      </section>

      <section className="workbench" id="features">
        <article className="result-card">
          <div className="section-heading">
            <span>解析结果</span>
            <FileVideo size={20} />
          </div>

          {info ? (
            <div className="video-result">
              <div className="thumbnail">
                {info.thumbnailUrl ? <img src={info.thumbnailUrl} alt={info.title} /> : <FileVideo size={52} />}
              </div>
              <div className="video-meta">
                <h2>{info.title}</h2>
                <p>
                  {info.uploader || "公开视频"} {durationText ? `· ${durationText}` : ""} ·{" "}
                  {platformLabel(info.platform)} · {info.resolverUsed}
                </p>
                {info.requiresCookie ? (
                  <div className="notice-line">更高清晰度可能需要平台登录权限，SaveAny 默认不处理用户 Cookie。</div>
                ) : null}
                <div className="format-row">
                  {qualityOptions.map((option) => (
                    <span className={option.available ? "" : "muted-pill"} key={option.value}>
                      {option.label}: {option.available ? option.hint : "不可用"}
                    </span>
                  ))}
                </div>
                <button
                  className="download-button"
                  type="button"
                  onClick={handleDownload}
                  disabled={status === "downloading" || status === "parsing"}
                >
                  {status === "downloading" ? <Loader2 className="spin" size={19} /> : <Download size={19} />}
                  保存当前质量
                </button>
                {download ? (
                  <a className="file-link" href={download.fileUrl}>
                    <ArrowDownToLine size={18} />
                    下载文件：{download.fileName}
                  </a>
                ) : null}
              </div>
            </div>
          ) : (
            <div className="empty-result">
              <div className="mock-player">
                <div />
                <div />
                <div />
              </div>
              <h2>准备保存你的下一个重要视频</h2>
              <p>先粘贴链接解析，SaveAny 会展示标题、封面和可保存质量。</p>
            </div>
          )}
        </article>

        <aside className="platform-wall">
          <div className="section-heading">
            <span>支持平台</span>
            <Sparkles size={20} />
          </div>
          <div className="platform-grid">
            {platformCards.map((platform) => (
              <span key={platform}>{platform}</span>
            ))}
          </div>
          <p>通用平台由 yt-dlp 兜底，抖音等特殊平台将逐步接入专用 Resolver。默认只处理公开视频。</p>
        </aside>
      </section>

      <section className="pro-section" id="pro">
        <div className="pro-copy">
          <div className="eyebrow">
            <Crown size={16} />
            SaveAny Pro
          </div>
          <h2>把“能下载”升级成“会整理”</h2>
          <p>第一版先把保存链路跑通，后续可把创作者真正愿意付费的能力接在同一套工作台里。</p>
        </div>
        <div className="pro-grid">
          {proItems.map((item) => (
            <article className="pro-card" key={item.title}>
              <item.icon size={24} />
              <h3>{item.title}</h3>
              <p>{item.text}</p>
              <span>Pro 预留</span>
            </article>
          ))}
        </div>
      </section>

      <section className="guide" id="guide">
        <div className="guide-card">
          <Wand2 size={24} />
          <h2>三步保存</h2>
          <p>粘贴公开视频链接，解析信息，选择质量后下载文件。遇到私密、会员或需要登录的内容，第一版会直接提示失败。</p>
        </div>
      </section>
    </main>
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
