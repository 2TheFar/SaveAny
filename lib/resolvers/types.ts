import type { Platform } from "@/lib/platform";

export type QualityValue = "best" | "1080p" | "720p" | "audio";

export type QualityOption = {
  value: QualityValue;
  label: string;
  hint: string;
  format?: string;
  available: boolean;
};

export type MediaFormat = {
  id: string;
  ext?: string;
  resolution?: string;
  note?: string;
  height?: number;
  acodec?: string;
  vcodec?: string;
  url?: string;
};

export type ResolvedMediaInfo = {
  title: string;
  uploader?: string;
  thumbnail?: string;
  thumbnailUrl?: string;
  duration?: number;
  webpageUrl: string;
  platform: Platform;
  resolverUsed: string;
  requiresCookie: boolean;
  availableQualities: QualityOption[];
  recommendedQuality: QualityValue;
  formats: MediaFormat[];
};

export type DownloadRequest = {
  url: string;
  quality: QualityValue;
};

export type DownloadResult = {
  id: string;
  fileName: string;
  fileUrl: string;
};

export type Resolver = {
  name: string;
  canResolve(url: string): boolean;
  resolve(url: string): Promise<ResolvedMediaInfo>;
  download(request: DownloadRequest): Promise<DownloadResult>;
};
