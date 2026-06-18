"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname } from "next/navigation";

const FRAME_COUNT = 192;
const FPS = 18;
const FRAME_MS = 1000 / FPS;
const SEQUENCE_BASE = "/models/operator-pipeline-clean-sequence/frame_";

type LoadedImage = HTMLImageElement | null;

function coverRect(imageWidth: number, imageHeight: number, canvasWidth: number, canvasHeight: number) {
  const scale = Math.max(canvasWidth / imageWidth, canvasHeight / imageHeight);
  const width = imageWidth * scale;
  const height = imageHeight * scale;
  return {
    x: (canvasWidth - width) / 2,
    y: (canvasHeight - height) / 2,
    width,
    height,
  };
}

function pageLabel(pathname: string | null) {
  if (pathname?.includes("autonomous-platform")) return "Autonomous Platform";
  if (pathname?.includes("operator")) return "Operator Workflow";
  return "Studio Workflow";
}

function BrandPipelineBadge() {
  const pathname = usePathname();
  const label = pageLabel(pathname);

  return (
    <div className="absolute bottom-5 right-5 z-20 overflow-hidden rounded-[22px] border border-cyan-100/22 bg-[#071421]/62 px-4 py-3 shadow-[0_18px_70px_rgba(0,0,0,0.36),0_0_38px_rgba(34,211,238,0.16)] backdrop-blur-xl md:bottom-7 md:right-8">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_22%_18%,rgba(34,211,238,0.18),transparent_34%),linear-gradient(135deg,rgba(255,255,255,0.12),rgba(255,255,255,0.025)_48%,rgba(34,211,238,0.07))]" />
      <div className="relative flex items-center gap-3">
        <div className="grid h-11 w-11 shrink-0 grid-cols-2 gap-1 rounded-[14px] border border-white/12 bg-white/[0.06] p-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.10)]">
          <span className="rounded-full bg-cyan-300 shadow-[0_0_16px_rgba(103,232,249,0.95)]" />
          <span className="rounded-full bg-fuchsia-300 shadow-[0_0_16px_rgba(217,70,239,0.78)]" />
          <span className="rounded-full bg-white/28" />
          <span className="rounded-full bg-cyan-100/70 shadow-[0_0_14px_rgba(165,243,252,0.72)]" />
        </div>
        <div className="min-w-[150px]">
          <div className="text-[10px] font-black uppercase tracking-[0.28em] text-cyan-100/70">Studio Pro</div>
          <div className="mt-0.5 text-sm font-black leading-none tracking-[-0.02em] text-white drop-shadow-[0_4px_18px_rgba(0,0,0,0.9)] md:text-base">
            {label}
          </div>
        </div>
        <div className="hidden h-2.5 w-2.5 rounded-full bg-cyan-300 shadow-[0_0_18px_rgba(103,232,249,0.95)] sm:block" />
      </div>
    </div>
  );
}

export function OperatorPipelineBackdrop() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const imagesRef = useRef<LoadedImage[]>(Array(FRAME_COUNT).fill(null));
  const rafRef = useRef<number | null>(null);
  const startRef = useRef<number | null>(null);
  const lastFrameRef = useRef(-1);
  const [ready, setReady] = useState(false);
  const [missing, setMissing] = useState(false);

  const sources = useMemo(
    () => Array.from({ length: FRAME_COUNT }, (_, index) => `${SEQUENCE_BASE}${String(index).padStart(3, "0")}.jpg`),
    [],
  );

  const resizeCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2.25);
    const width = window.innerWidth;
    const height = window.innerHeight;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    lastFrameRef.current = -1;
  }, []);

  const draw = useCallback((frameIndex: number) => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    const image = imagesRef.current[frameIndex] || imagesRef.current.find(Boolean);
    if (!canvas || !ctx || !image) return;

    const width = window.innerWidth;
    const height = window.innerHeight;
    const rect = coverRect(image.naturalWidth, image.naturalHeight, width, height);

    ctx.clearRect(0, 0, width, height);
    ctx.save();
    ctx.filter = "contrast(1.22) saturate(1.36) brightness(1.14)";
    ctx.drawImage(image, rect.x, rect.y, rect.width, rect.height);
    ctx.restore();

    const readability = ctx.createLinearGradient(0, 0, width, 0);
    readability.addColorStop(0, "rgba(2,8,18,0.40)");
    readability.addColorStop(0.2, "rgba(2,8,18,0.10)");
    readability.addColorStop(0.5, "rgba(2,8,18,0.02)");
    readability.addColorStop(0.82, "rgba(2,8,18,0.12)");
    readability.addColorStop(1, "rgba(2,8,18,0.36)");
    ctx.fillStyle = readability;
    ctx.fillRect(0, 0, width, height);

    const vertical = ctx.createLinearGradient(0, 0, 0, height);
    vertical.addColorStop(0, "rgba(2,8,18,0.14)");
    vertical.addColorStop(0.45, "rgba(2,8,18,0.03)");
    vertical.addColorStop(1, "rgba(2,8,18,0.34)");
    ctx.fillStyle = vertical;
    ctx.fillRect(0, 0, width, height);

    const glow = ctx.createRadialGradient(width * 0.58, height * 0.36, 80, width * 0.58, height * 0.36, Math.max(width, height) * 0.58);
    glow.addColorStop(0, "rgba(103,232,249,0.18)");
    glow.addColorStop(0.46, "rgba(103,232,249,0.07)");
    glow.addColorStop(1, "rgba(0,0,0,0.24)");
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, width, height);

    lastFrameRef.current = frameIndex;
  }, []);

  useEffect(() => {
    resizeCanvas();
    const onResize = () => {
      resizeCanvas();
      draw(Math.max(0, lastFrameRef.current));
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [draw, resizeCanvas]);

  useEffect(() => {
    let cancelled = false;
    let loaded = 0;
    let failed = 0;

    const probe = new Image();
    probe.decoding = "async";
    probe.onload = () => {
      if (cancelled) return;
      sources.forEach((src, index) => {
        const image = new Image();
        image.decoding = "async";
        image.onload = () => {
          if (cancelled) return;
          imagesRef.current[index] = image;
          loaded += 1;
          if (loaded === 1) draw(0);
          if (loaded >= 18) setReady(true);
        };
        image.onerror = () => {
          if (cancelled) return;
          failed += 1;
          if (failed > 24 && loaded === 0) setMissing(true);
        };
        image.src = `${src}?cleanBadge=v2`;
      });
    };
    probe.onerror = () => {
      if (!cancelled) setMissing(true);
    };
    probe.src = `${sources[0]}?v=${Date.now()}`;

    return () => {
      cancelled = true;
    };
  }, [draw, sources]);

  useEffect(() => {
    if (!ready) return;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reducedMotion) {
      draw(0);
      return;
    }

    const tick = (time: number) => {
      if (startRef.current === null) startRef.current = time;
      const frame = Math.floor((time - startRef.current) / FRAME_MS) % FRAME_COUNT;
      if (frame !== lastFrameRef.current) draw(frame);
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [draw, ready]);

  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden bg-[#020812]" aria-hidden="true">
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_15%_18%,rgba(168,85,247,0.12),transparent_32%),radial-gradient(circle_at_76%_20%,rgba(34,211,238,0.15),transparent_30%),linear-gradient(180deg,rgba(2,8,18,0.02),rgba(2,8,18,0.18))]" />
      <div className="absolute inset-0 opacity-[0.06] [background-image:linear-gradient(rgba(255,255,255,0.22)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.20)_1px,transparent_1px)] [background-size:54px_54px]" />
      <div className="absolute -left-1/3 top-[22%] h-40 w-2/3 -rotate-12 animate-[operatorFlow_10s_linear_infinite] bg-[linear-gradient(90deg,transparent,rgba(103,232,249,0.24),transparent)] blur-2xl" />
      <div className="absolute -right-1/3 bottom-[18%] h-36 w-2/3 rotate-12 animate-[operatorFlowReverse_12s_linear_infinite] bg-[linear-gradient(90deg,transparent,rgba(217,70,239,0.18),transparent)] blur-2xl" />
      <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t from-[#020812]/32 to-transparent" />
      <BrandPipelineBadge />

      {missing ? (
        <div className="absolute right-6 top-24 rounded-2xl border border-red-300/20 bg-red-950/40 px-4 py-3 text-xs text-red-100 backdrop-blur-xl">
          Operator pipeline frames not found.
        </div>
      ) : null}
    </div>
  );
}
