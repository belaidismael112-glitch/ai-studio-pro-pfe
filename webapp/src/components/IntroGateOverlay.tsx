"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const FRAME_COUNT = 192;
const FPS = 42;
const FRAME_MS = 1000 / FPS;

type IntroGateOverlayProps = {
  sequence: "home" | "login" | "register";
  label?: string;
};

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

export function IntroGateOverlay({ sequence, label = "AI Studio Pro" }: IntroGateOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const imagesRef = useRef<(HTMLImageElement | null)[]>(Array(FRAME_COUNT).fill(null));
  const rafRef = useRef<number | null>(null);
  const startedAtRef = useRef<number | null>(null);
  const lastDrawnRef = useRef(-1);
  const [ready, setReady] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [closing, setClosing] = useState(false);

  const sources = useMemo(
    () => Array.from({ length: FRAME_COUNT }, (_, index) => `/models/intro-sequences/${sequence}/${String(index).padStart(5, "0")}.jpg`),
    [sequence],
  );

  const resizeCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
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
    lastDrawnRef.current = -1;
  }, []);

  const draw = useCallback((frameIndex: number) => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    const image = imagesRef.current[frameIndex] || imagesRef.current.find(Boolean);
    if (!canvas || !ctx || !image) return;
    if (lastDrawnRef.current === frameIndex) return;

    const width = window.innerWidth;
    const height = window.innerHeight;
    const rect = coverRect(image.naturalWidth, image.naturalHeight, width, height);

    ctx.clearRect(0, 0, width, height);
    ctx.save();
    ctx.filter = "contrast(1.1) saturate(1.12) brightness(1.04)";
    ctx.drawImage(image, rect.x, rect.y, rect.width, rect.height);
    ctx.restore();

    const vignette = ctx.createRadialGradient(width * 0.5, height * 0.42, Math.min(width, height) * 0.15, width * 0.5, height * 0.42, Math.max(width, height) * 0.72);
    vignette.addColorStop(0, "rgba(0,0,0,0)");
    vignette.addColorStop(0.6, "rgba(0,0,0,0.18)");
    vignette.addColorStop(1, "rgba(0,0,0,0.68)");
    ctx.fillStyle = vignette;
    ctx.fillRect(0, 0, width, height);

    const bottom = ctx.createLinearGradient(0, 0, 0, height);
    bottom.addColorStop(0, "rgba(1,8,18,0.16)");
    bottom.addColorStop(0.72, "rgba(1,8,18,0.08)");
    bottom.addColorStop(1, "rgba(1,8,18,0.58)");
    ctx.fillStyle = bottom;
    ctx.fillRect(0, 0, width, height);

    lastDrawnRef.current = frameIndex;
  }, []);

  useEffect(() => {
    let cancelled = false;
    let loaded = 0;

    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);

    sources.forEach((src, index) => {
      const image = new Image();
      image.decoding = "async";
      image.onload = () => {
        if (cancelled) return;
        imagesRef.current[index] = image;
        loaded += 1;
        if (loaded === 1) draw(0);
        if (loaded >= Math.min(36, FRAME_COUNT)) setReady(true);
      };
      image.onerror = () => {
        if (cancelled) return;
        loaded += 1;
        if (loaded >= 24) setReady(true);
      };
      image.src = src;
    });

    return () => {
      cancelled = true;
      window.removeEventListener("resize", resizeCanvas);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [draw, resizeCanvas, sources]);

  useEffect(() => {
    if (!ready) return;

    const animate = (time: number) => {
      if (startedAtRef.current === null) startedAtRef.current = time;
      const elapsed = time - startedAtRef.current;
      const frame = Math.min(FRAME_COUNT - 1, Math.floor(elapsed / FRAME_MS));
      draw(frame);

      if (frame >= Math.floor(FRAME_COUNT * 0.66) && !closing) setClosing(true);

      if (frame < FRAME_COUNT - 1) {
        rafRef.current = requestAnimationFrame(animate);
      } else {
        setClosing(true);
        window.setTimeout(() => setHidden(true), 760);
      }
    };

    rafRef.current = requestAnimationFrame(animate);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [closing, draw, ready]);

  if (hidden) return null;

  return (
    <div
      className={`fixed inset-0 z-[999] overflow-hidden bg-[#020812] transition-opacity duration-700 ${closing ? "opacity-0" : "opacity-100"}`}
      aria-hidden="true"
    >
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" />

      <div className={`absolute inset-y-0 left-0 w-1/2 bg-[linear-gradient(90deg,#020812_0%,rgba(2,8,18,0.92)_72%,rgba(17,36,54,0.5)_100%)] shadow-[inset_-1px_0_0_rgba(103,232,249,0.26),0_0_90px_rgba(0,0,0,0.82)] transition-transform [transition-duration:1700ms] [transition-timing-function:cubic-bezier(.2,.9,.2,1)] ${ready ? "-translate-x-[104%]" : "translate-x-0"}`} />
      <div className={`absolute inset-y-0 right-0 w-1/2 bg-[linear-gradient(270deg,#020812_0%,rgba(2,8,18,0.92)_72%,rgba(17,36,54,0.5)_100%)] shadow-[inset_1px_0_0_rgba(103,232,249,0.26),0_0_90px_rgba(0,0,0,0.82)] transition-transform [transition-duration:1700ms] [transition-timing-function:cubic-bezier(.2,.9,.2,1)] ${ready ? "translate-x-[104%]" : "translate-x-0"}`} />

      <div className="absolute left-1/2 top-1/2 h-[110vh] w-px -translate-x-1/2 -translate-y-1/2 bg-cyan-200/55 shadow-[0_0_42px_rgba(103,232,249,0.85)]" />

      <div className={`absolute left-1/2 top-[70%] -translate-x-1/2 rounded-full border border-cyan-100/18 bg-black/36 px-5 py-3 text-[10px] font-black uppercase tracking-[0.36em] text-cyan-50/82 shadow-[0_22px_90px_rgba(0,0,0,0.48)] backdrop-blur-2xl transition-all duration-700 ${ready ? "opacity-0 translate-y-4" : "opacity-100"}`}>
        Opening {label}
      </div>
    </div>
  );
}
