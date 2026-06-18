"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const FRAME_COUNT = 192;
const FPS = 18;
const FRAME_MS = 1000 / FPS;
const SEQUENCE_BASE = "/models/backend-dashboard-sequence/frame_";

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

export function BackendDashboardBackdrop() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const imagesRef = useRef<LoadedImage[]>(Array(FRAME_COUNT).fill(null));
  const rafRef = useRef<number | null>(null);
  const startedAtRef = useRef<number | null>(null);
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

    const dpr = Math.min(window.devicePixelRatio || 1, 2.2);
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
    ctx.filter = "contrast(1.12) saturate(1.18) brightness(1.02)";
    ctx.drawImage(image, rect.x, rect.y, rect.width, rect.height);
    ctx.restore();

    const horizontal = ctx.createLinearGradient(0, 0, width, 0);
    horizontal.addColorStop(0, "rgba(2,8,18,0.56)");
    horizontal.addColorStop(0.18, "rgba(2,8,18,0.24)");
    horizontal.addColorStop(0.52, "rgba(2,8,18,0.04)");
    horizontal.addColorStop(0.84, "rgba(2,8,18,0.24)");
    horizontal.addColorStop(1, "rgba(2,8,18,0.54)");
    ctx.fillStyle = horizontal;
    ctx.fillRect(0, 0, width, height);

    const vertical = ctx.createLinearGradient(0, 0, 0, height);
    vertical.addColorStop(0, "rgba(2,8,18,0.34)");
    vertical.addColorStop(0.36, "rgba(2,8,18,0.08)");
    vertical.addColorStop(0.7, "rgba(2,8,18,0.12)");
    vertical.addColorStop(1, "rgba(2,8,18,0.58)");
    ctx.fillStyle = vertical;
    ctx.fillRect(0, 0, width, height);

    const vignette = ctx.createRadialGradient(
      width * 0.54,
      height * 0.42,
      Math.min(width, height) * 0.16,
      width * 0.54,
      height * 0.42,
      Math.max(width, height) * 0.8,
    );
    vignette.addColorStop(0, "rgba(0,0,0,0)");
    vignette.addColorStop(0.6, "rgba(0,0,0,0.08)");
    vignette.addColorStop(1, "rgba(0,0,0,0.44)");
    ctx.fillStyle = vignette;
    ctx.fillRect(0, 0, width, height);

    lastFrameRef.current = frameIndex;
  }, []);

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
          if (loaded >= 24) setReady(true);
        };
        image.onerror = () => {
          if (cancelled) return;
          failed += 1;
          if (failed > 20 && loaded === 0) setMissing(true);
        };
        image.src = src;
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
    resizeCanvas();
    const onResize = () => {
      resizeCanvas();
      draw(Math.max(0, lastFrameRef.current));
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [draw, resizeCanvas]);

  useEffect(() => {
    if (!ready) return;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reducedMotion) {
      draw(0);
      return;
    }

    const tick = (time: number) => {
      if (startedAtRef.current === null) startedAtRef.current = time;
      const elapsed = time - startedAtRef.current;
      const frame = Math.floor(elapsed / FRAME_MS) % FRAME_COUNT;
      if (frame !== lastFrameRef.current) draw(frame);
      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [draw, ready]);

  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden bg-[#020812]">
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_12%,rgba(34,211,238,0.10),transparent_30%),radial-gradient(circle_at_82%_18%,rgba(168,85,247,0.08),transparent_30%),linear-gradient(180deg,rgba(2,8,18,0.04),rgba(2,8,18,0.20))]" />
      <div
        className="absolute inset-0 opacity-[0.07]"
        style={{
          backgroundImage: "radial-gradient(rgba(255,255,255,0.72) 0.7px, transparent 0.7px)",
          backgroundSize: "28px 28px",
        }}
      />
      <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t from-[#020812]/70 to-transparent" />

      <div className="absolute inset-0 opacity-55 mix-blend-screen">
        <div className="absolute -left-1/3 top-1/4 h-44 w-2/3 -rotate-12 animate-[backendFlow_12s_linear_infinite] bg-[linear-gradient(90deg,transparent,rgba(103,232,249,0.12),transparent)] blur-2xl" />
        <div className="absolute -right-1/3 bottom-1/4 h-36 w-2/3 rotate-12 animate-[backendFlowReverse_14s_linear_infinite] bg-[linear-gradient(90deg,transparent,rgba(168,85,247,0.10),transparent)] blur-2xl" />
      </div>

      {!ready && !missing ? (
        <div className="absolute left-1/2 top-1/2 w-[min(86vw,360px)] -translate-x-1/2 -translate-y-1/2 rounded-[28px] border border-cyan-300/15 bg-[#06111f]/72 p-6 text-center shadow-[0_30px_120px_rgba(0,0,0,0.7)] backdrop-blur-2xl">
          <div className="mx-auto h-10 w-10 animate-spin rounded-full border border-cyan-200/20 border-t-cyan-200" />
          <div className="mt-4 text-xs font-black uppercase tracking-[0.24em] text-white/80">Loading workspace</div>
        </div>
      ) : null}

      {missing ? (
        <div className="absolute left-1/2 top-1/2 w-[min(86vw,520px)] -translate-x-1/2 -translate-y-1/2 rounded-[28px] border border-red-300/20 bg-red-950/35 p-6 text-center backdrop-blur-2xl">
          <div className="text-sm font-black text-white">Backend dashboard sequence was not found.</div>
          <div className="mt-3 text-xs leading-6 text-white/62">
            Expected frames in <strong>public/models/backend-dashboard-sequence/frame_000.jpg</strong>.
          </div>
        </div>
      ) : null}
    </div>
  );
}
