"use client";

import Link from "next/link";
import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  Bot,
  CheckCircle2,
  ChevronRight,
  Clock3,
  CreditCard,
  ImageIcon,
  Loader2,
  MessageCircle,
  MousePointer2,
  Music,
  Play,
  Send,
  ShieldCheck,
  Timer,
  XCircle,
} from "lucide-react";
import { OperatorPipelineBackdrop } from "@/components/OperatorPipelineBackdrop";
import { FocusModeToggle } from "@/components/layout/focus-mode-toggle";

import {
  aiOperatorApi,
  resolveOperatorAssetUrl,
  GenerationResponse,
  OperatorAction,
  OperatorExecutionEvent,
  OperatorPlanResponse,
} from "@/lib/ai-operator-api";
import { inferRenderableAssetKind } from "@/lib/media";

type CursorState = {
  x: number;
  y: number;
  label: string;
  visible: boolean;
  busy: boolean;
};

type Message = {
  id: string;
  role: "user" | "assistant" | "system";
  text: string;
};

type PreviewState = "idle" | "planning" | "waiting_approval" | "queued" | "rendering" | "done" | "failed";

type PreviewJob = {
  id: number;
  type: string;
  status: string;
  result_url?: string | null;
  thumbnail_url?: string | null;
  error_message?: string | null;
};

const EXAMPLE_COMMAND =
  "Create one premium cafe campaign hero image. Use a clean commercial style and keep the maximum budget under 20 credits.";

const QUIZ = [
  {
    question: "Which mood should the next version use?",
    options: ["Luxury", "Warm", "Minimal", "Futuristic"],
  },
  {
    question: "Which headline sounds stronger?",
    options: ["Taste the moment", "Brewed for elegance", "Coffee made clean"],
  },
  {
    question: "What should be improved next?",
    options: ["Lighting", "Colors", "Product focus", "Background"],
  },
];

function uid(prefix: string) {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function actionIcon(type: string) {
  if (type.includes("image")) return <ImageIcon className="h-4 w-4" />;
  if (type.includes("credit")) return <CreditCard className="h-4 w-4" />;
  return <MousePointer2 className="h-4 w-4" />;
}

function eventIcon(kind: string) {
  if (kind === "image") return <ImageIcon className="h-4 w-4" />;
  if (kind === "credits") return <CreditCard className="h-4 w-4" />;
  if (kind === "done") return <CheckCircle2 className="h-4 w-4" />;
  return <Clock3 className="h-4 w-4" />;
}

function createFallbackPlan(command: string): OperatorPlanResponse {
  const actions: OperatorAction[] = [
    {
      id: "understand-command",
      type: "improve_prompt",
      title: "Backend connection required",
      description: "The Operator backend API could not be reached. This preview is read-only and cannot spend credits or queue generation.",
      credits_cost: 0,
      requires_confirmation: false,
      status: "failed",
      payload: {},
    },
  ];

  return {
    session_id: `local-readonly-${Date.now()}`,
    title: command.length > 55 ? `${command.slice(0, 52)}...` : command,
    summary: "Read-only fallback. Reconnect the backend before running an Operator generation.",
    total_estimated_credits: 0,
    requires_confirmation: false,
    actions,
    assistant_message: "The Operator backend is unavailable. I did not create an executable plan and no credits can be spent until the backend reconnects.",
    cursor_script: [],
  };
}

function collectGenerationJobs(response: any): PreviewJob[] {
  const jobs: PreviewJob[] = [];
  const finalResult = response?.final_result || {};
  const events = response?.events || [];

  function add(obj: any) {
    if (!obj || typeof obj !== "object") return;
    if (typeof obj.id === "number" && obj.status) {
      jobs.push({
        id: obj.id,
        type: obj.generation_type || "generation",
        status: obj.status,
        result_url: resolveOperatorAssetUrl(obj.result_url),
        thumbnail_url: resolveOperatorAssetUrl(obj.thumbnail_url),
        error_message: obj.error_message || null,
      });
    }
  }

  if (Array.isArray(finalResult.generations)) finalResult.generations.forEach(add);
  if (Array.isArray(finalResult.images)) finalResult.images.forEach(add);
  events.forEach((event: any) => add(event?.data?.response));

  const seen = new Set<number>();
  return jobs.filter((job) => {
    if (seen.has(job.id)) return false;
    seen.add(job.id);
    return true;
  });
}

export default function AIStudioOperatorLive() {
  const [command, setCommand] = useState(EXAMPLE_COMMAND);
  const [brandName, setBrandName] = useState("Studio Pro");
  const [maxCredits, setMaxCredits] = useState(60);
  const [allowImage, setAllowImage] = useState(true);

  const [messages, setMessages] = useState<Message[]>([
    {
      id: uid("msg"),
      role: "assistant",
      text:
        "Tell me your image idea naturally. I will prepare one image-generation plan and ask permission before spending credits. Use the dedicated Image-to-Image page for uploaded references.",
    },
  ]);
  const [typedText, setTypedText] = useState("");
  const [plan, setPlan] = useState<OperatorPlanResponse | null>(null);
  const [events, setEvents] = useState<OperatorExecutionEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [backendWarning, setBackendWarning] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [cursor, setCursor] = useState<CursorState>({ x: 18, y: 24, label: "Ready", visible: true, busy: false });

  const [previewState, setPreviewState] = useState<PreviewState>("idle");
  const [previewJobs, setPreviewJobs] = useState<PreviewJob[]>([]);
  const [elapsed, setElapsed] = useState(0);
  const [quizIndex, setQuizIndex] = useState(0);
  const [quizChoice, setQuizChoice] = useState<string | null>(null);
  const [musicOn, setMusicOn] = useState(false);
  const audioRef = useRef<AudioContext | null>(null);
  const oscillatorRef = useRef<OscillatorNode | null>(null);
  const gainRef = useRef<GainNode | null>(null);

  const confirmedCost = useMemo(() => {
    if (!plan) return 0;
    return plan.actions.reduce((sum, item) => sum + item.credits_cost, 0);
  }, [plan]);

  const primaryPreview = previewJobs.find((job) => job.result_url || job.thumbnail_url) || previewJobs[0];

  async function moveCursor(x: number, y: number, label: string, busy = true) {
    setCursor({ x, y, label, visible: true, busy });
    await sleep(460);
  }

  async function typeAssistant(text: string) {
    setTypedText("");
    for (let index = 0; index < text.length; index += 1) {
      setTypedText(text.slice(0, index + 1));
      await sleep(index % 7 === 0 ? 16 : 6);
    }
    setMessages((current) => [...current, { id: uid("msg"), role: "assistant", text }]);
    setTypedText("");
  }

  function toggleMusic() {
    if (musicOn) {
      oscillatorRef.current?.stop();
      audioRef.current?.close();
      oscillatorRef.current = null;
      audioRef.current = null;
      gainRef.current = null;
      setMusicOn(false);
      return;
    }

    const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const oscillator = ctx.createOscillator();
    const gain = ctx.createGain();
    oscillator.type = "sine";
    oscillator.frequency.value = 174;
    gain.gain.value = 0.025;
    oscillator.connect(gain);
    gain.connect(ctx.destination);
    oscillator.start();
    audioRef.current = ctx;
    oscillatorRef.current = oscillator;
    gainRef.current = gain;
    setMusicOn(true);
  }

  async function runPlan() {
    const cleanCommand = command.trim();
    if (!cleanCommand || running) return;

    setRunning(true);
    setBackendWarning(null);
    setPlan(null);
    setEvents([]);
    setProgress(0);
    setPreviewJobs([]);
    setPreviewState("planning");
    setElapsed(0);
    setMessages((current) => [...current, { id: uid("msg"), role: "user", text: cleanCommand }]);

    try {
      await moveCursor(18, 24, "Reading command");
      await typeAssistant("I am reading your request and detecting whether it needs chat help or one image-generation action...");
      await moveCursor(36, 39, "Building plan");

      let nextPlan: OperatorPlanResponse;
      try {
        nextPlan = await aiOperatorApi.createPlan({
          command: cleanCommand,
          brand_name: brandName,
          max_credits: maxCredits,
          allow_image: allowImage,
          auto_execute_safe_actions: true,
          context: { source: "dashboard/operator", ui: "generation-preview-workbench" },
        });
      } catch (error: any) {
        nextPlan = createFallbackPlan(cleanCommand);
        setBackendWarning(`Operator could not create an executable backend plan. Read-only fallback only. Details: ${error?.message || "unknown error"}`);
      }

      setPlan(nextPlan);
      setProgress(20);
      setPreviewState(nextPlan.requires_confirmation ? "waiting_approval" : "done");
      await moveCursor(58, 42, "Checking credits");
      setProgress(35);
      await typeAssistant(nextPlan.assistant_message);
      await moveCursor(50, 82, nextPlan.requires_confirmation ? "Waiting approval" : "Done", false);
    } finally {
      setRunning(false);
    }
  }

  async function approvePlan(approved: boolean) {
    if (!plan || running) return;

    setRunning(true);
    setEvents([]);

    try {
      if (!approved) {
        if (!plan.session_id.startsWith("local-readonly-")) {
          try {
            await aiOperatorApi.confirm(plan.session_id, false);
          } catch {
            // Cancellation remains safe even if the backend connection drops.
          }
        }
        setPreviewState("idle");
        await moveCursor(50, 82, "Cancelled", false);
        await typeAssistant("Execution cancelled. No credits were spent.");
        return;
      }

      if (plan.session_id.startsWith("local-readonly-")) {
        setBackendWarning("Operator backend is unavailable. Reconnect the backend and create a new plan before approval.");
        setPreviewState("failed");
        await moveCursor(50, 82, "Backend required", false);
        return;
      }

      setPreviewState("queued");
      await moveCursor(50, 82, "Permission approved");
      await typeAssistant(`Permission approved. I will queue the real generation workflow. Estimated cost: ${confirmedCost} credits.`);

      let response = null as any;
      try {
        response = await aiOperatorApi.confirm(plan.session_id, true);
      } catch (error: any) {
        setBackendWarning(`Execution error: ${error?.message || "unknown error"}`);
        setPreviewState("failed");
        return;
      }

      const jobs = collectGenerationJobs(response);
      setPreviewJobs(jobs);
      if (jobs.length > 0) setPreviewState("rendering");

      for (const event of response.events || []) {
        const target = event.cursor_target || {};
        await moveCursor(typeof target.x === "number" ? target.x : 50, typeof target.y === "number" ? target.y : 50, event.title);
        setEvents((current) => [...current, event]);
        setProgress(event.progress);
        await typeAssistant(event.message);
        await sleep(220);
      }

      if (jobs.length > 0) {
        await pollGenerations(jobs);
      } else if (confirmedCost === 0) {
        setPreviewState("done");
      } else {
        setPreviewState("failed");
      }

      setCursor((current) => ({ ...current, busy: false, label: "Done" }));
    } finally {
      setRunning(false);
    }
  }

  async function pollGenerations(initialJobs: PreviewJob[]) {
    const ids = initialJobs.map((job) => job.id).filter(Boolean);
    if (ids.length === 0) return;

    let done = false;
    for (let attempt = 0; attempt < 90 && !done; attempt += 1) {
      await sleep(2000);
      const fresh: PreviewJob[] = [];
      for (const id of ids) {
        try {
          const data: GenerationResponse = await aiOperatorApi.getGeneration(id);
          fresh.push({
            id: data.id,
            type: data.generation_type,
            status: data.status,
            result_url: resolveOperatorAssetUrl(data.result_url),
            thumbnail_url: resolveOperatorAssetUrl(data.thumbnail_url),
            error_message: data.error_message,
          });
        } catch {
          const old = initialJobs.find((job) => job.id === id);
          if (old) fresh.push(old);
        }
      }
      setPreviewJobs(fresh);
      const completed = fresh.some((job) => job.status === "completed" && (job.result_url || job.thumbnail_url));
      const failed = fresh.length > 0 && fresh.every((job) => job.status === "failed");
      if (completed) {
        setPreviewState("done");
        setProgress(100);
        done = true;
      } else if (failed) {
        setPreviewState("failed");
        setBackendWarning(fresh.map((job) => job.error_message).filter(Boolean).join(" | ") || "Generation failed. Check History for details.");
        done = true;
      } else {
        setPreviewState("rendering");
        setProgress((current) => Math.min(96, Math.max(current, 45 + attempt)));
      }
    }

    if (!done) {
      setPreviewState("queued");
      setBackendWarning("Generation is still processing after the live-preview timeout. Open History to follow the queued job; the Operator will not stay stuck on Rendering forever.");
      setCursor((current) => ({ ...current, busy: false, label: "Queued — check History" }));
    }
  }

  useEffect(() => {
    if (!["queued", "rendering", "planning"].includes(previewState)) return;
    const interval = window.setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => window.clearInterval(interval);
  }, [previewState]);

  useEffect(() => {
    return () => {
      oscillatorRef.current?.stop();
      audioRef.current?.close();
    };
  }, []);

  return (
    <main className="operator-workspace human-made-screen relative min-h-screen overflow-hidden bg-transparent px-4 py-8 text-white md:px-8">
      <OperatorPipelineBackdrop />
      <div className="pointer-events-none absolute inset-0 z-[1] bg-[radial-gradient(circle_at_15%_20%,rgba(124,58,237,0.12),transparent_30%),radial-gradient(circle_at_82%_16%,rgba(34,211,238,0.10),transparent_28%),linear-gradient(180deg,rgba(2,8,18,0.04),rgba(2,8,18,0.22))]" />
      <div className="pointer-events-none absolute inset-0 z-[1] opacity-[0.035] [background-image:linear-gradient(rgba(255,255,255,0.12)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.12)_1px,transparent_1px)] [background-size:64px_64px]" />

      <section className="relative z-10 mx-auto max-w-7xl">
        <div className="mb-7 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-cyan-300/15 bg-cyan-300/[0.05] px-4 py-2 text-[11px] uppercase tracking-[0.25em] text-cyan-100/75">
              <Bot className="h-4 w-4" /> Operator
            </div>
            <h1 className="text-3xl font-semibold tracking-tight text-white drop-shadow-[0_12px_40px_rgba(0,0,0,0.82)] md:text-5xl">Live generation panel</h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-white/80">
              Write a natural command, approve the plan, queue one real image generation, and review the live preview. Uploaded-reference workflows stay in the dedicated Image-to-Image page.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <FocusModeToggle className="h-[46px] rounded-2xl bg-cyan-300/10 px-5 text-sm" />
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-2 rounded-2xl border border-white/12 bg-black/[0.34] px-4 py-3 text-sm font-bold text-white/90 shadow-[0_18px_70px_rgba(0,0,0,0.32)] backdrop-blur-xl transition hover:-translate-y-0.5 hover:border-cyan-200/35 hover:bg-white/[0.08]"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Dashboard
            </Link>
            <div className="rounded-2xl border border-white/12 bg-black/[0.34] px-4 py-3 text-sm text-white/80 shadow-[0_18px_70px_rgba(0,0,0,0.30)] backdrop-blur-xl">
              Estimated credits: <span className="font-semibold text-white">{confirmedCost}</span>
            </div>
          </div>
        </div>

        {backendWarning && (
          <div className="mb-5 flex items-start gap-3 rounded-2xl border border-amber-400/20 bg-amber-400/10 p-4 text-sm leading-6 text-amber-100">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" /> <span>{backendWarning}</span>
          </div>
        )}

        <div className="relative grid gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(420px,1.1fr)]">
          <LiveCursor cursor={cursor} />

          <div className="rounded-[2rem] border border-white/10 bg-black/[0.32] p-5 shadow-[0_30px_120px_rgba(0,0,0,0.44)] backdrop-blur-md md:p-6">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold">Command Center</h2>
                <p className="mt-1 text-sm text-white/80">Write naturally. No need to type generate.</p>
              </div>
              <div className="flex items-center gap-2 rounded-full border border-emerald-300/15 bg-emerald-300/[0.06] px-3 py-1.5 text-xs text-emerald-100/80">
                <ShieldCheck className="h-4 w-4" /> Permission-safe
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <label className="md:col-span-2">
                <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-white/60">Brand name</span>
                <input value={brandName} onChange={(event) => setBrandName(event.target.value)} className="h-12 w-full rounded-2xl border border-white/10 bg-black/[0.44] px-4 text-sm text-white outline-none transition placeholder:text-white/30 focus:border-cyan-300/45" />
              </label>
              <label>
                <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-white/60">Max credits</span>
                <input type="number" min={0} value={maxCredits} onChange={(event) => setMaxCredits(Number(event.target.value || 0))} className="h-12 w-full rounded-2xl border border-white/10 bg-black/[0.44] px-4 text-sm text-white outline-none transition placeholder:text-white/30 focus:border-cyan-300/45" />
              </label>
            </div>

            <div className="mt-4 flex flex-wrap gap-3">
              <label className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-white/10 bg-white/[0.075] px-4 py-2 text-sm text-white/80">
                <input type="checkbox" checked={allowImage} onChange={(event) => setAllowImage(event.target.checked)} className="accent-cyan-300" /> Allow image actions
              </label>
            </div>

            <label className="mt-5 block">
              <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-white/60">User command</span>
              <textarea value={command} onChange={(event) => setCommand(event.target.value)} rows={6} spellCheck={false} className="w-full resize-none rounded-3xl border border-white/10 bg-black/[0.44] p-5 text-sm leading-6 text-white outline-none transition placeholder:text-white/30 focus:border-fuchsia-300/45" placeholder="Example: a clean poster for a cafe based on this uploaded bottle..." />
            </label>

            <button onClick={runPlan} disabled={running || !command.trim()} className="mt-5 flex h-14 w-full items-center justify-center gap-3 rounded-2xl border border-white/10 bg-gradient-to-r from-fuchsia-600 via-violet-600 to-cyan-500 text-base font-semibold text-white shadow-[0_0_45px_rgba(217,70,239,0.25)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60">
              {running && !plan ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />} Start Operator
            </button>

            <LiveConversation messages={messages} typedText={typedText} />
          </div>

          <div className="space-y-6">
            <GenerationPreviewPanel
              state={previewState}
              progress={progress}
              elapsed={elapsed}
              jobs={previewJobs}
              primaryPreview={primaryPreview}
              musicOn={musicOn}
              onToggleMusic={toggleMusic}
              quizIndex={quizIndex}
              quizChoice={quizChoice}
              setQuizChoice={setQuizChoice}
              nextQuiz={() => {
                setQuizChoice(null);
                setQuizIndex((index) => (index + 1) % QUIZ.length);
              }}
            />

            <PlanPanel plan={plan} progress={progress} running={running} approvePlan={approvePlan} />
            <TimelinePanel events={events} />
          </div>
        </div>
      </section>
    </main>
  );
}

function LiveConversation({ messages, typedText }: { messages: Message[]; typedText: string }) {
  return (
    <div className="mt-6 rounded-3xl border border-white/10 bg-black/30 p-4">
      <div className="mb-3 flex items-center gap-2 text-sm font-medium text-white/80">
        <MessageCircle className="h-4 w-4 text-fuchsia-200" /> Live conversation
      </div>
      <div className="max-h-[260px] space-y-3 overflow-y-auto pr-1">
        {messages.map((message) => (
          <div key={message.id} className={`rounded-2xl px-4 py-3 text-sm leading-6 ${message.role === "user" ? "ml-8 bg-cyan-300/10 text-cyan-50" : "mr-8 bg-white/[0.075] text-white/85"}`}>
            {message.text}
          </div>
        ))}
        {typedText && (
          <div className="mr-8 rounded-2xl bg-white/[0.075] px-4 py-3 text-sm leading-6 text-white/85">
            {typedText}<span className="ml-1 inline-block h-4 w-px translate-y-0.5 animate-pulse bg-cyan-200" />
          </div>
        )}
      </div>
    </div>
  );
}

function GenerationPreviewPanel(props: {
  state: PreviewState;
  progress: number;
  elapsed: number;
  jobs: PreviewJob[];
  primaryPreview?: PreviewJob;
  musicOn: boolean;
  onToggleMusic: () => void;
  quizIndex: number;
  quizChoice: string | null;
  setQuizChoice: (choice: string) => void;
  nextQuiz: () => void;
}) {
  const quiz = QUIZ[props.quizIndex];
  const imgUrl = props.primaryPreview?.result_url || props.primaryPreview?.thumbnail_url || null;
  const renderKind = inferRenderableAssetKind(imgUrl, props.primaryPreview?.type);
  const eta = Math.max(0, 55 - props.elapsed);

  return (
    <div className="rounded-[2rem] border border-white/10 bg-black/[0.32] p-5 shadow-[0_30px_120px_rgba(0,0,0,0.40)] backdrop-blur-md md:p-6">
      <div className="mb-5 flex items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold">Live Preview</h2>
          <p className="mt-1 text-sm text-white/80">The visual appears here while generation is running.</p>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.075] px-3 py-1.5 text-xs text-white/75">
          <Timer className="h-4 w-4" /> {formatTime(props.elapsed)} / ETA {formatTime(eta)}
        </div>
      </div>

      <div className="mb-4 h-2 overflow-hidden rounded-full border border-white/10 bg-black/[0.32]">
        <div className="h-full rounded-full bg-gradient-to-r from-cyan-300 via-fuchsia-300 to-violet-300 transition-all duration-500" style={{ width: `${props.progress}%` }} />
      </div>

      <div className="relative flex aspect-square min-h-[360px] items-center justify-center overflow-hidden rounded-[2rem] border border-white/10 bg-black/[0.44]">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_30%,rgba(34,211,238,0.18),transparent_35%),radial-gradient(circle_at_50%_85%,rgba(217,70,239,0.18),transparent_38%)]" />
        {!imgUrl ? (
          <div className="relative z-10 flex max-w-sm flex-col items-center text-center">
            <div className="mb-5 h-28 w-28 rounded-[2rem] border border-cyan-300/20 bg-cyan-300/10 p-1 shadow-[0_0_60px_rgba(34,211,238,0.16)]">
              <div className="h-full w-full animate-pulse rounded-[1.6rem] bg-gradient-to-br from-white/10 via-cyan-300/10 to-fuchsia-300/20" />
            </div>
            <p className="text-lg font-semibold text-white">{previewCopy(props.state)}</p>
            <p className="mt-2 text-sm leading-6 text-white/80">The image is being queued, rendered, and refreshed automatically. Keep this panel open or check History.</p>
          </div>
        ) : (
          <img className="relative z-10 h-full w-full animate-[fadeIn_0.8s_ease] object-contain" src={imgUrl} alt="Generated preview" />
        )}
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-2">
        <button onClick={props.onToggleMusic} className="flex items-center justify-center gap-2 rounded-2xl border border-white/10 bg-white/[0.075] px-4 py-3 text-sm font-semibold text-white/85 hover:bg-white/[0.08]">
          <Music className="h-4 w-4" /> {props.musicOn ? "Pause ambient" : "Play ambient"}
        </button>
        <a href="/history" className="flex items-center justify-center gap-2 rounded-2xl border border-cyan-300/20 bg-cyan-300/10 px-4 py-3 text-sm font-semibold text-cyan-50 hover:bg-cyan-300/15">
          Open History <ChevronRight className="h-4 w-4" />
        </a>
      </div>

      <div className="mt-4 rounded-3xl border border-white/10 bg-white/[0.035] p-4">
        <p className="text-xs uppercase tracking-[0.2em] text-white/60">While waiting</p>
        <p className="mt-2 text-sm font-semibold text-white/85">{quiz.question}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {quiz.options.map((option) => (
            <button key={option} onClick={() => props.setQuizChoice(option)} className={`rounded-full border px-3 py-1.5 text-xs transition ${props.quizChoice === option ? "border-cyan-300/40 bg-cyan-300/15 text-cyan-50" : "border-white/10 bg-black/[0.35] text-white/80 hover:bg-white/5"}`}>
              {option}
            </button>
          ))}
          <button onClick={props.nextQuiz} className="rounded-full border border-fuchsia-300/20 bg-fuchsia-300/10 px-3 py-1.5 text-xs text-fuchsia-100">Next</button>
        </div>
      </div>
    </div>
  );
}

function PlanPanel({ plan, progress, running, approvePlan }: { plan: OperatorPlanResponse | null; progress: number; running: boolean; approvePlan: (approved: boolean) => void }) {
  return (
    <div className="rounded-[2rem] border border-white/10 bg-black/[0.32] p-5 shadow-[0_30px_120px_rgba(0,0,0,0.40)] backdrop-blur-md md:p-6">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Execution Plan</h2>
          <p className="mt-1 text-sm text-white/80">Every action is visible and traceable.</p>
        </div>
        <div className="rounded-full border border-white/10 bg-white/[0.075] px-3 py-1.5 text-xs text-white/75">{progress}%</div>
      </div>
      {!plan ? (
        <div className="rounded-3xl border border-dashed border-white/10 bg-white/[0.025] p-8 text-center text-sm leading-6 text-white/80">The operator plan will appear here.</div>
      ) : (
        <div className="space-y-3">
          <div className="rounded-3xl border border-white/10 bg-white/[0.075] p-4">
            <h3 className="font-semibold text-white">{plan.title}</h3>
            <p className="mt-2 text-sm leading-6 text-white/70">{plan.summary}</p>
          </div>
          {plan.actions.map((action) => (
            <div key={action.id} className="flex gap-3 rounded-2xl border border-white/10 bg-black/[0.28] p-4">
              <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-white/[0.06] text-cyan-100">{actionIcon(action.type)}</div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h4 className="text-sm font-semibold text-white/90">{action.title}</h4>
                  {action.requires_confirmation && <span className="rounded-full border border-amber-300/20 bg-amber-300/10 px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] text-amber-100/75">permission</span>}
                  {action.credits_cost > 0 && <span className="rounded-full border border-fuchsia-300/20 bg-fuchsia-300/10 px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] text-fuchsia-100/75">{action.credits_cost} credits</span>}
                </div>
                <p className="mt-1 text-xs leading-5 text-white/80">{action.description}</p>
              </div>
            </div>
          ))}
          {plan.requires_confirmation && (
            <div className="grid gap-3 pt-2 md:grid-cols-2">
              <button onClick={() => approvePlan(false)} disabled={running} className="flex h-12 items-center justify-center gap-2 rounded-2xl border border-red-400/20 bg-red-400/10 text-sm font-semibold text-red-100 transition hover:bg-red-400/15 disabled:opacity-60"><XCircle className="h-4 w-4" /> Cancel</button>
              <button onClick={() => approvePlan(true)} disabled={running} className="flex h-12 items-center justify-center gap-2 rounded-2xl border border-emerald-300/20 bg-emerald-300/15 text-sm font-semibold text-emerald-50 transition hover:bg-emerald-300/20 disabled:opacity-60">{running && plan ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} Approve and execute</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function TimelinePanel({ events }: { events: OperatorExecutionEvent[] }) {
  return (
    <div className="rounded-[2rem] border border-white/10 bg-black/[0.32] p-5 shadow-[0_30px_120px_rgba(0,0,0,0.34)] backdrop-blur-md md:p-6">
      <div className="mb-5 flex items-center gap-2"><Clock3 className="h-5 w-5 text-cyan-100" /><h2 className="text-xl font-semibold">Live Execution Timeline</h2></div>
      {events.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-white/10 bg-white/[0.025] p-7 text-center text-sm leading-6 text-white/80">Approved actions will appear here in real time.</div>
      ) : (
        <div className="space-y-3">
          {events.map((event) => (
            <div key={event.id} className="flex gap-3 rounded-2xl border border-white/10 bg-white/[0.075] p-4">
              <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-cyan-300/10 text-cyan-100">{eventIcon(event.kind)}</div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2"><h4 className="text-sm font-semibold text-white/90">{event.title}</h4><ChevronRight className="h-4 w-4 text-white/40" /><span className="text-xs text-white/80">{event.progress}%</span></div>
                <p className="mt-1 text-xs leading-5 text-white/70">{event.message}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function LiveCursor({ cursor }: { cursor: CursorState }) {
  return (
    <div className={`pointer-events-none absolute z-50 transition-all duration-500 ease-out ${cursor.visible ? "opacity-100" : "opacity-0"}`} style={{ left: `${cursor.x}%`, top: `${cursor.y}%` }}>
      <div className="relative -translate-x-2 -translate-y-2">
        <MousePointer2 className="h-7 w-7 rotate-[-12deg] fill-cyan-200 text-cyan-100 drop-shadow-[0_0_18px_rgba(34,211,238,0.85)]" />
        {cursor.busy && <span className="absolute -left-3 -top-3 h-10 w-10 animate-ping rounded-full border border-cyan-200/40" />}
        <div className="absolute left-6 top-5 whitespace-nowrap rounded-full border border-white/10 bg-black/70 px-3 py-1.5 text-[11px] uppercase tracking-[0.18em] text-white/80 shadow-[0_10px_35px_rgba(0,0,0,0.45)] backdrop-blur-xl">{cursor.busy ? "Working" : cursor.label}</div>
      </div>
    </div>
  );
}

function formatTime(seconds: number) {
  const min = Math.floor(seconds / 60).toString().padStart(2, "0");
  const sec = Math.floor(seconds % 60).toString().padStart(2, "0");
  return `${min}:${sec}`;
}

function previewCopy(state: PreviewState) {
  if (state === "planning") return "Understanding your idea...";
  if (state === "waiting_approval") return "Plan ready. Waiting for your permission.";
  if (state === "queued") return "Generation queued...";
  if (state === "rendering") return "Rendering your visual...";
  if (state === "done") return "Your visual is ready.";
  if (state === "failed") return "Generation failed. Check timeline details.";
  return "Preview will appear here.";
}
