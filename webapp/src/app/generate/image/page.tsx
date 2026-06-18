"use client";

import { useMemo, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import Image from "next/image";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuth } from "@/hooks/useAuth";
import { useGenerateImage } from "@/hooks/useGenerations";
import {
  Loader2,
  Download,
  RefreshCw,
  ImageIcon,
  ChevronRight,
  Sparkles,
  FileImage,
} from "lucide-react";

const imageStyles = [
  { value: "default", label: "Default" },
  { value: "photorealistic", label: "Photorealistic" },
  { value: "digital_art", label: "Digital Art" },
  { value: "studio", label: "Studio" },
  { value: "cinematic", label: "Cinematic" },
  { value: "neonpunk", label: "Neonpunk" },
  { value: "3d", label: "3D Render" },
];

const sizes = [
  { value: "1280x720", label: "1280×720 · production landscape", width: 1280, height: 720 },
  { value: "1024x576", label: "1024×576 · landscape", width: 1024, height: 576 },
  { value: "1024x1024", label: "1024×1024 · square", width: 1024, height: 1024 },
  { value: "768x768", label: "768×768 · square", width: 768, height: 768 },
  { value: "576x1024", label: "576×1024 · portrait", width: 576, height: 1024 },
];

const promptPresets = [
  "Clean product hero shot with premium studio lighting and realistic detail",
  "Cinematic portrait with natural light, balanced skin tones and shallow depth of field",
  "Modern social media poster with strong composition and professional visual hierarchy",
  "Luxury commercial scene with sharp subject focus, subtle reflections and polished background",
];

function errorToText(error: any) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail?.message) return detail.message;
  if (Array.isArray(detail)) return detail.map((item: any) => item?.msg || "Validation error").join(" | ");
  return error?.message || "Image generation failed.";
}

export default function GenerateImagePage() {
  useAuth();

  const [prompt, setPrompt] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("");
  const [style, setStyle] = useState("studio");
  const [size, setSize] = useState("1280x720");
  const [generatedImage, setGeneratedImage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const generateImage = useGenerateImage();
  const previewRef = useRef<HTMLDivElement | null>(null);

  const selectedSize = useMemo(
    () => sizes.find((s) => s.value === size) || sizes[0],
    [size]
  );
  const selectedStyleLabel = imageStyles.find((s) => s.value === style)?.label || "Studio";

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) {
      setErrorMessage("Prompt is required.");
      return;
    }

    try {
      setErrorMessage(null);
      setGeneratedImage(null);
      const result = await generateImage.mutateAsync({
        prompt: prompt.trim(),
        negative_prompt: negativePrompt.trim(),
        width: selectedSize.width,
        height: selectedSize.height,
        style: style && style !== "default" ? (style as any) : undefined,
      });

      if (result?.result_url) {
        setGeneratedImage(result.result_url);
        previewRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
        return;
      }

      throw new Error("No image URL was returned by the backend.");
    } catch (error) {
      console.error("Generation failed:", error);
      setErrorMessage(errorToText(error));
    }
  };

  const handleDownload = async () => {
    if (!generatedImage) return;
    try {
      const response = await fetch(generatedImage);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `generated-image-${Date.now()}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Download failed:", error);
    }
  };

  const handleRegenerate = async () => {
    const submitEvent = { preventDefault: () => {} } as FormEvent;
    await handleSubmit(submitEvent);
  };

  const isGenerating = generateImage.isPending;
  const statusText = errorMessage
    ? errorMessage
    : isGenerating
    ? "Text-to-image generation is running through the ComfyUI image pipeline."
    : generatedImage
    ? "Image generated successfully. You can preview, download, or regenerate."
    : "Ready for text-to-image generation. Use Image-to-Image from the left sidebar when you want to transform an uploaded reference.";

  return (
    <DashboardLayout>
      <div className="human-made-screen relative min-h-[calc(100vh-120px)] overflow-hidden rounded-[28px] border border-white/10 bg-black text-white shadow-[0_0_80px_rgba(217,70,239,0.08)]">
        <div className="absolute inset-0">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(217,70,239,0.14),transparent_28%),radial-gradient(circle_at_top_right,rgba(34,211,238,0.10),transparent_24%),radial-gradient(circle_at_bottom_center,rgba(239,68,68,0.10),transparent_30%),linear-gradient(180deg,#050505_0%,#090909_100%)]" />
          <div
            className="absolute inset-0 opacity-[0.18]"
            style={{
              backgroundImage: "radial-gradient(rgba(255,255,255,0.55) 0.6px, transparent 0.6px)",
              backgroundSize: "26px 26px",
            }}
          />
          <div className="absolute left-[14%] top-[20%] h-44 w-44 rounded-full bg-fuchsia-500/10 blur-3xl" />
          <div className="absolute right-[10%] top-[30%] h-52 w-52 rounded-full bg-cyan-400/10 blur-3xl" />
          <div className="absolute bottom-[10%] left-[35%] h-56 w-56 rounded-full bg-red-500/10 blur-3xl" />
        </div>

        <div className="relative z-10 p-6 md:p-8 xl:p-10">
          <div className="mb-8 flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] tracking-[0.08em] text-white/60 backdrop-blur">
                <span className="h-2 w-2 rounded-full bg-fuchsia-300" />
                Text-to-image workspace
              </div>

              <h1 className="text-4xl font-black tracking-tight md:text-5xl">
                Generate <span className="text-fuchsia-400">Images</span>
              </h1>

              <p className="mt-3 max-w-3xl text-sm leading-6 text-white/60 md:text-base">
                This page is dedicated to pure text-to-image generation. If you want to transform a person, product or object from an uploaded reference, use the dedicated Image-to-Image page from the sidebar.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Link
                href="/generate/image-to-image"
                className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-white/70 backdrop-blur transition hover:border-white/20 hover:bg-white/10 hover:text-white"
              >
                Open Image-to-Image
                <ChevronRight className="h-4 w-4" />
              </Link>
            </div>
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.02fr_0.98fr]">
            <div className="rounded-[26px] border border-white/10 bg-white/[0.04] p-5 backdrop-blur-xl md:p-6">
              <div className="mb-5 flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-fuchsia-500/10">
                  <Sparkles className="h-5 w-5 text-fuchsia-300" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold">Prompt Controls</h2>
                  <p className="text-sm text-white/50">Pure text prompt + production output</p>
                </div>
              </div>

              <form onSubmit={handleSubmit} className="space-y-5">
                <div className="space-y-2">
                  <Label className="text-[12px] uppercase tracking-[0.22em] text-white/65">Prompt presets</Label>
                  <div className="grid gap-2 md:grid-cols-2">
                    {promptPresets.map((preset) => (
                      <button
                        key={preset}
                        type="button"
                        onClick={() => setPrompt(preset)}
                        className="rounded-2xl border border-white/10 bg-white/[0.03] p-3 text-left text-xs leading-5 text-white/70 transition hover:bg-white/[0.07]"
                      >
                        {preset}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="prompt" className="text-[12px] uppercase tracking-[0.22em] text-white/65">
                    Prompt *
                  </Label>
                  <Textarea
                    id="prompt"
                    placeholder="Example: premium perfume bottle on a glossy black pedestal, elegant studio lighting, luxury ad composition, ultra clean reflections"
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    className="min-h-[160px] rounded-2xl border-white/10 bg-black/35 text-white placeholder:text-white/30 focus-visible:ring-fuchsia-400/30"
                    required
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="negative" className="text-[12px] uppercase tracking-[0.22em] text-white/65">
                    Negative Prompt
                  </Label>
                  <Input
                    id="negative"
                    placeholder="Things to avoid..."
                    value={negativePrompt}
                    onChange={(e) => setNegativePrompt(e.target.value)}
                    className="h-12 rounded-2xl border-white/10 bg-black/35 text-white placeholder:text-white/30 focus-visible:ring-fuchsia-400/30"
                  />
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label className="text-[12px] uppercase tracking-[0.22em] text-white/65">Style</Label>
                    <Select value={style} onValueChange={setStyle}>
                      <SelectTrigger className="h-12 rounded-2xl border-white/10 bg-black/35 text-white focus:ring-fuchsia-400/30">
                        <SelectValue placeholder="Select a style" />
                      </SelectTrigger>
                      <SelectContent className="border-white/10 bg-[#0b0b0f] text-white">
                        {imageStyles.map((s) => (
                          <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label className="text-[12px] uppercase tracking-[0.22em] text-white/65">Size</Label>
                    <Select value={size} onValueChange={setSize}>
                      <SelectTrigger className="h-12 rounded-2xl border-white/10 bg-black/35 text-white focus:ring-fuchsia-400/30">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="border-white/10 bg-[#0b0b0f] text-white">
                        {sizes.map((s) => (
                          <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="grid gap-3 md:grid-cols-3">
                  <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                    <div className="text-[11px] uppercase tracking-[0.22em] text-white/45">Cost</div>
                    <div className="mt-2 text-lg font-bold text-fuchsia-300">10 credits</div>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                    <div className="text-[11px] uppercase tracking-[0.22em] text-white/45">Pipeline</div>
                    <div className="mt-2 text-sm font-medium text-white/85">Text-to-Image</div>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                    <div className="text-[11px] uppercase tracking-[0.22em] text-white/45">Output</div>
                    <div className="mt-2 text-sm font-medium text-white/85">{selectedSize.label}</div>
                  </div>
                </div>

                <Button
                  type="submit"
                  className="h-12 w-full rounded-2xl bg-fuchsia-600 text-white shadow-[0_0_36px_rgba(217,70,239,0.28)] transition hover:bg-fuchsia-500"
                  disabled={isGenerating || !prompt.trim()}
                >
                  {isGenerating ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Generating...
                    </>
                  ) : (
                    <>
                      <FileImage className="mr-2 h-4 w-4" /> Generate Image
                    </>
                  )}
                </Button>
              </form>
            </div>

            <div ref={previewRef} className="rounded-[26px] border border-white/10 bg-white/[0.04] p-5 backdrop-blur-xl md:p-6">
              <div className="mb-5 flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-cyan-400/10">
                  <ImageIcon className="h-5 w-5 text-cyan-300" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold">Live Preview</h2>
                  <p className="text-sm text-white/50">Generated result appears here</p>
                </div>
              </div>

              <div className="relative overflow-hidden rounded-[24px] border border-white/10 bg-black/40">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(217,70,239,0.08),transparent_35%),radial-gradient(circle_at_bottom,rgba(34,211,238,0.06),transparent_30%)]" />
                <div className="relative aspect-video w-full items-center justify-center p-4 flex">
                  {generatedImage ? (
                    <div className="relative h-full w-full overflow-hidden rounded-[20px] border border-white/10 bg-black/20">
                      <Image src={generatedImage} alt="Generated image" fill className="object-contain" unoptimized />
                    </div>
                  ) : isGenerating ? (
                    <div className="text-center text-white/60">
                      <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full border border-white/10 bg-white/5">
                        <Loader2 className="h-7 w-7 animate-spin text-fuchsia-300" />
                      </div>
                      <p className="text-lg font-medium text-white/80">Generating image...</p>
                      <p className="mt-1 text-sm text-white/45">Please wait while the backend runs the text-to-image pipeline</p>
                    </div>
                  ) : (
                    <div className="text-center text-white/45">
                      <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full border border-white/10 bg-white/5">
                        <ImageIcon className="h-7 w-7 text-white/40" />
                      </div>
                      <p className="text-lg font-medium text-white/70">Preview ready</p>
                      <p className="mt-1 text-sm">Use a prompt to create a brand-new image</p>
                    </div>
                  )}
                </div>
              </div>

              {generatedImage && (
                <div className="mt-4 grid grid-cols-2 gap-3">
                  <Button variant="outline" className="h-11 rounded-2xl border-white/10 bg-white/5 text-white hover:bg-white/10" onClick={handleDownload}>
                    <Download className="mr-2 h-4 w-4" /> Download
                  </Button>
                  <Button variant="outline" className="h-11 rounded-2xl border-white/10 bg-white/5 text-white hover:bg-white/10" onClick={handleRegenerate} disabled={isGenerating}>
                    <RefreshCw className="mr-2 h-4 w-4" /> Regenerate
                  </Button>
                </div>
              )}

              <div className={`mt-5 rounded-2xl border p-4 ${errorMessage ? "border-red-400/25 bg-red-500/10" : "border-white/10 bg-white/[0.03]"}`}>
                <div className="text-[11px] uppercase tracking-[0.24em] text-white/45">Status</div>
                <div className={`mt-2 text-sm ${errorMessage ? "text-red-100" : "text-white/75"}`}>{statusText}</div>
              </div>

              <div className="mt-5 rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                <div className="text-[11px] uppercase tracking-[0.24em] text-white/45">Current setup</div>
                <div className="mt-3 grid gap-2 text-sm text-white/70">
                  <div>Style: <span className="text-white">{selectedStyleLabel}</span></div>
                  <div>Output size: <span className="text-white">{selectedSize.label}</span></div>
                  <div>Mode: <span className="text-white">Text-to-Image only</span></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
