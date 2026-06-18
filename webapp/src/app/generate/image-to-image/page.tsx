"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent, type ChangeEvent } from "react";
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
import { Slider } from "@/components/ui/slider";
import { useAuth } from "@/hooks/useAuth";
import { useGenerations } from "@/hooks/useGenerations";
import { generationApi } from "@/lib/api";
import {
  Loader2,
  Download,
  RefreshCw,
  ImageIcon,
  ChevronRight,
  UploadCloud,
  Sparkles,
  Package,
  UserRound,
  PanelsTopLeft,
  Mountain,
  Wand2,
  X,
} from "lucide-react";

type ImageToImageMode =
  | "auto"
  | "person_identity"
  | "product_ad"
  | "flyer_poster"
  | "background_replace"
  | "creative_image";

const imageStyles = [
  { value: "default", label: "Default" },
  { value: "photorealistic", label: "Photorealistic" },
  { value: "digital_art", label: "Digital Art" },
  { value: "studio", label: "Studio" },
  { value: "cinematic", label: "Cinematic" },
  { value: "neonpunk", label: "Neonpunk" },
  { value: "3d", label: "3D Render" },
];


function isInternalV10AssetUrl(url?: string | null): boolean {
  const value = String(url || "").toLowerCase();
  return (
    (value.includes("v10_comfy_backdrop_") ||
      value.includes("aistudiopro_v10_backdrop_flyer") ||
      value.includes("source_lock_backdrop") ||
      value.includes("commercial_backdrop") ||
      value.includes("backdrop_flyer")) &&
    !value.includes("generated_v10_flyer_")
  );
}

function pickUserFacingResultUrl(generation: any): string | null {
  const candidates = [
    generation?.result_url,
    generation?.thumbnail_url,
    generation?.url,
    generation?.final_url,
    generation?.metadata?.final_url,
    generation?.metadata?.final_result_url,
    generation?.metadata?.user_facing_url,
  ];

  for (const candidate of candidates) {
    if (candidate && !isInternalV10AssetUrl(candidate)) {
      return candidate;
    }
  }

  return null;
}

const modes: Array<{
  value: ImageToImageMode;
  label: string;
  icon: any;
  description: string;
  hint: string;
  example: string;
}> = [
  {
    value: "auto",
    label: "Auto Smart",
    icon: Sparkles,
    description: "Detects whether the upload is a person, product or object and routes it to the best source-lock workflow.",
    hint: "Best when you want the app to decide between identity, product, poster or creative routing.",
    example: "Turn this upload into a polished hero visual while keeping the main subject clear and recognizable.",
  },
  {
    value: "person_identity",
    label: "Person / Identity",
    icon: UserRound,
    description: "Same person, new scene, new outfit, new styling or poster while preserving the facial identity.",
    hint: "Use for portraits, same-person scene changes and identity-preserving visuals.",
    example: "Same person in a modern studio portrait, balanced lighting, clean background, realistic detail.",
  },
  {
    value: "product_ad",
    label: "Product Ad",
    icon: Package,
    description: "Creates a visibly new commercial composition for a bottle, watch, shoe, bag or any product.",
    hint: "Use for premium e-commerce visuals, splash ads and hero product compositions.",
    example: "Create a premium hero product advertisement with glossy reflections, a stronger commercial background, polished lighting and a clearly new composition.",
  },
  {
    value: "flyer_poster",
    label: "Flyer / Poster",
    icon: PanelsTopLeft,
    description: "Builds a marketing flyer or poster from the upload with structured space for headline and call-to-action.",
    hint: "Use when you want a social post, promo poster, menu visual or campaign flyer.",
    example: "Create a polished social media flyer with strong background styling, clean space for headline, price and CTA, and a clearly transformed poster composition.",
  },
  {
    value: "background_replace",
    label: "Background Replace",
    icon: Mountain,
    description: "Preserves the main subject and changes the environment clearly.",
    hint: "Use to place the same person or product in a new scene without redesigning the subject.",
    example: "Keep the subject identical and place it cleanly into a clearly different premium environment.",
  },
  {
    value: "creative_image",
    label: "Creative Reference",
    icon: Wand2,
    description: "Uses the uploaded image as visual source material for a more transformed creative composition.",
    hint: "Use for cinematic, stylized or editorial reinterpretations of the uploaded image.",
    example: "Transform the upload into a cinematic editorial visual with dramatic mood, premium composition and a noticeably stronger reinterpretation.",
  },
];

const sizes = [
  { value: "1280x720", label: "1280×720 · production landscape", width: 1280, height: 720 },
  { value: "1024x576", label: "1024×576 · landscape", width: 1024, height: 576 },
  { value: "1024x1024", label: "1024×1024 · square", width: 1024, height: 1024 },
  { value: "768x768", label: "768×768 · square", width: 768, height: 768 },
  { value: "576x1024", label: "576×1024 · portrait", width: 576, height: 1024 },
];

function errorToText(error: any) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail?.message) {
    const risks = detail?.details?.risks;
    const extra = Array.isArray(risks) && risks.length ? ` ${risks.join(" ")}` : "";
    return `${detail.message}${extra}`;
  }
  if (Array.isArray(detail)) return detail.map((item: any) => item?.msg || "Validation error").join(" | ");
  return error?.message || "Image generation failed.";
}

function defaultStrength(mode: ImageToImageMode) {
  if (mode === "person_identity") return 18;
  if (mode === "background_replace") return 46;
  if (mode === "product_ad") return 60;
  if (mode === "flyer_poster") return 68;
  if (mode === "creative_image") return 68;
  return 48;
}

function preserveLabel(value: number) {
  if (value <= 28) return "Conservative";
  if (value <= 48) return "Balanced";
  if (value <= 65) return "Transforming";
  return "Creative";
}

function buildPrompt(params: {
  mode: ImageToImageMode;
  prompt: string;
  sceneBrief: string;
  designBrief: string;
  headline: string;
  subheadline: string;
  cta: string;
}) {
  const base = params.prompt.trim();
  const scene = params.sceneBrief.trim();
  const design = params.designBrief.trim();
  const headline = params.headline.trim();
  const subheadline = params.subheadline.trim();
  const cta = params.cta.trim();

  if (params.mode === "person_identity") {
    return [
      base,
      scene ? `Requested scene or outfit: ${scene}.` : "Preserve the same person and make only the requested scene or styling change.",
      design ? `Styling notes: ${design}.` : "Keep the exact face, age impression, wrinkles and facial proportions stable. Change only scene, outfit or styling.",
    ].join(" ").trim();
  }

  if (params.mode === "product_ad") {
    return [
      base,
      scene ? `Advertising environment: ${scene}.` : "Create a premium commercial scene around the uploaded product.",
      design ? `Commercial direction: ${design}.` : "Use a polished studio-ad look with strong composition and clean highlights.",
    ].join(" ").trim();
  }

  if (params.mode === "flyer_poster") {
    return [
      base,
      scene ? `Poster scene or background: ${scene}.` : "Create a clean marketing flyer or poster composition.",
      design ? `Layout and style direction: ${design}.` : "Keep the main subject dominant and leave room for marketing text.",
      headline ? `Headline idea: ${headline}.` : "",
      subheadline ? `Secondary text idea: ${subheadline}.` : "",
      cta ? `CTA or price note: ${cta}.` : "",
    ].filter(Boolean).join(" ").trim();
  }

  if (params.mode === "background_replace") {
    return [
      base,
      scene ? `Replace the background with: ${scene}.` : "Replace the background clearly while keeping the subject unchanged.",
      design ? `Environment style: ${design}.` : "Do not redesign the main subject.",
    ].join(" ").trim();
  }

  if (params.mode === "creative_image") {
    return [
      base,
      scene ? `Creative scene direction: ${scene}.` : "Create a visibly transformed creative composition from the upload.",
      design ? `Mood and creative style: ${design}.` : "Use a stronger editorial or cinematic reinterpretation.",
    ].join(" ").trim();
  }

  return [
    base,
    scene ? `Extra scene direction: ${scene}.` : "Use the uploaded image as the source and choose the best image-to-image pipeline automatically.",
    design ? `Creative notes: ${design}.` : "Keep the uploaded subject clear and coherent.",
  ].join(" ").trim();
}

export default function GenerateImageToImagePage() {
  useAuth();

  const [mode, setMode] = useState<ImageToImageMode>("auto");
  const [prompt, setPrompt] = useState("");
  const [sceneBrief, setSceneBrief] = useState("");
  const [designBrief, setDesignBrief] = useState("");
  const [headline, setHeadline] = useState("");
  const [subheadline, setSubheadline] = useState("");
  const [cta, setCta] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("");
  const [applyTemplateOverlay, setApplyTemplateOverlay] = useState(false);
  const [identityBoard, setIdentityBoard] = useState(false);
  const [style, setStyle] = useState("studio");
  const [size, setSize] = useState("1280x720");
  const [referenceStrength, setReferenceStrength] = useState<number[]>([defaultStrength("auto")]);
  const [referenceFile, setReferenceFile] = useState<File | null>(null);
  const [referencePreview, setReferencePreview] = useState<string | null>(null);
  const [referenceDimensions, setReferenceDimensions] = useState<{ width: number; height: number } | null>(null);
  const [generatedImage, setGeneratedImage] = useState<string | null>(null);
  const [currentGenerationId, setCurrentGenerationId] = useState<number | null>(null);
  const [isWaitingForResult, setIsWaitingForResult] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const previewRef = useRef<HTMLDivElement | null>(null);

  const generationsQuery = useGenerations({ page: 1, page_size: 20 });

  const selectedSize = useMemo(
    () => sizes.find((s) => s.value === size) || sizes[0],
    [size]
  );
  const selectedMode = modes.find((item) => item.value === mode) || modes[0];
  const selectedStyleLabel = imageStyles.find((s) => s.value === style)?.label || "Studio";
  const effectiveStrength = referenceStrength[0] / 100;
  const commercialMode = mode === "product_ad" || mode === "flyer_poster";
  const commercialSourceNeedsEnhancement = Boolean(
    commercialMode && referenceDimensions && (
      Math.max(referenceDimensions.width, referenceDimensions.height) < 1200 ||
      Math.min(referenceDimensions.width, referenceDimensions.height) < 420
    )
  );
  const commercialSourceTooSmall = Boolean(
    commercialMode && referenceDimensions && (
      Math.max(referenceDimensions.width, referenceDimensions.height) < 720 ||
      Math.min(referenceDimensions.width, referenceDimensions.height) < 240
    )
  );

  useEffect(() => {
    setReferenceStrength([defaultStrength(mode)]);
    setSceneBrief("");
    setDesignBrief("");
    setHeadline("");
    setSubheadline("");
    setCta("");
    setApplyTemplateOverlay(mode === "flyer_poster");
    setIdentityBoard(true);
    if (mode === "person_identity") setSize("1280x720");
    setPrompt(selectedMode.example);
  }, [mode, selectedMode.example]);

  useEffect(() => {
    if (!referenceFile) {
      setReferencePreview(null);
      return;
    }

    const url = URL.createObjectURL(referenceFile);
    setReferencePreview(url);
    return () => URL.revokeObjectURL(url);
  }, [referenceFile]);

  async function pollGeneration(id: number) {
    setIsWaitingForResult(true);
    setErrorMessage(null);

    const maxAttempts = 300;
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise((resolve) => setTimeout(resolve, 2000));
      const response = await generationApi.getGeneration(id);
      const current = response.data as any;

      if (current.status === "completed") {
        const userFacingUrl = pickUserFacingResultUrl(current);
        if (!userFacingUrl) {
          throw new Error("Final composed image was not returned. Internal ComfyUI backdrop is hidden from user preview.");
        }
        setGeneratedImage(userFacingUrl);
        setIsWaitingForResult(false);
        generationsQuery.refetch();
        previewRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
        return;
      }

      if (current.status === "failed") {
        throw new Error(current.error_message || "Image generation failed.");
      }
    }

    throw new Error("Image generation timed out. Check History or ComfyUI queue.");
  }

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] || null;
    setReferenceFile(file);
    setReferenceDimensions(null);
    if (!file) return;

    const objectUrl = URL.createObjectURL(file);
    const probe = document.createElement("img");
    probe.onload = () => {
      setReferenceDimensions({ width: probe.naturalWidth, height: probe.naturalHeight });
      URL.revokeObjectURL(objectUrl);
    };
    probe.onerror = () => URL.revokeObjectURL(objectUrl);
    probe.src = objectUrl;
  };

  const clearReference = () => {
    setReferenceFile(null);
    setReferenceDimensions(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleUseExample = () => {
    setPrompt(selectedMode.example);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    if (!referenceFile) {
      setErrorMessage("Upload a reference image first. The Image-to-Image page works only with a source image.");
      return;
    }

    if (!prompt.trim()) {
      setErrorMessage("Describe the result you want from the uploaded reference.");
      return;
    }

    if (commercialSourceTooSmall) {
      setErrorMessage(
        "This image is too small for a production-quality product result. Upload a clearer packshot with at least 720px on its longest side and 240px on its shortest side."
      );
      return;
    }

    try {
      setGeneratedImage(null);
      setErrorMessage(null);
      setCurrentGenerationId(null);
      setIsWaitingForResult(false);

      const effectivePrompt = buildPrompt({
        mode,
        prompt,
        sceneBrief,
        designBrief,
        headline,
        subheadline,
        cta,
      });

      const formData = new FormData();
      formData.append("image", referenceFile);
      formData.append("prompt", effectivePrompt);
      formData.append("negative_prompt", negativePrompt.trim());
      formData.append("style", style && style !== "default" ? style : "studio");
      formData.append("size", selectedSize.value);
      formData.append("generation_mode", mode);
      formData.append("subject_lock", "true");
      // Keep the full packshot for commercial composition modes. Tight crops
      // make bottles/cans look narrow and reduce the model's scene-building room.
      const allowAutoCrop = mode === "person_identity";
      formData.append("auto_crop", String(allowAutoCrop));
      formData.append("apply_template_overlay", String(mode === "flyer_poster" && Boolean(headline.trim() || subheadline.trim() || cta.trim())));
      // FINAL PRO FIX: Neural Camera report is diagnostic UI only.
      // Do not send identity_board=true to the final generation endpoint;
      // otherwise the backend returns the report board instead of the AI image.
      formData.append("identity_board", "false");
      formData.append("strength", String(effectiveStrength));

      const response = await generationApi.generateImageFromReference(formData, mode);
      const result = response.data as any;

      if (result?.result_url) {
        setGeneratedImage(result.result_url);
        previewRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
        return;
      }

      if (result?.id) {
        setCurrentGenerationId(result.id);
        await pollGeneration(result.id);
        return;
      }

      throw new Error("No generation ID was returned by the backend.");
    } catch (error) {
      console.error("Generation failed:", error);
      setErrorMessage(errorToText(error));
      setIsWaitingForResult(false);
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

  const isGenerating = isWaitingForResult;
  const displayHint = errorMessage
    ? "If the page looks cramped on laptop screens, use browser zoom 90% to 100%. V7.1 also improves wrapping and preview sizing."
    : "";

  const statusText = errorMessage
    ? errorMessage
    : isGenerating
    ? `Running ${selectedMode.label} through its own dedicated image-to-image service endpoint and ComfyUI pipeline.`
    : generatedImage
    ? "Image-to-image result generated successfully. You can preview, download or regenerate."
    : "Ready for reference-based generation. Upload a source image, choose a dedicated mode, then generate a transformed result.";

  return (
    <DashboardLayout>
      <div className="human-made-screen relative min-h-[calc(100vh-120px)] overflow-x-hidden overflow-y-visible rounded-[28px] border border-white/10 bg-black text-white shadow-[0_0_80px_rgba(34,211,238,0.08)]">
        <div className="absolute inset-0">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.14),transparent_28%),radial-gradient(circle_at_top_right,rgba(217,70,239,0.10),transparent_24%),radial-gradient(circle_at_bottom_center,rgba(59,130,246,0.10),transparent_30%),linear-gradient(180deg,#050505_0%,#090909_100%)]" />
          <div
            className="absolute inset-0 opacity-[0.16]"
            style={{
              backgroundImage: "radial-gradient(rgba(255,255,255,0.52) 0.6px, transparent 0.6px)",
              backgroundSize: "26px 26px",
            }}
          />
          <div className="absolute left-[10%] top-[24%] h-48 w-48 rounded-full bg-cyan-400/10 blur-3xl" />
          <div className="absolute right-[8%] top-[18%] h-56 w-56 rounded-full bg-fuchsia-500/10 blur-3xl" />
          <div className="absolute bottom-[12%] left-[38%] h-56 w-56 rounded-full bg-blue-500/10 blur-3xl" />
        </div>

        <div className="relative z-10 p-6 md:p-8 xl:p-10">
          <div className="mb-8 flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] tracking-[0.08em] text-white/60 backdrop-blur">
                <span className="h-2 w-2 rounded-full bg-cyan-300" />
                Dedicated reference studio
              </div>

              <h1 className="text-4xl font-black tracking-tight md:text-5xl">
                Image-to-<span className="text-cyan-300">Image</span>
              </h1>

              <p className="mt-3 max-w-3xl text-sm leading-6 text-white/60 md:text-base">
                This page is different from Generate Images. It is built only for uploaded references, and each of the 6 modes now runs through its own dedicated image-to-image route to avoid cross-mode conflicts.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Link
                href="/generate/image"
                className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-white/70 backdrop-blur transition hover:border-white/20 hover:bg-white/10 hover:text-white"
              >
                Pure Generate Images
                <ChevronRight className="h-4 w-4" />
              </Link>
            </div>
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.08fr_0.92fr] items-start">
            <div className="space-y-6">
              <div className="rounded-[26px] border border-white/10 bg-white/[0.04] p-5 backdrop-blur-xl md:p-6">
                <div className="mb-5 flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-cyan-400/10">
                    <ImageIcon className="h-5 w-5 text-cyan-300" />
                  </div>
                  <div>
                    <h2 className="text-lg font-semibold">Reference Source</h2>
                    <p className="text-sm text-white/50">Image-to-image requires an uploaded image</p>
                  </div>
                </div>

                <div className="rounded-3xl border border-dashed border-white/15 bg-black/30 p-4">
                  {referencePreview ? (
                    <div className="grid gap-4 md:grid-cols-[180px_1fr]">
                      <div className="relative aspect-video overflow-hidden rounded-2xl border border-white/10 bg-black/40">
                        <Image src={referencePreview} alt="Reference preview" fill className="object-cover" unoptimized />
                      </div>
                      <div className="flex flex-col justify-center gap-3">
                        <div>
                          <p className="text-sm font-semibold text-white">{referenceFile?.name}</p>
                          <p className="text-xs text-white/50">
                            {commercialMode
                              ? "Product Ad and Flyer keep the full packshot. The backend analyses, cuts and source-locks the detected product before credits are used."
                              : "The backend analyses the reference first. Object sources can use saved transparent source-lock assets; person identity stays on the conservative identity workflow."}
                          </p>
                          {referenceDimensions && (
                            <p className={`mt-1 text-xs ${commercialSourceTooSmall || commercialSourceNeedsEnhancement ? "text-amber-300" : "text-cyan-200"}`}>
                              Source: {referenceDimensions.width}×{referenceDimensions.height}px
                              {commercialSourceTooSmall
                                ? " · too small for production source-lock"
                                : commercialSourceNeedsEnhancement
                                ? " · accepted for inspection; a larger 1200px+ packshot is recommended for sharper packaging"
                                : " · ready for backend inspection"}
                            </p>
                          )}
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Button type="button" variant="outline" onClick={() => fileInputRef.current?.click()} className="rounded-2xl border-white/10 bg-white/5 text-white hover:bg-white/10">
                            <UploadCloud className="mr-2 h-4 w-4" /> Change
                          </Button>
                          <Button type="button" variant="outline" onClick={clearReference} className="rounded-2xl border-red-400/20 bg-red-500/10 text-red-100 hover:bg-red-500/15">
                            <X className="mr-2 h-4 w-4" /> Remove
                          </Button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      className="flex w-full flex-col items-center justify-center rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-10 text-center transition hover:bg-white/[0.06]"
                    >
                      <UploadCloud className="mb-3 h-8 w-8 text-cyan-300" />
                      <span className="text-sm font-semibold text-white">Upload or capture a reference</span>
                      <span className="mt-1 text-xs text-white/45">Person, product, bottle, watch, shoe, poster source, object</span>
                    </button>
                  )}
                  <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFileChange} className="hidden" />
                </div>
              </div>

              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="rounded-[26px] border border-white/10 bg-white/[0.04] p-5 backdrop-blur-xl md:p-6">
                  <div className="mb-5 flex items-center gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-fuchsia-500/10">
                      <Sparkles className="h-5 w-5 text-fuchsia-300" />
                    </div>
                    <div>
                      <h2 className="text-lg font-semibold">Choose a real mode</h2>
                      <p className="text-sm text-white/50">Each mode now has its own purpose and guidance</p>
                    </div>
                  </div>

                  <div className="grid gap-3 md:grid-cols-2">
                    {modes.map((item) => {
                      const Icon = item.icon;
                      const active = item.value === mode;
                      return (
                        <button
                          key={item.value}
                          type="button"
                          onClick={() => setMode(item.value)}
                          className={`rounded-2xl border p-4 text-left transition ${
                            active
                              ? "border-cyan-400/45 bg-cyan-500/15 shadow-[0_0_30px_rgba(34,211,238,0.12)]"
                              : "border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
                          }`}
                        >
                          <div className="flex items-start gap-3">
                            <span className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-black/25">
                              <Icon className="h-4 w-4 text-cyan-200" />
                            </span>
                            <div>
                              <p className="text-sm font-semibold text-white">{item.label}</p>
                              <p className="mt-1 text-xs leading-5 text-white/45">{item.description}</p>
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>

                  <div className="mt-4 rounded-2xl border border-cyan-400/20 bg-cyan-500/10 p-4">
                    <div className="text-[11px] uppercase tracking-[0.22em] text-cyan-100/70">Current mode</div>
                    <div className="mt-2 text-sm text-white/90">{selectedMode.label}</div>
                    <div className="mt-2 text-xs leading-5 text-cyan-100/70">{selectedMode.hint}</div>
                  </div>
                </div>

                <div className="rounded-[26px] border border-white/10 bg-white/[0.04] p-5 backdrop-blur-xl md:p-6 space-y-5">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <h2 className="text-lg font-semibold">Mode tools</h2>
                      <p className="text-sm text-white/50">Extra controls that make Image-to-Image different from Generate Images</p>
                    </div>
                    <Button type="button" variant="outline" onClick={handleUseExample} className="rounded-2xl border-white/10 bg-white/5 text-white hover:bg-white/10">
                      Use example
                    </Button>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="prompt" className="text-[12px] uppercase tracking-[0.22em] text-white/65">Main prompt *</Label>
                    <Textarea
                      id="prompt"
                      placeholder={selectedMode.example}
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      className="min-h-[120px] rounded-2xl border-white/10 bg-black/35 text-white placeholder:text-white/30 focus-visible:ring-cyan-400/30"
                      required
                    />
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label className="text-[12px] uppercase tracking-[0.22em] text-white/65">Scene / environment</Label>
                      <Input
                        placeholder={mode === "background_replace" ? "Luxury showroom, beach sunset, restaurant interior..." : "Optional scene direction..."}
                        value={sceneBrief}
                        onChange={(e) => setSceneBrief(e.target.value)}
                        className="h-12 rounded-2xl border-white/10 bg-black/35 text-white placeholder:text-white/30"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-[12px] uppercase tracking-[0.22em] text-white/65">Design / style notes</Label>
                      <Input
                        placeholder={mode === "product_ad" ? "Splash, glossy, luxury, minimal, editorial..." : "Optional design notes..."}
                        value={designBrief}
                        onChange={(e) => setDesignBrief(e.target.value)}
                        className="h-12 rounded-2xl border-white/10 bg-black/35 text-white placeholder:text-white/30"
                      />
                    </div>
                  </div>

                  {mode === "person_identity" && (
                    <div className="rounded-2xl border border-violet-400/20 bg-violet-500/[0.07] p-4">
                      <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-white/10 bg-black/20 p-4">
                        <input
                          type="checkbox"
                          checked={identityBoard}
                          onChange={(e) => setIdentityBoard(e.target.checked)}
                          className="mt-1 h-4 w-4 accent-violet-400"
                        />
                        <span>
                          <span className="block text-sm font-semibold text-white/90">Create Neural Camera analysis report</span>
                          <span className="mt-1 block text-xs leading-5 text-white/50">Optional report only. Leave this OFF for the actual AI identity generation. Turn it ON only when you want a source-lock diagnostic board for review.</span>
                        </span>
                      </label>
                    </div>
                  )}

                  {mode === "flyer_poster" && (
                    <div className="space-y-4 rounded-2xl border border-cyan-400/20 bg-cyan-500/[0.07] p-4">
                      <div className="grid gap-4 md:grid-cols-3">
                        <div className="space-y-2">
                          <Label className="text-[12px] uppercase tracking-[0.22em] text-white/65">Headline idea</Label>
                          <Input value={headline} onChange={(e) => setHeadline(e.target.value)} placeholder="Summer promo" className="h-12 rounded-2xl border-white/10 bg-black/35 text-white placeholder:text-white/30" />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-[12px] uppercase tracking-[0.22em] text-white/65">Subheadline</Label>
                          <Input value={subheadline} onChange={(e) => setSubheadline(e.target.value)} placeholder="Limited time only" className="h-12 rounded-2xl border-white/10 bg-black/35 text-white placeholder:text-white/30" />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-[12px] uppercase tracking-[0.22em] text-white/65">CTA / price note</Label>
                          <Input value={cta} onChange={(e) => setCta(e.target.value)} placeholder="Order now · 19 DT" className="h-12 rounded-2xl border-white/10 bg-black/35 text-white placeholder:text-white/30" />
                        </div>
                      </div>
                      <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-white/10 bg-black/20 p-4">
                        <input
                          type="checkbox"
                          checked={mode === "flyer_poster" ? true : applyTemplateOverlay}
                          onChange={(e) => setApplyTemplateOverlay(e.target.checked)}
                          className="mt-1 h-4 w-4 accent-cyan-400"
                        />
                        <span>
                          <span className="block text-sm font-semibold text-white/90">Add readable flyer text layout after AI generation</span>
                          <span className="mt-1 block text-xs leading-5 text-white/50">Always on in V5. The app draws readable headline and CTA text after image understanding so the poster is a real delivery asset, not just a staged image.</span>
                        </span>
                      </label>
                    </div>
                  )}

                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-3">
                      <Label className="text-[12px] uppercase tracking-[0.22em] text-white/65">Reference strength</Label>
                      <div className="text-sm text-cyan-200">{referenceStrength[0]}% · {preserveLabel(referenceStrength[0])}</div>
                    </div>
                    <Slider value={referenceStrength} min={18} max={78} step={2} onValueChange={setReferenceStrength} />
                    <p className="text-xs text-white/45">
                      Lower values preserve the reference more strongly. Higher values give the selected mode more freedom to transform the uploaded source.
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="negative" className="text-[12px] uppercase tracking-[0.22em] text-white/65">Negative prompt</Label>
                    <Input
                      id="negative"
                      placeholder="Things to avoid..."
                      value={negativePrompt}
                      onChange={(e) => setNegativePrompt(e.target.value)}
                      className="h-12 rounded-2xl border-white/10 bg-black/35 text-white placeholder:text-white/30"
                    />
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label className="text-[12px] uppercase tracking-[0.22em] text-white/65">Style</Label>
                      <Select value={style} onValueChange={setStyle}>
                        <SelectTrigger className="h-12 rounded-2xl border-white/10 bg-black/35 text-white focus:ring-cyan-400/30">
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
                        <SelectTrigger className="h-12 rounded-2xl border-white/10 bg-black/35 text-white focus:ring-cyan-400/30">
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

                  <div className="grid gap-3 md:grid-cols-4">
                    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                      <div className="text-[11px] uppercase tracking-[0.22em] text-white/45">Cost</div>
                      <div className="mt-2 text-lg font-bold text-cyan-300">12 credits</div>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                      <div className="text-[11px] uppercase tracking-[0.22em] text-white/45">Pipeline</div>
                      <div className="mt-2 text-sm font-medium text-white/85">{selectedMode.label}</div>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                      <div className="text-[11px] uppercase tracking-[0.22em] text-white/45">Output</div>
                      <div className="mt-2 text-sm font-medium text-white/85">{selectedSize.label}</div>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                      <div className="text-[11px] uppercase tracking-[0.22em] text-white/45">Reference lock</div>
                      <div className="mt-2 text-sm font-medium text-white/85">{preserveLabel(referenceStrength[0])}</div>
                    </div>
                  </div>

                  <Button
                    type="submit"
                    className="h-12 w-full rounded-2xl bg-cyan-500 text-black shadow-[0_0_36px_rgba(34,211,238,0.24)] transition hover:bg-cyan-400"
                    disabled={isGenerating || !prompt.trim() || !referenceFile}
                  >
                    {isGenerating ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Generating...
                      </>
                    ) : (
                      <>
                        <ImageIcon className="mr-2 h-4 w-4" /> Generate {selectedMode.label}
                      </>
                    )}
                  </Button>
                </div>
              </form>
            </div>

            <div ref={previewRef} className="space-y-6 xl:sticky xl:top-6 self-start">
              <div className="rounded-[26px] border border-white/10 bg-white/[0.04] p-5 backdrop-blur-xl md:p-6">
                <div className="mb-5 flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-cyan-400/10">
                    <ImageIcon className="h-5 w-5 text-cyan-300" />
                  </div>
                  <div>
                    <h2 className="text-lg font-semibold">Live Preview</h2>
                    <p className="text-sm text-white/50">Generated reference-based result appears here</p>
                  </div>
                </div>

                <div className="relative overflow-hidden rounded-[24px] border border-white/10 bg-black/40">
                  <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(34,211,238,0.08),transparent_35%),radial-gradient(circle_at_bottom,rgba(217,70,239,0.06),transparent_30%)]" />
                  <div className="relative flex aspect-[4/5] md:aspect-video w-full items-center justify-center p-4">
                    {generatedImage ? (
                      <div className="relative h-full w-full overflow-hidden rounded-[20px] border border-white/10 bg-black/20">
                        <Image src={generatedImage} alt="Generated image" fill className="object-contain" unoptimized />
                      </div>
                    ) : isGenerating ? (
                      <div className="text-center text-white/60">
                        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full border border-white/10 bg-white/5">
                          <Loader2 className="h-7 w-7 animate-spin text-cyan-300" />
                        </div>
                        <p className="text-lg font-medium text-white/80">Generating image-to-image...</p>
                        <p className="mt-1 text-sm text-white/45">Please wait while the selected reference mode is processed</p>
                      </div>
                    ) : (
                      <div className="text-center text-white/45">
                        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full border border-white/10 bg-white/5">
                          <ImageIcon className="h-7 w-7 text-white/40" />
                        </div>
                        <p className="text-lg font-medium text-white/70">Preview ready</p>
                        <p className="mt-1 text-sm">Upload a source image and run a dedicated image-to-image mode</p>
                      </div>
                    )}
                  </div>
                </div>

                {generatedImage && (
                  <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
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
                  <div className={`mt-2 text-sm break-words whitespace-pre-wrap leading-6 ${errorMessage ? "text-red-100" : "text-white/75"}`}>{statusText}</div>
                  {currentGenerationId && <div className="mt-2 text-xs text-white/40">Generation ID: {currentGenerationId}</div>}
                  {displayHint && <div className="mt-3 text-xs leading-5 text-white/45">{displayHint}</div>}
                </div>
              </div>

              <div className="rounded-[26px] border border-white/10 bg-white/[0.04] p-5 backdrop-blur-xl md:p-6">
                <div className="text-[11px] uppercase tracking-[0.24em] text-white/45">How this page is different</div>
                <div className="mt-4 space-y-3 text-sm leading-6 text-white/70">
                  <p>• It requires a source image and does not behave like plain Generate Images.</p>
                  <p>• It exposes 6 dedicated reference modes, and each mode can run on its own isolated backend route.</p>
                  <p>• It lets you control reference strength so you can preserve identity or transform more aggressively.</p>
                  <p>• Product and object modes stay isolated from person and creative routes so ComfyUI does not mix the wrong image workflow.</p>
                  <p>• Person / Identity now generates the AI identity result by default. The Neural Camera report is optional and no longer replaces the final image.</p>
                </div>
              </div>

              <div className="rounded-[26px] border border-white/10 bg-white/[0.04] p-5 backdrop-blur-xl md:p-6">
                <div className="text-[11px] uppercase tracking-[0.24em] text-white/45">Current setup</div>
                <div className="mt-4 grid gap-2 text-sm text-white/70">
                  <div>Mode: <span className="text-white">{selectedMode.label}</span></div>
                  <div>Style: <span className="text-white">{selectedStyleLabel}</span></div>
                  <div>Output size: <span className="text-white">{selectedSize.label}</span></div>
                  <div>Strength: <span className="text-white">{referenceStrength[0]}%</span></div>
                  <div>Reference uploaded: <span className="text-white">{referenceFile ? "Yes" : "No"}</span></div>
                  <div>Optional flyer overlay: <span className="text-white">{mode === "flyer_poster" && (headline.trim() || subheadline.trim() || cta.trim()) ? "Enabled" : "Off"}</span></div>
                  <div>Neural Camera report: <span className="text-white">{mode === "person_identity" && identityBoard ? "UI only · final image separate" : "Off"}</span></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
