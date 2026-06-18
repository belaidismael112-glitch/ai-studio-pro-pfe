export type RenderableAssetKind = "image" | "video";

function normalize(url?: string | null) {
  if (!url) return "";
  return url.split("?")[0].split("#")[0].toLowerCase();
}

export function isVideoFileUrl(url?: string | null) {
  const clean = normalize(url);
  return [".mp4", ".webm", ".mov", ".m4v", ".ogg"].some((ext) => clean.endsWith(ext));
}

export function isImageFileUrl(url?: string | null) {
  const clean = normalize(url);
  return [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg", ".avif"].some((ext) => clean.endsWith(ext));
}

export function inferRenderableAssetKind(url?: string | null, declaredKind?: string | null): RenderableAssetKind {
  if (isVideoFileUrl(url)) return "video";
  if (isImageFileUrl(url)) return "image";
  if ((declaredKind || "").toLowerCase().includes("video")) return "video";
  return "image";
}
