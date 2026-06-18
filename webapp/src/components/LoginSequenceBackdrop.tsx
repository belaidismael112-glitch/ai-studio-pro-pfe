"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const FRAME_COUNT = 192;
const FPS = 30;
const BASES = ["/models/login-sequence/", "/login-sequence/"];

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

export function LoginSequenceBackdrop() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const imagesRef = useRef<LoadedImage[]>(Array(FRAME_COUNT).fill(null));
  const rafRef = useRef<number | null>(null);
  const activeRef = useRef(0);
  const lastTimeRef = useRef(0);
  const mouseRef = useRef({ x: 0, y: 0 });
  const [loaded, setLoaded] = useState(0);
  const [missing, setMissing] = useState(false);

  const sources = useMemo(
    () =>
      BASES.map((base) =>
        Array.from({ length: FRAME_COUNT }, (_, index) => `${base}${String(index + 1).padStart(5, "0")}.jpg`),
      ),
    [],
  );

  const resize = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    canvas.width = Math.round(window.innerWidth * dpr);
    canvas.height = Math.round(window.innerHeight * dpr);
    canvas.style.width = `${window.innerWidth}px`;
    canvas.style.height = `${window.innerHeight}px`;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
  }, []);

  const draw = useCallback((frameValue: number) => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const frame = clamp(Math.round(frameValue), 0, FRAME_COUNT - 1);
    const image = imagesRef.current[frame] || imagesRef.current.find(Boolean);
    if (!image) return;

    const width = window.innerWidth;
    const height = window.innerHeight;
    const rect = coverRect(image.naturalWidth, image.naturalHeight, width, height);
    const parallaxX = mouseRef.current.x * 18;
    const parallaxY = mouseRef.current.y * 10;

    ctx.clearRect(0, 0, width, height);
    ctx.save();
    ctx.filter = "contrast(1.12) saturate(1.12) brightness(1.04)";
    ctx.drawImage(image, rect.x + parallaxX, rect.y + parallaxY, rect.width, rect.height);
    ctx.restore();

    const formReadability = ctx.createLinearGradient(0, 0, width, 0);
    formReadability.addColorStop(0, "rgba(2,8,18,0.82)");
    formReadability.addColorStop(0.24, "rgba(2,8,18,0.55)");
    formReadability.addColorStop(0.48, "rgba(2,8,18,0.18)");
    formReadability.addColorStop(0.76, "rgba(2,8,18,0.08)");
    formReadability.addColorStop(1, "rgba(2,8,18,0.18)");
    ctx.fillStyle = formReadability;
    ctx.fillRect(0, 0, width, height);

    const vertical = ctx.createLinearGradient(0, 0, 0, height);
    vertical.addColorStop(0, "rgba(2,8,18,0.42)");
    vertical.addColorStop(0.44, "rgba(2,8,18,0.03)");
    vertical.addColorStop(1, "rgba(2,8,18,0.76)");
    ctx.fillStyle = vertical;
    ctx.fillRect(0, 0, width, height);

    const vignette = ctx.createRadialGradient(
      width * 0.62,
      height * 0.44,
      Math.min(width, height) * 0.18,
      width * 0.62,
      height * 0.44,
      Math.max(width, height) * 0.78,
    );
    vignette.addColorStop(0, "rgba(0,0,0,0)");
    vignette.addColorStop(0.62, "rgba(0,0,0,0.11)");
    vignette.addColorStop(1, "rgba(0,0,0,0.66)");
    ctx.fillStyle = vignette;
    ctx.fillRect(0, 0, width, height);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      for (const set of sources) {
        const probe = new Image();
        probe.decoding = "async";
        const ok = await new Promise<boolean>((resolve) => {
          probe.onload = () => resolve(true);
          probe.onerror = () => resolve(false);
          probe.src = `${set[0]}?v=${Date.now()}`;
        });

        if (!ok || cancelled) continue;
        setMissing(false);
        let count = 0;

        set.forEach((src, index) => {
          const image = new Image();
          image.decoding = "async";
          image.onload = () => {
            if (cancelled) return;
            imagesRef.current[index] = image;
            count += 1;
            setLoaded(count);
            if (count === 1) draw(0);
          };
          image.src = src;
        });
        return;
      }

      if (!cancelled) setMissing(true);
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [draw, sources]);

  useEffect(() => {
    resize();
    const onResize = () => {
      resize();
      draw(activeRef.current);
    };
    const onPointerMove = (event: PointerEvent) => {
      mouseRef.current = {
        x: (event.clientX / window.innerWidth - 0.5) * -1,
        y: (event.clientY / window.innerHeight - 0.5) * -1,
      };
    };

    window.addEventListener("resize", onResize);
    window.addEventListener("pointermove", onPointerMove);
    return () => {
      window.removeEventListener("resize", onResize);
      window.removeEventListener("pointermove", onPointerMove);
    };
  }, [draw, resize]);

  useEffect(() => {
    const loop = (time: number) => {
      if (!lastTimeRef.current) lastTimeRef.current = time;
      const delta = time - lastTimeRef.current;
      if (delta >= 1000 / FPS) {
        const scrollNudge = window.scrollY * 0.035;
        activeRef.current = (activeRef.current + delta / (1000 / FPS) + scrollNudge * 0.0016) % FRAME_COUNT;
        draw(activeRef.current);
        lastTimeRef.current = time;
      }
      rafRef.current = requestAnimationFrame(loop);
    };

    rafRef.current = requestAnimationFrame(loop);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [draw]);

  return (
    <div className="fixed inset-0 z-0 overflow-hidden bg-[#020812]">
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_72%_42%,rgba(34,211,238,0.12),transparent_34%),linear-gradient(90deg,rgba(2,8,18,0.18),transparent_55%,rgba(2,8,18,0.06))]" />
      <div className="pointer-events-none absolute inset-0 opacity-[0.045] [background-image:linear-gradient(rgba(255,255,255,0.16)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.12)_1px,transparent_1px)] [background-size:48px_48px]" />

      {!missing && loaded < 8 && (
        <div className="absolute bottom-8 right-8 rounded-full border border-white/10 bg-black/24 px-4 py-2 text-[10px] font-black uppercase tracking-[0.28em] text-white/48 backdrop-blur-xl">
          Loading sequence
        </div>
      )}

      {missing && (
        <div className="absolute bottom-8 right-8 max-w-sm rounded-3xl border border-red-400/20 bg-red-950/30 p-5 text-sm leading-6 text-red-100 backdrop-blur-xl">
          Login sequence files are missing. Check public/models/login-sequence/00001.jpg.
        </div>
      )}
    </div>
  );
}
