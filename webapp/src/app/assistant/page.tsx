"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/hooks/useAuth";
import { BACKEND_BASE_URL } from "@/lib/api";
import { withAuthHeaders } from "@/lib/auth-fetch";
import {
  AlertTriangle,
  Bot,
  ChevronRight,
  Copy,
  ImageIcon,
  Languages,
  Loader2,
  MessageCircle,
  RefreshCw,
  Send,
  Trash2,
} from "lucide-react";

type ChatRole = "user" | "assistant";
type ModelMode = "auto" | "fast" | "advanced";

type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  createdAt: string;
};

type AssistantApiResponse = {
  success: boolean;
  reply?: string;
  provider?: string;
  error?: string | null;
};

const STORAGE_KEY = "ai-studio-pro-assistant-messages-v1";

const starterMessages: ChatMessage[] = [
  {
    id: "welcome",
    role: "assistant",
    createdAt: new Date().toISOString(),
    content:
      "Hi. I am your AI Studio Pro Workspace Assistant. You can write in English, French, Tunisian Arabic, or Arabizi. I answer in the selected output language and can explain the app, improve image and image-to-image prompts, debug ComfyUI issues, explain credits/history, and help you contact administration.",
  },
];

const quickPrompts = [
  {
    icon: ImageIcon,
    label: "Improve image-to-image result",
    prompt:
      "My image-to-image result drifted too far from the reference. How can I preserve the subject better?",
  },
  {
    icon: ImageIcon,
    label: "Better image prompt",
    prompt:
      "Give me a professional image generation prompt with a strong negative prompt.",
  },
  {
    icon: AlertTriangle,
    label: "Debug app error",
    prompt:
      "I have an app error. What steps should I follow to debug browser, backend, ComfyUI, and worker logs?",
  },
  {
    icon: Languages,
    label: "French help",
    prompt:
      "Explique-moi comment écrire un bon prompt image-to-image en français.",
  },
];

function makeId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function formatTime(value: string) {
  try {
    return new Intl.DateTimeFormat(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(value));
  } catch {
    return "";
  }
}

function detectDirection(text: string) {
  return /[\u0600-\u06FF]/.test(text) ? "rtl" : "ltr";
}

export default function AssistantPage() {
  useAuth();

  const [messages, setMessages] = useState<ChatMessage[]>(starterMessages);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [provider, setProvider] = useState<string | null>(null);
  const [modelMode, setModelMode] = useState<ModelMode>("auto");

  const bottomRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setMessages(parsed);
        }
      }
    } catch {
      setMessages(starterMessages);
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(messages.slice(-40)));
    } catch {
      // localStorage can fail in private mode; the assistant still works.
    }
  }, [messages]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending]);

  const canSend = input.trim().length > 0 && !isSending;

  const visibleMessages = useMemo(() => messages.filter((m) => m.content.trim()), [messages]);

  async function sendMessage(customPrompt?: string) {
    const cleanInput = (customPrompt ?? input).trim();
    if (!cleanInput || isSending) return;

    const userMessage: ChatMessage = {
      id: makeId(),
      role: "user",
      content: cleanInput,
      createdAt: new Date().toISOString(),
    };

    const nextMessages = [...messages, userMessage];
    setMessages(nextMessages);
    setInput("");
    setErrorMessage(null);
    setIsSending(true);

    try {
      const response = await fetch(`${BACKEND_BASE_URL}/assistant/chat`, {
        method: "POST",
        headers: withAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          message: cleanInput,
          lang: "auto",
          model_mode: modelMode,
          page_context: "workspace assistant page",
          messages: nextMessages.slice(-12).map((message) => ({
            role: message.role,
            content: message.content,
          })),
        }),
      });

      const data = (await response.json().catch(() => ({}))) as AssistantApiResponse & { detail?: string };
      if (!response.ok) {
        throw new Error(data.detail || data.error || `Assistant request failed (${response.status}).`);
      }

      if (!data?.success || !data.reply) {
        throw new Error(data?.error || "Assistant returned an empty response.");
      }

      setProvider(data.provider || null);

      setMessages((current) => [
        ...current,
        {
          id: makeId(),
          role: "assistant",
          content: data.reply || "",
          createdAt: new Date().toISOString(),
        },
      ]);
    } catch (error: any) {
      console.error("Assistant request failed:", error);
      setErrorMessage(
        error?.response?.data?.detail ||
          error?.response?.data?.error ||
          error?.message ||
          "Assistant request failed. Check backend terminal and /assistant/chat route."
      );

      setMessages((current) => [
        ...current,
        {
          id: makeId(),
          role: "assistant",
          content:
            "I cannot connect to the assistant API right now. Check the backend route /assistant/chat and the uvicorn terminal, then send the exact error if it still fails.",
          createdAt: new Date().toISOString(),
        },
      ]);
    } finally {
      setIsSending(false);
      textareaRef.current?.focus();
    }
  }

  function clearChat() {
    setMessages(starterMessages);
    setErrorMessage(null);
    setProvider(null);
    setInput("");
  }

  async function copyText(text: string) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Clipboard may be blocked by browser permissions.
    }
  }

  function onTextareaKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  }

  return (
    <DashboardLayout>
      <div className="human-made-screen relative min-h-[calc(100vh-120px)] overflow-hidden rounded-[28px] border border-white/10 bg-black text-white shadow-[0_0_80px_rgba(217,70,239,0.08)]">
        <div className="absolute inset-0">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(217,70,239,0.14),transparent_28%),radial-gradient(circle_at_top_right,rgba(34,211,238,0.10),transparent_24%),radial-gradient(circle_at_bottom_center,rgba(239,68,68,0.10),transparent_30%),linear-gradient(180deg,#050505_0%,#090909_100%)]" />
          <div
            className="absolute inset-0 opacity-[0.18]"
            style={{
              backgroundImage:
                "radial-gradient(rgba(255,255,255,0.55) 0.6px, transparent 0.6px)",
              backgroundSize: "26px 26px",
            }}
          />
          <div className="absolute left-[12%] top-[16%] h-44 w-44 rounded-full bg-fuchsia-500/10 blur-3xl" />
          <div className="absolute right-[12%] top-[26%] h-52 w-52 rounded-full bg-cyan-400/10 blur-3xl" />
          <div className="absolute bottom-[10%] left-[35%] h-56 w-56 rounded-full bg-red-500/10 blur-3xl" />
        </div>

        <div className="relative z-10 flex min-h-[calc(100vh-120px)] flex-col p-6 md:p-8 xl:p-10">
          <div className="mb-6 flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <div className="mb-3 human-pill inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] tracking-[0.08em] text-white/60 backdrop-blur">
                <Bot className="h-3.5 w-3.5 text-fuchsia-300" />
                Assistant
              </div>

              <h1 className="text-4xl font-black tracking-tight md:text-5xl">
                Workspace <span className="text-fuchsia-400">Assistant</span>
              </h1>

              <p className="human-note mt-3 max-w-3xl text-sm leading-6 text-white/60 md:text-base">
                A smart helper for your app. You can write in English, French, Tunisian Arabic, or Arabizi.
                Replies stay in the selected English or French output language. Voice output is EN / FR only. The assistant includes Audience Mirror,
                Launch Pack - Brand Studio, Director Mode + Prompt Doctor, and Neural Camera Analysis with a two-stage persona workflow.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Button
                type="button"
                variant="outline"
                onClick={clearChat}
                className="rounded-full border-white/10 bg-white/5 text-white/70 backdrop-blur hover:bg-white/10 hover:text-white"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Clear chat
              </Button>

              <Link
                href="/history"
                className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-white/70 backdrop-blur transition hover:border-white/20 hover:bg-white/10 hover:text-white"
              >
                Recent generations
                <ChevronRight className="h-4 w-4" />
              </Link>
            </div>
          </div>

          <div className="grid flex-1 gap-6 xl:grid-cols-[0.72fr_1.28fr]">
            <div className="space-y-5">
              <div className="rounded-[26px] border border-white/10 bg-white/[0.04] p-5 backdrop-blur-xl md:p-6">
                <div className="mb-5 flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-fuchsia-500/10">
                    <MessageCircle className="h-5 w-5 text-fuchsia-300" />
                  </div>
                  <div>
                    <h2 className="text-lg font-semibold">What it can do</h2>
                    <p className="text-sm text-white/50">Professional support inside your app</p>
                  </div>
                </div>

                <div className="grid gap-3">
                  <Feature icon={ImageIcon} title="Image prompts" text="Better prompts, negative prompts, styles, and quality tips." />
                  <Feature icon={ImageIcon} title="Image-to-image" text="Helps users preserve identity, control reference strength, and improve source-based results." />
                  <Feature icon={AlertTriangle} title="Error debugging" text="Guides users through browser console, backend logs, Celery, and routes." />
                  <Feature icon={Languages} title="Flexible text input" text="Write in English, French, Tunisian Arabic, or Arabizi. Replies and voice output remain EN/FR only." />
                  <Feature icon={ImageIcon} title="Neural Camera persona workflow" text="Build a same-person expression board first, then review full-body pose and wardrobe directions." />
                </div>
              </div>

              <div className="rounded-[26px] border border-white/10 bg-white/[0.04] p-5 backdrop-blur-xl md:p-6">
                <div className="mb-4 flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-white/10 bg-cyan-400/10">
                    <Copy className="h-5 w-5 text-cyan-300" />
                  </div>
                  <div>
                    <h2 className="text-lg font-semibold">Quick actions</h2>
                    <p className="text-sm text-white/50">One click examples</p>
                  </div>
                </div>

                <div className="grid gap-3">
                  {quickPrompts.map((item) => {
                    const Icon = item.icon;
                    return (
                      <button
                        key={item.label}
                        type="button"
                        onClick={() => sendMessage(item.prompt)}
                        disabled={isSending}
                        className="group flex items-center gap-3 rounded-2xl border border-white/10 bg-black/25 p-4 text-left transition hover:border-fuchsia-300/30 hover:bg-white/[0.06] disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-fuchsia-200">
                          <Icon className="h-5 w-5" />
                        </span>
                        <span>
                          <span className="block text-sm font-semibold text-white/85">{item.label}</span>
                          <span className="mt-1 block text-xs leading-5 text-white/45">{item.prompt}</span>
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            <div className="flex min-h-[680px] flex-col rounded-[26px] border border-white/10 bg-white/[0.04] p-5 backdrop-blur-xl md:p-6">
              <div className="mb-5 flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-cyan-400/10">
                    <MessageCircle className="h-5 w-5 text-cyan-300" />
                  </div>
                  <div>
                    <h2 className="text-lg font-semibold">Live Chat</h2>
                    <p className="text-sm text-white/50">
                      {provider ? `Provider: ${provider}` : "Ready to help"}
                    </p>
                  </div>
                </div>

                <div className="hidden rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/50 md:block">
                  Enter = send • Shift + Enter = new line
                </div>
              </div>

              {errorMessage && (
                <div className="mb-4 rounded-2xl border border-red-400/20 bg-red-500/10 p-4 text-sm text-red-100">
                  {errorMessage}
                </div>
              )}

              <div className="relative flex-1 overflow-hidden rounded-[24px] border border-white/10 bg-black/35">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(217,70,239,0.06),transparent_35%),radial-gradient(circle_at_bottom,rgba(34,211,238,0.05),transparent_30%)]" />
                <div className="relative h-full max-h-[560px] overflow-y-auto p-4 md:p-5">
                  <div className="space-y-4">
                    {visibleMessages.map((message) => {
                      const isUser = message.role === "user";
                      const direction = detectDirection(message.content);

                      return (
                        <div
                          key={message.id}
                          className={`flex ${isUser ? "justify-end" : "justify-start"}`}
                        >
                          <div
                            className={`max-w-[88%] rounded-3xl border p-4 shadow-sm md:max-w-[78%] ${
                              isUser
                                ? "border-fuchsia-300/20 bg-fuchsia-500/15 text-white"
                                : "border-white/10 bg-white/[0.06] text-white/85"
                            }`}
                          >
                            <div className="mb-2 flex items-center justify-between gap-3">
                              <div className="flex items-center gap-2 text-xs text-white/45">
                                {isUser ? (
                                  <span className="rounded-full bg-fuchsia-400/20 px-2 py-0.5 text-fuchsia-100">You</span>
                                ) : (
                                  <span className="rounded-full bg-cyan-400/15 px-2 py-0.5 text-cyan-100">Assistant</span>
                                )}
                                <span>{formatTime(message.createdAt)}</span>
                              </div>

                              <button
                                type="button"
                                onClick={() => copyText(message.content)}
                                className="rounded-full p-1 text-white/35 transition hover:bg-white/10 hover:text-white/70"
                                aria-label="Copy message"
                              >
                                <Copy className="h-3.5 w-3.5" />
                              </button>
                            </div>

                            <div
                              dir={direction}
                              className="whitespace-pre-wrap text-sm leading-7"
                            >
                              {message.content}
                            </div>
                          </div>
                        </div>
                      );
                    })}

                    {isSending && (
                      <div className="flex justify-start">
                        <div className="rounded-3xl border border-white/10 bg-white/[0.06] p-4 text-white/70">
                          <div className="flex items-center gap-3 text-sm">
                            <Loader2 className="h-4 w-4 animate-spin text-fuchsia-300" />
                            Assistant is thinking...
                          </div>
                        </div>
                      </div>
                    )}

                    <div ref={bottomRef} />
                  </div>
                </div>
              </div>

              <div className="mt-4 rounded-[24px] border border-white/10 bg-black/35 p-3">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/10 bg-white/[0.03] px-3 py-2">
                  <div>
                    <div className="text-[11px] uppercase tracking-[0.18em] text-white/40">Local AI model</div>
                    <div className="mt-1 text-xs text-white/55">Auto uses the light model for chat and the advanced model for creative tools.</div>
                  </div>
                  <select
                    value={modelMode}
                    onChange={(event) => setModelMode(event.target.value as ModelMode)}
                    className="h-10 rounded-xl border border-white/10 bg-black/70 px-3 text-xs text-white outline-none"
                    title="Local AI model"
                  >
                    <option value="auto">Auto Smart</option>
                    <option value="fast">Fast Local</option>
                    <option value="advanced">Advanced Local</option>
                  </select>
                </div>
                <div className="flex flex-col gap-3 md:flex-row md:items-end">
                  <Textarea
                    ref={textareaRef}
                    value={input}
                    onChange={(event) => setInput(event.target.value)}
                    onKeyDown={onTextareaKeyDown}
                    placeholder="Write in English, French, Tunisian Arabic, or Arabizi..."
                    className="min-h-[86px] flex-1 resize-none rounded-2xl border-white/10 bg-black/35 text-white placeholder:text-white/30 focus-visible:ring-fuchsia-400/30"
                    disabled={isSending}
                  />

                  <div className="flex gap-2 md:flex-col">
                    <Button
                      type="button"
                      onClick={() => sendMessage()}
                      disabled={!canSend}
                      className="h-12 flex-1 rounded-2xl bg-fuchsia-600 text-white shadow-[0_0_36px_rgba(217,70,239,0.28)] transition hover:bg-fuchsia-500 md:w-36"
                    >
                      {isSending ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <Send className="mr-2 h-4 w-4" />
                      )}
                      Send
                    </Button>

                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => sendMessage("Give me a professional image-to-image prompt with a strong negative prompt.")}
                      disabled={isSending}
                      className="h-12 flex-1 rounded-2xl border-white/10 bg-white/5 text-white hover:bg-white/10 md:w-36"
                    >
                      <RefreshCw className="mr-2 h-4 w-4" />
                      Example
                    </Button>
                  </div>
                </div>
              </div>

              <div className="mt-4 rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                <div className="text-[11px] uppercase tracking-[0.24em] text-white/45">Tip</div>
                <div className="mt-2 text-sm leading-6 text-white/65">
                  For best generation results, never put the main subject in the negative prompt.
                  Example: prompt “dog” and negative “dog” cancels the subject.
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

function Feature({
  icon: Icon,
  title,
  text,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  text: string;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-black/25 p-4">
      <div className="flex gap-3">
        <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-fuchsia-200">
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <div className="text-sm font-semibold text-white/85">{title}</div>
          <div className="mt-1 text-sm leading-6 text-white/50">{text}</div>
        </div>
      </div>
    </div>
  );
}
