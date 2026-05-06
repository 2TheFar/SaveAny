import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SaveAny - 跨平台视频保存助手",
  description: "粘贴公开视频链接，使用 yt-dlp 快速保存视频。"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
