"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const FRAME_COUNT = 120;
const SMOOTHING = 0.16;
const CANDIDATE_BASES = ["/models/hero-sequence/frame_", "/hero-sequence/frame_"];

type LoadedImage = HTMLImageElement | null;

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

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

function scrollProgress() {
  const doc = document.documentElement;
  const maxScroll = Math.max(1, doc.scrollHeight - window.innerHeight);
  return clamp(window.scrollY / maxScroll, 0, 1);
}

export function CinematicSequenceBackdrop() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const imagesRef = useRef<LoadedImage[]>(Array(FRAME_COUNT).fill(null));
  const rafRef = useRef<number | null>(null);
  const targetFrameRef = useRef(0);
  const smoothFrameRef = useRef(0);
  const lastDrawnRef = useRef(-1);
  const firstFrameDrawnRef = useRef(false);

  const [, setFrame] = useState(0);

  const candidates = useMemo(
    () =>
      CANDIDATE_BASES.map((base) =>
        Array.from({ length: FRAME_COUNT }, (_, index) => `${base}${String(index).padStart(3, "0")}.jpg`),
      ),
    [],
  );

  const resizeCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 3);
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

  const draw = useCallback((value: number) => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const frameIndex = clamp(Math.round(value), 0, FRAME_COUNT - 1);
    const image = imagesRef.current[frameIndex] || imagesRef.current.find(Boolean);
    if (!image) return;

    const width = window.innerWidth;
    const height = window.innerHeight;
    const rect = coverRect(image.naturalWidth, image.naturalHeight, width, height);

    ctx.clearRect(0, 0, width, height);
    ctx.save();
    ctx.filter = "contrast(1.06) saturate(1.04) brightness(0.98)";
    ctx.drawImage(image, rect.x, rect.y, rect.width, rect.height);
    ctx.restore();

    const readability = ctx.createLinearGradient(0, 0, width, 0);
    readability.addColorStop(0, "rgba(1,6,14,0.72)");
    readability.addColorStop(0.28, "rgba(1,6,14,0.36)");
    readability.addColorStop(0.58, "rgba(1,6,14,0.14)");
    readability.addColorStop(1, "rgba(1,6,14,0.62)");
    ctx.fillStyle = readability;
    ctx.fillRect(0, 0, width, height);

    const vertical = ctx.createLinearGradient(0, 0, 0, height);
    vertical.addColorStop(0, "rgba(1,6,14,0.44)");
    vertical.addColorStop(0.42, "rgba(1,6,14,0.08)");
    vertical.addColorStop(1, "rgba(1,6,14,0.84)");
    ctx.fillStyle = vertical;
    ctx.fillRect(0, 0, width, height);

    const vignette = ctx.createRadialGradient(
      width * 0.52,
      height * 0.42,
      Math.min(width, height) * 0.18,
      width * 0.52,
      height * 0.42,
      Math.max(width, height) * 0.74,
    );
    vignette.addColorStop(0, "rgba(0,0,0,0)");
    vignette.addColorStop(0.58, "rgba(0,0,0,0.12)");
    vignette.addColorStop(1, "rgba(0,0,0,0.64)");
    ctx.fillStyle = vignette;
    ctx.fillRect(0, 0, width, height);

    lastDrawnRef.current = frameIndex;
    setFrame(frameIndex);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function findSequence() {
      for (const sourceSet of candidates) {
        const probe = new Image();
        probe.decoding = "async";
        const available = await new Promise<boolean>((resolve) => {
          probe.onload = () => resolve(true);
          probe.onerror = () => resolve(false);
          probe.src = `${sourceSet[0]}?v=${Date.now()}`;
        });

        if (!available || cancelled) continue;
        let count = 0;
        sourceSet.forEach((src, index) => {
          const image = new Image();
          image.decoding = "async";
          image.onload = () => {
            if (cancelled) return;
            imagesRef.current[index] = image;
            count += 1;
            if (!firstFrameDrawnRef.current && index === 0) {
              firstFrameDrawnRef.current = true;
              draw(0);
            }
          };
          image.onerror = () => {
            if (cancelled) return;
            count += 1;
          };
          image.src = src;
        });
        return;
      }

    }

    findSequence();
    return () => {
      cancelled = true;
    };
  }, [candidates, draw]);

  useEffect(() => {
    resizeCanvas();
    const onResize = () => {
      resizeCanvas();
      draw(smoothFrameRef.current);
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [draw, resizeCanvas]);

  useEffect(() => {
    const updateTarget = () => {
      targetFrameRef.current = scrollProgress() * (FRAME_COUNT - 1);
    };

    updateTarget();
    window.addEventListener("scroll", updateTarget, { passive: true });
    window.addEventListener("resize", updateTarget);

    const tick = () => {
      const difference = targetFrameRef.current - smoothFrameRef.current;
      if (Math.abs(difference) > 0.008) {
        smoothFrameRef.current += difference * SMOOTHING;
        const rounded = Math.round(smoothFrameRef.current);
        if (rounded !== lastDrawnRef.current) draw(smoothFrameRef.current);
      }
      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      window.removeEventListener("scroll", updateTarget);
      window.removeEventListener("resize", updateTarget);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [draw]);

  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden bg-[#020812]">
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_42%,rgba(103,232,249,0.08),transparent_28%),linear-gradient(180deg,rgba(2,8,18,0.2),rgba(2,8,18,0.34))]" />
      <div className="absolute inset-x-0 bottom-0 h-48 bg-gradient-to-t from-[#020812] to-transparent" />

    </div>
  );
}
