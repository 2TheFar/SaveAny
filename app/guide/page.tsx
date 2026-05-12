import { ArrowDownToLine, CheckCircle2, Home, ShieldCheck, Sparkles } from "lucide-react";
import Link from "next/link";

const rules = [
  "只处理用户有权访问的视频链接。",
  "解析成功后再选择画质，文件需要手动点击保存。",
  "Bilibili 高清画质可能需要扫码登录后刷新。",
  "字幕、总结、导图和问答在更多 AI 功能中完成。"
];

export default function GuidePage() {
  return (
    <main className="guide-page">
      <nav className="topbar minimal-topbar">
        <Link className="brand" href="/">
          <span className="brand-mark">
            <ArrowDownToLine size={21} strokeWidth={2.6} />
          </span>
          <span>SaveAny</span>
        </Link>
        <div className="nav-links" aria-label="主导航">
          <Link href="/">保存</Link>
          <Link href="/guide">使用说明</Link>
        </div>
        <Link className="nav-action" href="/">
          <Home size={16} />
          回到首页
        </Link>
      </nav>

      <section className="guide-hero">
        <div className="eyebrow">
          <ShieldCheck size={16} />
          使用说明
        </div>
        <h1>保存、整理，各走各的路。</h1>
        <p>首页负责保存视频，需要字幕、总结和问答时再进入更多 AI 功能。</p>
      </section>

      <section className="guide-rules">
        {rules.map((rule) => (
          <article key={rule}>
            <CheckCircle2 size={20} />
            <span>{rule}</span>
          </article>
        ))}
      </section>

      <section className="guide-split">
        <article>
          <ArrowDownToLine size={24} />
          <h2>保存</h2>
          <p>粘贴链接，解析，选择画质，保存文件。</p>
        </article>
        <article>
          <Sparkles size={24} />
          <h2>AI</h2>
          <p>需要字幕、总结、导图和问答时，再进入更多 AI 功能。</p>
        </article>
      </section>
    </main>
  );
}
