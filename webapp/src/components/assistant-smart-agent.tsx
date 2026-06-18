"use client";

import { normalizeBackendRoot } from "@/lib/url-config";

import { useEffect, useRef, useState } from "react";
import {
  Bot,
  Send,
  X,
  Loader2,
  MessageCircle,
  CheckCircle2,
  XCircle,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Download,
  RefreshCw,
  ImageIcon,
  Camera,
  Clapperboard,
  Briefcase,
  Users,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { withAuthHeaders } from "@/lib/auth-fetch";
import { Textarea } from "@/components/ui/textarea";
import { useSpeechToText } from "@/hooks/useSpeechToText";
import {
  AgentToolRequest,
  executeAgentTool,
  pollGenerationResult,
} from "@/lib/agent-bridge";
import {
  MagicLensAnalyzeResult as ImageCheckAnalyzeResult,
  MagicLensModal as ImageCheckModal,
  MagicLensSuggestion as ImageCheckSuggestion,
} from "@/components/magic-lens-modal";
import {
  DirectorModeModal,
  DirectorPlan,
  DirectorSuggestion,
} from "@/components/director-mode-modal";
import {
  BrandPack,
  BrandStudioModal,
  BrandSuggestion,
} from "@/components/brand-studio-modal";
import {
  AudienceMirrorModal,
  AudienceReview,
  AudienceSuggestion,
} from "@/components/audience-mirror-modal";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  toolRequest?: AgentToolRequest | null;
  resultUrl?: string | null;
};

type AssistantApiResponse = {
  success?: boolean;
  reply?: string;
  provider?: string;
  error?: string | null;
  code_version?: string;
};

type SpeechLang = "fr" | "en";
type MicLang = "fr-FR" | "en-US";
type LanguageMode = "en" | "fr";
type ModelMode = "auto" | "fast" | "advanced";

const ASSISTANT_API_BASE = normalizeBackendRoot(
  process.env.NEXT_PUBLIC_ASSISTANT_API_URL || process.env.NEXT_PUBLIC_BACKEND_URL
);
const SUPPORT_ADMIN_NAME =
  process.env.NEXT_PUBLIC_SUPPORT_ADMIN_NAME || "Support Team";
const SUPPORT_ADMIN_EMAIL =
  process.env.NEXT_PUBLIC_SUPPORT_ADMIN_EMAIL || "support@example.com";

const FIRST_GREETING =
  "Hi. I am your Smart Agent for AI Studio Pro. I include Audience Mirror, Launch Pack - Brand Studio, Director Mode + Prompt Doctor, and Neural Camera Analysis. Voice output is English or French only. I ask permission before actions.";

const LANGUAGE_LABELS: Record<LanguageMode, string> = {
  en: "EN",
  fr: "FR",
};

function micLangFromMode(mode: LanguageMode): MicLang {
  if (mode === "fr") return "fr-FR";
  return "en-US";
}

function normalizeArabicText(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

function detectTextLanguage(text: string): SpeechLang {
  const lowered = text.toLowerCase();
  const frenchWords = ["bonjour", "salut", "merci", "français", "francais", "vidéo", "image", "erreur", "paramètres", "aide", "créer", "générer"];
  if (/[àâçéèêëîïôûùüÿœ]/i.test(text) || frenchWords.some((word) => lowered.includes(word))) return "fr";
  return "en";
}

function speechLangForMessage(_text: string, mode: LanguageMode): SpeechLang {
  return mode === "fr" ? "fr" : "en";
}

function getLanguageInstruction(mode: LanguageMode, _userText: string): string {
  if (mode === "fr") {
    return "The user selected French. Answer in French only. Do not use English except product names or code identifiers.";
  }
  return "The user selected English. Answer in English only. Do not use French except product names or code identifiers.";
}

function getLocalKnowledgeReply(message: string, lang: SpeechLang): string | null {
  const lowered = message.replace(/ |​/g, " ").replace(/؛/g, ";").toLowerCase();
  const contactTerms = [
    "contact admin",
    "contact administration",
    "administration contact",
    "support admin",
    "admin email",
    "how can i contact",
    "how do i contact",
    "contact support",
    "reclamation",
    "complaint",
    "contacter",
    "administration",
    "support",
    "réclamation",
    "reclamation",
  ];
  const appTerms = [
    "what is this app",
    "what does this app do",
    "explain the app",
    "describe the app",
    "what can this app do",
    "features",
    "admin features",
    "how does ai studio pro work",
    "about this app",
    "c'est quoi",
    "que fait",
    "explique l'application",
    "fonctionnalités",
    "fonctionnalites",
  ];

  if (contactTerms.some((term) => lowered.includes(term))) {
    if (lang === "fr") {
      return `Tu peux contacter l'administration de AI Studio Pro ici:\n- Support admin: ${SUPPORT_ADMIN_NAME}\n- Email: ${SUPPORT_ADMIN_EMAIL}\n- Téléphone urgent: non configuré pour le moment.\n\nTu peux aussi envoyer une réclamation depuis la page Reclamations / Support Center: écris ton message, l'admin verra le ticket et peut répondre avec le statut et les notes.`;
    }
    return `You can contact the AI Studio Pro administration here:\n- Support admin: ${SUPPORT_ADMIN_NAME}\n- Email: ${SUPPORT_ADMIN_EMAIL}\n- Urgent phone: not configured yet.\n\nYou can also send a message from Reclamations / Support Center: write your issue, submit it, and the admin can reply with status and notes.`;
  }

  if (appTerms.some((term) => lowered.includes(term))) {
    if (lang === "fr") {
      return "AI Studio Pro est un espace créatif IA pour générer des images et faire de l’image-vers-image. Il contient Image Generation, Image-to-Image, Smart Agent avec voix EN/FR uniquement et approbation avant action, Director Mode + Prompt Doctor, Neural Camera Analysis, Brand Studio/Launch Pack, Audience Mirror, History, Credits, Reclamations, Model Comparison, Settings, et Admin Analytics. Les admins peuvent gérer utilisateurs, crédits, générations et tickets. Product Studio/Product Campaign a été supprimé.";
    }
    return "AI Studio Pro is a creative AI workspace for image generation and image-to-image workflows. It includes Image Generation, Image-to-Image, Smart Agent with EN/FR-only voice and approval before actions, Director Mode + Prompt Doctor, Neural Camera Analysis, Brand Studio/Launch Pack, Audience Mirror, History, Credits, Reclamations, Model Comparison, Settings, and Admin Analytics. Admins can manage users, credits, generations, and support tickets. Product Studio/Product Campaign has been removed.";
  }

  return null;
}

function getVisiblePageContext(): string {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return "";
  }

  const path = window.location.pathname;

  const title =
    document.querySelector("h1")?.textContent?.trim() ||
    document.title ||
    "Studio Pro";

  const mainText =
    document.querySelector("main")?.textContent ||
    document.body?.textContent ||
    "";

  const cleanedText = mainText
    .replace(/\s+/g, " ")
    .replace(/Assistant[\s\S]*$/i, "")
    .trim()
    .slice(0, 2500);

  return [
    `Current page: ${path}`,
    `Page title: ${title}`,
    `Visible page content: ${cleanedText}`,
  ].join("\n");
}


function detectWeakSubjectLockPrompt(message: string) {
  const lowered = message.toLowerCase();
  const metricSep = String.raw`\s*(?:[:=]|-|–|—)?\s*`;
  const scorePattern = String.raw`([0-9]+(?:\.[0-9]+)?)\s*(?:\/\s*100|%)?`;
  const subjectMatch = lowered.match(new RegExp(String.raw`(?:subject\s+type|subject_type|type\s+sujet|type_sujet)${metricSep}([a-z0-9_\-/]+)`, "i"));
  const coverageMatch = lowered.match(new RegExp(String.raw`(?:face\s+coverage|subject\s+coverage|coverage|couverture|couverture\s+visage)${metricSep}([0-9]+(?:\.[0-9]+)?)\s*%`, "i"));
  const qualityMatch = lowered.match(new RegExp(String.raw`(?:reference\s+quality|reference_quality|qualit[ée]\s+r[ée]f[ée]rence|qualite\s+reference)${metricSep}${scorePattern}`, "i"));
  const preservationMatch = lowered.match(new RegExp(String.raw`(?:subject\s+preservation|subject_preservation|pr[ée]servation\s+sujet|preservation\s+sujet)${metricSep}${scorePattern}`, "i"));
  const identityMatch = lowered.match(new RegExp(String.raw`(?:identity\s+reliability|identity_reliability(?:_score)?|fiabilit[ée]\s+identit[ée]|fiabilite\s+identite|score\s+fiabilit[ée]\s+identit[ée])\s*(?:score)?${metricSep}${scorePattern}`, "i"));
  const generationMatch = lowered.match(new RegExp(String.raw`(?:generation\s+confidence|generation_confidence(?:_score)?|confiance\s+g[ée]n[ée]ration|confiance\s+generation|score\s+confiance\s+g[ée]n[ée]ration)\s*(?:score)?${metricSep}${scorePattern}`, "i"));
  const blockedGate = new RegExp(String.raw`(?:generation[_\s-]*gate|gate)${metricSep}(blocked|bloqu[ée]|bloque)`, "i").test(lowered);

  const subjectType = subjectMatch?.[1] || (identityMatch || generationMatch ? "person_face" : null);
  const hasMetadata = Boolean(subjectType || coverageMatch || qualityMatch || preservationMatch || identityMatch || generationMatch || blockedGate);
  if (!hasMetadata) return null;

  const coverage = coverageMatch ? Number(coverageMatch[1]) : null;
  const quality = qualityMatch ? Number(qualityMatch[1]) : null;
  const preservation = preservationMatch ? Number(preservationMatch[1]) : null;
  const readScoreFallback = (labels: string[]) => {
    for (const label of labels) {
      const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const match = lowered.match(
        new RegExp(
          `${escaped}\\s*(?:score)?\\s*(?:[:=]|-|–|—)?\\s*([0-9]+(?:\\.[0-9]+)?)\\s*(?:\\/\\s*100|%)?`,
          "i"
        )
      );
      if (match) return Number(match[1]);
    }
    return null;
  };
  const identity = identityMatch ? Number(identityMatch[1]) : readScoreFallback(["identity reliability", "fiabilité identité", "fiabilite identite"]);
  const generation = generationMatch ? Number(generationMatch[1]) : readScoreFallback(["generation confidence", "confiance génération", "confiance generation"]);
  const isPerson = subjectType === "person_face" || subjectType === "person" || identity !== null || generation !== null;

  const failures: string[] = [];
  // Only person-identity metadata is a hard frontend stop. Product/object
  // references remain warning-only and are validated server-side.
  if (!isPerson) return null;

  if (blockedGate) failures.push("generation gate is blocked");
  if (coverage !== null && coverage < 8) failures.push(`face coverage ${coverage}% < 8%`);
  if (identity !== null && identity < 35) failures.push(`identity reliability ${identity}/100 < 35/100`);
  if (generation !== null && generation < 35) failures.push(`generation confidence ${generation}/100 < 35/100`);

  return failures.length > 0 ? { subjectType, failures } : null;
}

function looksLikeSourceLockedPrompt(text: string) {
  const lowered = text.toLowerCase();
  return [
    "uploaded image",
    "uploaded reference",
    "primary identity source",
    "same person from the reference",
    "preserve the exact same person",
    "subject-lock",
    "source-lock",
  ].some((marker) => lowered.includes(marker));
}

function numberValue(value: any): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function selectImageCheckSource(result: ImageCheckAnalyzeResult, suggestion?: ImageCheckSuggestion | null) {
  const profile: any = result.face_profile || {};
  const assessment: any = profile.production_assessment || {};
  const subject: any = profile.subject_analysis || {};
  const real: any = profile.real_face_analysis || {};
  const position: any = real.face_position || {};
  const subjectType = String(subject.subject_type || "unknown").toLowerCase();
  const fullBody = subject.full_body_analysis || {};
  const fullFrame = result.image_url || null;
  const subjectCrop = subject.primary_subject_crop_url || profile.primary_subject_crop_url || null;
  const faceCrop = profile.primary_face_crop_url || subjectCrop || null;
  const coverage = numberValue(position.coverage_percent ?? subject.primary_subject_coverage_percent) ?? 0;
  const quality = numberValue(subject.reference_quality_score ?? assessment.generation_confidence_score ?? real.generation_confidence_score) ?? 0;
  const preservation = numberValue(subject.subject_preservation_score ?? assessment.identity_reliability_score ?? real.identity_reliability_score) ?? 0;
  const stage = suggestion?.workflow_stage || null;

  if (subjectType === "person_full_body" || fullBody.detected) {
    return { url: fullFrame || subjectCrop || faceCrop, strategy: fullFrame ? "full_frame_body_reference" : "subject_crop_reference" };
  }

  if (subjectType === "person_face") {
    if (stage === "identity_expression_board") {
      return { url: faceCrop || fullFrame, strategy: faceCrop ? "face_crop_identity" : "full_frame_camera_reference" };
    }
    if (stage === "pose_style_direction") {
      return { url: fullFrame || faceCrop, strategy: fullFrame ? "full_frame_camera_reference" : "face_crop_identity" };
    }
    const useFullFrame = Boolean(fullFrame) && (coverage >= 14 || (quality >= 60 && preservation >= 60));
    return useFullFrame
      ? { url: fullFrame, strategy: "full_frame_camera_reference" }
      : { url: faceCrop || fullFrame, strategy: faceCrop ? "face_crop_identity" : "full_frame_camera_reference" };
  }

  if (subjectType === "product" || subjectType === "car" || subjectType === "pet" || subjectType === "object_or_product" || subjectType === "document" || subjectType === "document_or_poster") {
    return { url: subjectCrop || fullFrame, strategy: subjectCrop ? "subject_crop_reference" : "full_frame_camera_reference" };
  }

  return { url: fullFrame || subjectCrop || faceCrop, strategy: fullFrame ? "full_frame_camera_reference" : "subject_crop_reference" };
}

function buildImageCheckReferenceArgs(result: ImageCheckAnalyzeResult): Record<string, any> {
  const profile: any = result.face_profile || {};
  const assessment: any = profile.production_assessment || {};
  const subject: any = profile.subject_analysis || {};
  const selectedSource = selectImageCheckSource(result);
  const preferredSource = selectedSource.url;
  const blocked =
    Boolean(subject.hard_block_generation) ||
    subject.can_generate === false ||
    Boolean(assessment.hard_block_generation) ||
    assessment.can_generate === false;

  return {
    source_image_url: preferredSource,
    original_source_image_url: result.image_url || null,
    source_strategy: selectedSource.strategy,
    source_description: result.description || "",
    subject_lock: true,
    gate_allowed: !blocked,
    gate_status: blocked ? "blocked" : "allowed",
    reference_quality_score: subject.reference_quality_score ?? null,
    subject_preservation_score: subject.subject_preservation_score ?? null,
    subject_coverage_percent: subject.primary_subject_coverage_percent ?? null,
    subject_type: subject.subject_type || "unknown",
    identity_lock: subject.subject_type === "person_face",
    identity_review_required: !(subject.can_generate_confidently || assessment.can_generate_confidently),
    identity_warning_summary:
      subject.risks?.[0] || profile.generation_warning_en || profile.generation_warning_fr || null,
  };
}

function hasGenerationIntent(message: string, page: string) {
  const lowered = normalizeArabicText(message.toLowerCase());
  const actionWords = ["generate", "create", "make", "draw", "génère", "genere", "générer", "generer", "crée", "cree"];
  const imageWords = ["image", "photo", "picture", "pic"];
  const videoWords = ["video", "vidéo"];
  const wantsAction = actionWords.some((word) => lowered.includes(normalizeArabicText(word)));
  const namesMedia = [...imageWords, ...videoWords].some((word) => lowered.includes(normalizeArabicText(word)));
  return wantsAction && (namesMedia || page.includes("/generate/image") || page.includes("/generate/image-to-image"));
}

function buildFrontendToolRequest(
  message: string,
  pageContext: string
): AgentToolRequest | null {
  const rawLowered = message.toLowerCase();
  const lowered = normalizeArabicText(rawLowered);
  const page = pageContext.toLowerCase();

  const languageOnlyQuestions = [
    "can you speak",
    "do you speak",
    "speak english",
    "speak french",
    "parle français",
    "parle francais",
    "tu parles",
  ];

  if (
    languageOnlyQuestions.some((word) =>
      lowered.includes(normalizeArabicText(word.toLowerCase()))
    )
  ) {
    return null;
  }

  const actionWords = [
    "generate",
    "génère",
    "genere",
    "générer",
    "generer",
    "create",
    "make",
    "draw",
    "crée",
    "cree",
  ];

  const imageWords = [
    "generate image",
    "génère une image",
    "genere une image",
    "create image",
    "make image",
    "draw image",
    "image",
    "photo",
    "picture",
    "pic",
  ];

  const videoWords = [
    "generate video",
    "génère une vidéo",
    "genere une video",
    "create video",
    "make video",
    "video",
    "vidéo",
  ];

  const downloadWords = [
    "download",
    "télécharger",
    "telecharger",
    "save",
    "download it",
    "yes download",
  ];

  const regenerateWords = [
    "regenerate",
    "again",
    "no regenerate",
  ];

  const wantsAction = actionWords.some((word) =>
    lowered.includes(normalizeArabicText(word.toLowerCase()))
  );

  const wantsImage =
    wantsAction &&
    (imageWords.some((word) =>
      lowered.includes(normalizeArabicText(word.toLowerCase()))
    ) || page.includes("/generate/image"));

  const wantsImageAlternativeForVideo =
    wantsAction &&
    videoWords.some((word) =>
      lowered.includes(normalizeArabicText(word.toLowerCase()))
    );

  const wantsDownload = downloadWords.some((word) =>
    lowered.includes(normalizeArabicText(word.toLowerCase()))
  );

  const wantsRegenerate = regenerateWords.some((word) =>
    lowered.includes(normalizeArabicText(word.toLowerCase()))
  );

  const cleanedPrompt = message
    .replace(/génère/gi, "")
    .replace(/genere/gi, "")
    .replace(/générer/gi, "")
    .replace(/generer/gi, "")
    .replace(/generate/gi, "")
    .replace(/create/gi, "")
    .replace(/make/gi, "")
    .replace(/draw/gi, "")
    .replace(/une image/gi, "")
    .replace(/an image/gi, "")
    .replace(/image/gi, "")
    .replace(/photo/gi, "")
    .replace(/picture/gi, "")
    .replace(/pic/gi, "")
    .replace(/une vidéo/gi, "")
    .replace(/une video/gi, "")
    .replace(/a video/gi, "")
    .replace(/video/gi, "")
    .replace(/vidéo/gi, "")
    .replace(/\s+/g, " ")
    .trim();

  if (wantsDownload) {
    return {
      id: `download_${Date.now()}`,
      tool: "download",
      title: "Download result",
      description: "Download last generated result to PC",
      requires_approval: true,
      args: {},
    };
  }

  if (wantsRegenerate) {
    return {
      id: `regenerate_${Date.now()}`,
      tool: "regenerate",
      title: "Regenerate",
      description: "Regenerate the last approved generation",
      requires_approval: true,
      args: {},
    };
  }

  if (wantsImageAlternativeForVideo) {
    const prompt =
      cleanedPrompt.length > 0
        ? `${cleanedPrompt}, cinematic still composition, natural lighting, high quality, detailed, sharp focus`
        : "cinematic still composition, natural lighting, high quality, detailed, sharp focus";

    return {
      id: `generate_image_${Date.now()}`,
      tool: "generate_image",
      title: "Generate image",
      description: `${prompt}. Video generation is disabled in this image-first workspace, so I prepared a strong still-image alternative.`,
      requires_approval: true,
      args: {
        prompt,
        negative_prompt:
          "blurry, low quality, distorted, noise, artifacts, bad anatomy, watermark, text",
                width: 1280,
        height: 720,
      },
    };
  }

  if (wantsImage) {
    const prompt =
      cleanedPrompt.length > 0
        ? `${cleanedPrompt}, realistic, detailed, natural lighting, high quality, sharp focus`
        : "realistic detailed image, detailed, high quality, sharp focus";

    return {
      id: `generate_image_${Date.now()}`,
      tool: "generate_image",
      title: "Generate image",
      description: prompt,
      requires_approval: true,
      args: {
        prompt,
        negative_prompt:
          "blurry, low quality, distorted, noise, artifacts, bad anatomy, watermark, text",
        width: 1280,
        height: 720,
      },
    };
  }

  return null;
}

export function AssistantSmartAgent() {
  const [isOpen, setIsOpen] = useState(false);
  const [imageCheckOpen, setImageCheckOpen] = useState(false);
  const [directorOpen, setDirectorOpen] = useState(false);
  const [brandStudioOpen, setBrandStudioOpen] = useState(false);
  const [audienceMirrorOpen, setAudienceMirrorOpen] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [languageMode, setLanguageMode] = useState<LanguageMode>("en");
  const [modelMode, setModelMode] = useState<ModelMode>("auto");
  const [speechLang, setSpeechLang] = useState<MicLang>("en-US");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content: FIRST_GREETING,
    },
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [lastResultUrl, setLastResultUrl] = useState<string | null>(null);
  const [lastToolRequest, setLastToolRequest] =
    useState<AgentToolRequest | null>(null);
  const [pendingImageCheckReference, setPendingImageCheckReference] =
    useState<Record<string, any> | null>(null);
  const [pendingPersonaStage2, setPendingPersonaStage2] =
    useState<AgentToolRequest | null>(null);
  const [personaStage2Ready, setPersonaStage2Ready] = useState(false);

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const speakRunIdRef = useRef(0);

  const {
    supported,
    listening,
    transcript,
    finalTranscript,
    error: speechError,
    startListening,
    stopListening,
    resetTranscript,
  } = useSpeechToText({
    lang: speechLang,
    continuous: false,
    interimResults: true,
  });

  const stopSpeaking = () => {
    speakRunIdRef.current = Date.now();

    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }

    if (typeof window !== "undefined") {
      window.speechSynthesis?.cancel();
    }
  };

  const speak = async (text: string, forcedLang?: SpeechLang) => {
    if (!voiceEnabled || typeof window === "undefined") return;

    const runId = Date.now();
    speakRunIdRef.current = runId;

    const cleanText = text
      .replace(/\*\*/g, "")
      .replace(/[#*_`]/g, "")
      .replace(/\n+/g, ". ")
      .slice(0, 900);

    if (!cleanText.trim()) return;

    // Arabic-script text stays supported in chat, but it must never be spoken
    // through Piper or the browser EN/FR fallback.
    if (/[\u0600-\u06FF]/.test(cleanText)) return;

    try {
      stopSpeaking();
      speakRunIdRef.current = runId;

      const lang = forcedLang || speechLangForMessage(cleanText, languageMode);

      const response = await fetch(`${ASSISTANT_API_BASE}/assistant/speech`, {
        method: "POST",
        headers: withAuthHeaders({
          "Content-Type": "application/json",
        }),
        body: JSON.stringify({
          text: cleanText,
          lang,
        }),
      });

      const data = await response.json();

      if (speakRunIdRef.current !== runId) return;

      if (!response.ok || !data?.success || !data?.audio_url) {
        throw new Error(
          data?.error || `Piper speech failed with status ${response.status}`
        );
      }

      const audioUrl = String(data.audio_url).startsWith("http")
        ? data.audio_url
        : `${ASSISTANT_API_BASE}${String(data.audio_url).startsWith("/") ? "" : "/"}${data.audio_url}`;
      const audio = new Audio(audioUrl);
      audio.volume = 1;
      audioRef.current = audio;

      audio.onended = () => {
        if (audioRef.current === audio) {
          audioRef.current = null;
        }
      };

      await audio.play();
    } catch (error) {
      console.error("Assistant speech API failed, using browser TTS fallback:", error);
      try {
        const fallbackLang = (forcedLang || speechLangForMessage(cleanText, languageMode)) === "fr" ? "fr-FR" : "en-US";
        window.speechSynthesis?.cancel();
        const utterance = new SpeechSynthesisUtterance(cleanText);
        utterance.lang = fallbackLang;
        window.speechSynthesis?.speak(utterance);
      } catch (browserSpeechError) {
        console.error("Browser TTS fallback failed:", browserSpeechError);
      }
    }
  };

  useEffect(() => {
    const spoken = `${finalTranscript} ${transcript}`.trim();

    if (spoken) {
      setInput(spoken);
    }
  }, [finalTranscript, transcript]);

  const scrollToBottom = () => {
    setTimeout(() => {
      scrollRef.current?.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    }, 50);
  };

  const openAgent = () => {
    setIsOpen(true);
  };

  const closeAgent = () => {
    stopSpeaking();
    setIsOpen(false);
  };

  const handleLanguageChange = (nextMode: LanguageMode) => {
    if (listening) {
      stopListening();
    }

    stopSpeaking();
    resetTranscript();
    setInput("");
    setLanguageMode(nextMode);
    setSpeechLang(micLangFromMode(nextMode));

    const languageMessage =
      nextMode === "fr"
        ? "Mode français activé. Je répondrai uniquement en français."
        : "English mode enabled. I will answer in English only.";

    setMessages([
      {
        role: "assistant",
        content: languageMessage,
      },
    ]);

    const voiceLang: SpeechLang = nextMode === "fr" ? "fr" : "en";

    speak(languageMessage, voiceLang);
  };

  const requestMicrophonePermission = async () => {
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        const msg =
          languageMode === "fr"
            ? "Ce navigateur ne prend pas en charge le micro. Essaie Chrome ou Edge."
            : "This browser does not support microphone input. Try Chrome or Edge.";

        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: msg,
          },
        ]);

        speak(msg, languageMode === "fr" ? "fr" : "en");
        return;
      }

      await navigator.mediaDevices.getUserMedia({ audio: true });
      startListening();
    } catch (error) {
      const msg =
        languageMode === "fr"
          ? "Autorise le micro dans le navigateur pour que je puisse t’écouter."
          : "Allow microphone permission in the browser so I can hear you.";

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: msg,
        },
      ]);

      speak(msg, languageMode === "fr" ? "fr" : "en");
      console.error("Microphone permission denied:", error);
    }
  };

  const addAssistantMessage = (
    content: string,
    extras?: Partial<ChatMessage>,
    forcedLang?: SpeechLang
  ) => {
    setMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        content,
        ...extras,
      },
    ]);

    speak(content, forcedLang);
    scrollToBottom();
  };

  const buildImageCheckSummary = (result: ImageCheckAnalyzeResult) => {
    const profile: any = result.face_profile || {};
    const subject: any = profile.subject_analysis || {};
    const assessment: any = profile.production_assessment || {};
    const real: any = profile.real_face_analysis || {};
    const pos: any = real.face_position || {};
    const subjectType = subject.subject_type || "unknown";
    const coverage = subject.primary_subject_coverage_percent ?? pos.coverage_percent ?? "-";
    const preservation = subject.subject_preservation_score ?? assessment.identity_reliability_score ?? real.identity_reliability_score ?? "-";
    const quality = subject.reference_quality_score ?? assessment.generation_confidence_score ?? real.generation_confidence_score ?? "-";
    const gate = subject.hard_block_generation ? "blocked" : subject.can_generate_confidently ? "client-ready" : subject.can_generate ? "review" : "waiting";
    if (languageMode === "fr") {
      return `Sujet: ${subjectType}. Couverture ${coverage}% · préservation ${preservation}/100 · qualité ${quality}/100 · gate ${gate}.`;
    }
    return `Subject: ${subjectType}. Coverage ${coverage}% · preservation ${preservation}/100 · quality ${quality}/100 · gate ${gate}.`;
  };

  const buildImageCheckBlockText = (result: ImageCheckAnalyzeResult) => {
    const profile: any = result.face_profile || {};
    const subject: any = profile.subject_analysis || {};
    const assessment: any = profile.production_assessment || {};
    const recommendations: string[] = [...(subject.recommendations || []), ...(assessment.recommendations || [])];
    const first = recommendations[0] || (
      languageMode === "fr"
        ? "Recadre le sujet ou reprends une référence plus nette avant de générer."
        : "Crop the subject or retake a sharper reference before generating."
    );
    if (subject.hard_block_generation) {
      if (languageMode === "fr") {
        return `Référence bloquée pour identity-lock. ${buildImageCheckSummary(result)} Recommandation: ${first}`;
      }
      return `Reference blocked for identity lock. ${buildImageCheckSummary(result)} Recommendation: ${first}`;
    }
    if (languageMode === "fr") {
      return `Référence faible mais utilisable. ${buildImageCheckSummary(result)} Auto-crop activé. Recommandation: ${first}`;
    }
    return `Weak but usable reference. ${buildImageCheckSummary(result)} Auto-crop enabled. Recommendation: ${first}`;
  };

  const handleImageCheckSuggestion = (
    suggestion: ImageCheckSuggestion,
    result: ImageCheckAnalyzeResult
  ) => {
    // Step 1 is now an optional identity-review helper. Do not hard-lock
    // Step 2, otherwise the assistant can appear stuck after the user clicks
    // the full-body/wardrobe action from Neural Camera Analysis.
    const isDirectStage2WithoutReview =
      suggestion.workflow_stage === "pose_style_direction" && !personaStage2Ready;

    setImageCheckOpen(false);
    const referenceArgs = buildImageCheckReferenceArgs(result);
    setPendingImageCheckReference(referenceArgs);

    if (suggestion.action === "make_prompt") {
      setInput(suggestion.prompt);

      const msg =
        languageMode === "fr"
          ? "J'ai préparé le prompt dans la zone de texte. Tu peux le modifier ou l'envoyer."
          : languageMode === "en"
          ? "I prepared the prompt in the text box. You can edit it or send it."
          : "I placed the prompt in the input. You can edit it or send it.";

      addAssistantMessage(
        msg,
        {},
        languageMode === "fr" ? "fr" : "en"
      );

      return;
    }

    const profile: any = result.face_profile || {};
    const assessment: any = profile.production_assessment || {};
    const subject: any = profile.subject_analysis || {};
    const selectedSource = selectImageCheckSource(result, suggestion);
    const preferredSource = selectedSource.url;
    const identityReviewRequired = !(subject.can_generate_confidently || assessment.can_generate_confidently);
    const blocked =
      Boolean(subject.hard_block_generation) ||
      subject.can_generate === false ||
        Boolean(assessment.hard_block_generation) ||
      assessment.can_generate === false;

    if (blocked) {
      addAssistantMessage(
        languageMode === "fr"
          ? `Exécution bloquée. ${buildImageCheckBlockText(result)}`
          : `Execution blocked. ${buildImageCheckBlockText(result)}`,
        {},
        languageMode === "fr" ? "fr" : "en"
      );
      return;
    }

    const toolRequest: AgentToolRequest = {
      id: `image_check_${suggestion.action}_${Date.now()}`,
      tool: suggestion.action,
      title: suggestion.title,
      description: suggestion.description || buildImageCheckSummary(result),
      requires_approval: true,
      args: {
        ...referenceArgs,
        prompt: suggestion.prompt,
        negative_prompt:
          suggestion.negative_prompt ||
          "blurry, low quality, distorted, noise, artifacts, bad anatomy, watermark, text",
        width: suggestion.width || 1280,
        height: suggestion.height || 720,
        source_image_url: preferredSource,
        original_source_image_url: result.image_url || null,
        source_strategy: selectedSource.strategy,
        source_description: result.description || "",
        prefer_img2img: suggestion.action === "generate_image",
        strength: suggestion.strength ?? 0.22,
        generation_mode: suggestion.generation_mode || (subject.subject_type === "person_face" ? "person_identity" : "auto"),
        persona_workflow_stage: suggestion.workflow_stage || null,
        persona_layout: suggestion.layout || null,
        motion_strength: 35,
        identity_lock: suggestion.action === "generate_image" && subject.subject_type === "person_face",
        subject_lock: true,
        gate_allowed: !blocked,
        gate_status: blocked ? "blocked" : "allowed",
        reference_quality_score: subject.reference_quality_score ?? null,
        subject_preservation_score: subject.subject_preservation_score ?? null,
        subject_coverage_percent: subject.primary_subject_coverage_percent ?? null,
        subject_type: subject.subject_type || "unknown",
        identity_review_required: identityReviewRequired,
        identity_warning_summary:
          subject.risks?.[0] || profile.generation_warning_en || profile.generation_warning_fr || null,
      },
    };

    if (suggestion.workflow_stage === "identity_expression_board") {
      const stage2Suggestion = result.suggestions.find(
        (item) => item.action === "generate_image" && item.workflow_stage === "pose_style_direction"
      );
      if (stage2Suggestion) {
        setPersonaStage2Ready(false);
        setPendingPersonaStage2({
          ...toolRequest,
          id: `image_check_stage2_${Date.now()}`,
          title: stage2Suggestion.title,
          description: stage2Suggestion.description || "Full-body pose and wardrobe direction board after identity review.",
          args: {
            ...toolRequest.args,
            prompt: stage2Suggestion.prompt,
            negative_prompt: stage2Suggestion.negative_prompt || toolRequest.args.negative_prompt,
            source_image_url: selectImageCheckSource(result, stage2Suggestion).url,
            source_strategy: selectImageCheckSource(result, stage2Suggestion).strategy,
            width: stage2Suggestion.width || 1536,
            height: stage2Suggestion.height || 1024,
            strength: stage2Suggestion.strength ?? 0.35,
            generation_mode: stage2Suggestion.generation_mode || "person_identity",
            persona_workflow_stage: "pose_style_direction",
            persona_layout: stage2Suggestion.layout || null,
          },
        });
      }
    }

    if (suggestion.workflow_stage === "pose_style_direction") {
      setPendingPersonaStage2(null);
    }

    const weakWarning = identityReviewRequired
      ? languageMode === "fr"
        ? " Référence utilisable avec auto-crop et revue du résultat."
        : " Reference usable with auto-crop and result review."
      : "";

    const directStage2Notice = isDirectStage2WithoutReview
      ? languageMode === "fr"
        ? " Étape 2 lancée en mode direct: l'étape 1 est optionnelle et sert uniquement à vérifier l'identité."
        : " Step 2 direct mode: step 1 is optional and only used for identity review."
      : "";

    const text =
      languageMode === "fr"
        ? `Neural Camera Analysis prêt. ${toolRequest.description}${weakWarning}${directStage2Notice} Confirmer l'exécution ?`
        : languageMode === "en"
        ? `Neural Camera Analysis ready. ${toolRequest.description}${weakWarning}${directStage2Notice} Approve execution?`
        : `Neural Camera Analysis ready. ${toolRequest.description}${weakWarning}${directStage2Notice} Approve execution?`;

    addAssistantMessage(
      text,
      { toolRequest },
      languageMode === "fr" ? "fr" : "en"
    );
  };

  const handleDirectorSuggestion = (
    suggestion: DirectorSuggestion,
    plan: DirectorPlan
  ) => {
    setDirectorOpen(false);

    if (suggestion.action === "make_prompt") {
      setInput(suggestion.prompt);

      addAssistantMessage(
        languageMode === "fr"
          ? "J'ai préparé le prompt amélioré dans la zone de texte. Tu peux le modifier ou l'envoyer."
          : languageMode === "en"
          ? "I prepared the improved prompt in the text box. You can edit it or send it."
          : "I placed the improved prompt in the input. You can edit it or send it.",
        {},
        languageMode === "fr" ? "fr" : "en"
      );

      return;
    }

    const toolRequest: AgentToolRequest = {
      id: `director_${suggestion.action}_${Date.now()}`,
      tool: suggestion.action,
      title: suggestion.title,
      description: suggestion.prompt,
      requires_approval: true,
      args: {
        prompt: suggestion.prompt,
        negative_prompt:
          suggestion.negative_prompt ||
          plan.negative_prompt ||
          "blurry, low quality, distorted, noise, artifacts, bad anatomy, watermark, text",
        width: suggestion.width || 1280,
        height: suggestion.height || 720,
        director_plan: {
          title: plan.title,
          summary: plan.summary,
          scene: plan.scene,
          style: plan.style,
          lighting: plan.lighting,
          camera: plan.camera,
          mood: plan.mood,
          caption: plan.caption,
        },
      },
    };

    const text =
      languageMode === "fr"
        ? `Director Mode a préparé le plan. Action prête : ${suggestion.title}. Confirmer l'exécution ?`
        : languageMode === "en"
        ? `Director Mode prepared the plan. I can run this action: ${suggestion.title}. Do you approve?`
        : `Director Mode prepared the plan. I can run this action: ${suggestion.title}. Do you approve?`;

    addAssistantMessage(
      text,
      { toolRequest },
      languageMode === "fr" ? "fr" : "en"
    );
  };


  const handleAudienceSuggestion = (
    suggestion: AudienceSuggestion,
    review: AudienceReview
  ) => {
    setAudienceMirrorOpen(false);

    if (suggestion.action === "copy_review" || suggestion.action === "fix_prompt") {
      setInput(suggestion.prompt);

      addAssistantMessage(
        languageMode === "fr"
          ? "J'ai préparé l'analyse ou le prompt amélioré dans la zone de texte."
          : languageMode === "en"
          ? "I prepared the review or improved prompt in the text box."
          : "I placed the analysis or improved prompt in the input.",
        {},
        languageMode === "fr" ? "fr" : "en"
      );

      return;
    }

    const toolRequest: AgentToolRequest = {
      id: `audience_${suggestion.action}_${Date.now()}`,
      tool: suggestion.action,
      title: suggestion.title,
      description: suggestion.prompt,
      requires_approval: true,
      args: {
        prompt: suggestion.prompt,
        negative_prompt:
          suggestion.negative_prompt ||
          review.negative_prompt ||
          "blurry, low quality, cluttered, confusing text, weak CTA, watermark, distorted, noisy",
        width: suggestion.width || 1280,
        height: suggestion.height || 720,
        audience_review: {
          title: review.content_title,
          summary: review.executive_summary,
          scores: review.scores,
          publish_advice: review.publish_advice,
        },
      },
    };

    const text =
      languageMode === "fr"
        ? `Audience Mirror a terminé le test. Version prête : ${suggestion.title}. Confirmer l'exécution ?`
        : languageMode === "en"
        ? `Audience Mirror finished the test. I can run this improved version: ${suggestion.title}. Do you approve?`
        : `Audience Mirror finished the test. I can run this improved version: ${suggestion.title}. Do you approve?`;

    addAssistantMessage(
      text,
      { toolRequest },
      languageMode === "fr" ? "fr" : "en"
    );
  };

  const handleBrandSuggestion = (
    suggestion: BrandSuggestion,
    pack: BrandPack
  ) => {
    setBrandStudioOpen(false);

    if (suggestion.action === "copy_pack") {
      setInput(suggestion.prompt);

      addAssistantMessage(
        languageMode === "fr"
          ? "J'ai préparé le Launch Pack complet dans la zone de texte. Tu peux le copier ou le modifier."
          : languageMode === "en"
          ? "I prepared the complete Launch Pack in the text box. You can copy it or edit it."
          : "I placed the complete Launch Pack in the input. You can copy or edit it.",
        {},
        languageMode === "fr" ? "fr" : "en"
      );

      return;
    }

    const toolRequest: AgentToolRequest = {
      id: `brand_${suggestion.action}_${Date.now()}`,
      tool: suggestion.action,
      title: suggestion.title,
      description: suggestion.prompt,
      requires_approval: true,
      args: {
        prompt: suggestion.prompt,
        negative_prompt:
          suggestion.negative_prompt ||
          pack.negative_prompt ||
          "blurry, low quality, distorted, noise, artifacts, bad anatomy, watermark, text",
        width: suggestion.width || 1280,
        height: suggestion.height || 720,
        brand_pack: {
          brand_name: pack.brand_name,
          business_type: pack.business_type,
          audience: pack.audience,
          slogan: pack.slogan,
          brand_voice: pack.brand_voice,
          colors: pack.colors,
          cta: pack.cta,
        },
      },
    };

    const text =
      languageMode === "fr"
        ? `Brand Studio a préparé le Launch Pack. Action prête : ${suggestion.title}. Confirmer l'exécution ?`
        : languageMode === "en"
        ? `Brand Studio prepared the Launch Pack. I can run this action: ${suggestion.title}. Do you approve?`
        : `Brand Studio prepared the Launch Pack. I can run this action: ${suggestion.title}. Do you approve?`;

    addAssistantMessage(
      text,
      { toolRequest },
      languageMode === "fr" ? "fr" : "en"
    );
  };

  const sendMessage = async () => {
    const clean = input.trim();

    if (!clean || isLoading) return;

    const pagePath =
      typeof window !== "undefined" ? window.location.pathname : "";

    const weakSubjectGate = detectWeakSubjectLockPrompt(clean);

    const outputLang = speechLangForMessage(clean, languageMode);
    const languageInstruction = getLanguageInstruction(languageMode, clean);
    const visibleContext = getVisiblePageContext();
    const pageContext = `${pagePath} | ${languageInstruction}\n${visibleContext}`;

    let localToolRequest = buildFrontendToolRequest(clean, pagePath);

    // A prompt copied from Camera / Neural Camera Analysis still needs the captured source
    // image. Previously the source URL was lost and the assistant silently fell
    // back to a generic text conversation instead of running img2img.
    if (!localToolRequest && pendingImageCheckReference?.source_image_url && looksLikeSourceLockedPrompt(clean)) {
      localToolRequest = {
        id: `camera_prompt_generate_image_${Date.now()}`,
        tool: "generate_image",
        title: "Generate camera subject-lock image",
        description: clean,
        requires_approval: true,
        args: {
          ...pendingImageCheckReference,
          prompt: clean,
          negative_prompt: "blurry, low quality, distorted, noise, artifacts, watermark, text, identity drift, different person, warped face",
          width: 1280,
          height: 720,
          prefer_img2img: true,
          strength: 0.22,
          generation_mode: pendingImageCheckReference.subject_type === "person_face" ? "person_identity" : "auto",
        },
      };
    }

    if (
      localToolRequest &&
      pendingImageCheckReference?.source_image_url &&
      (localToolRequest.tool === "generate_image") &&
      (looksLikeSourceLockedPrompt(clean) || clean.toLowerCase().includes("camera") || clean.toLowerCase().includes("this image"))
    ) {
      localToolRequest = {
        ...localToolRequest,
        args: {
          ...pendingImageCheckReference,
          ...localToolRequest.args,
          prefer_img2img: localToolRequest.tool === "generate_image",
          strength: localToolRequest.tool === "generate_image" ? 0.22 : localToolRequest.args.strength,
          generation_mode:
            pendingImageCheckReference.subject_type === "person_face"
              ? "person_identity"
              : localToolRequest.args.generation_mode || "auto",
        },
      };
    }

    if (
      localToolRequest &&
      weakSubjectGate &&
      (localToolRequest.tool === "generate_image")
    ) {
      const blockedReply =
        outputLang === "fr"
          ? `Référence personne vraiment trop faible pour identity lock. Corrige la référence avant de générer : ${weakSubjectGate.failures.join("; ")}.`
          : `Person reference is too weak for identity lock. Fix the reference before generating: ${weakSubjectGate.failures.join("; ")}.`;

      setMessages((prev) => [
        ...prev,
        { role: "user", content: clean },
        { role: "assistant", content: blockedReply },
      ]);
      setInput("");
      resetTranscript();
      speak(blockedReply, outputLang);
      scrollToBottom();
      return;
    }

    if (localToolRequest) {
      const nextMessages: ChatMessage[] = [
        ...messages,
        {
          role: "user",
          content: clean,
        },
      ];

      setMessages(nextMessages);
      setInput("");
      resetTranscript();

      const approvalReply =
        outputLang === "fr"
          ? `Action prête : ${localToolRequest.title}. Confirmer l'exécution ?`
          : outputLang === "en"
          ? `Action ready: ${localToolRequest.title}. Approve execution?`
          : `Action ready: ${localToolRequest.title}. Approve execution?`;

      addAssistantMessage(
        approvalReply,
        {
          toolRequest: localToolRequest,
        },
        outputLang
      );

      return;
    }

    // If a Neural Camera/source-lock prompt was copied into the assistant but
    // the active source image is not available in assistant state, answer
    // locally instead of waiting for Ollama. This prevents the chat bubble from
    // staying on "Assistant is thinking..." and tells the user exactly what to do.
    if (!localToolRequest && looksLikeSourceLockedPrompt(clean) && !pendingImageCheckReference?.source_image_url) {
      const noSourceReply =
        outputLang === "fr"
          ? "Prompt Neural Camera détecté, mais je n'ai pas l'image source active dans cette fenêtre. Va dans Image-to-Image, upload l'image, ouvre Neural Camera Analysis, clique Put in prompt, puis lance Generate. Je n'appelle pas l'Assistant API pour éviter un chargement bloqué."
          : "Neural Camera prompt detected, but I do not have the active source image in this assistant session. Go to Image-to-Image, upload the image, open Neural Camera Analysis, click Put in prompt, then run Generate. I am not calling the Assistant API, so it will not stay stuck thinking.";

      setMessages((prev) => [
        ...prev,
        { role: "user", content: clean },
        { role: "assistant", content: noSourceReply },
      ]);
      setInput("");
      resetTranscript();
      speak(noSourceReply, outputLang);
      scrollToBottom();
      return;
    }

    const localKnowledgeReply = getLocalKnowledgeReply(clean, outputLang);
    if (localKnowledgeReply) {
      setMessages((prev) => [
        ...prev,
        { role: "user", content: clean },
        { role: "assistant", content: localKnowledgeReply },
      ]);
      setInput("");
      resetTranscript();
      speak(localKnowledgeReply, outputLang);
      scrollToBottom();
      return;
    }

    const nextMessages: ChatMessage[] = [
      ...messages,
      {
        role: "user",
        content: clean,
      },
    ];

    setMessages(nextMessages);
    setInput("");
    setIsLoading(true);
    resetTranscript();
    scrollToBottom();

    const assistantController = new AbortController();
    const assistantTimeout = window.setTimeout(() => assistantController.abort(), 12000);

    try {
      const response = await fetch(`${ASSISTANT_API_BASE}/assistant/chat`, {
        method: "POST",
        signal: assistantController.signal,
        headers: withAuthHeaders({
          "Content-Type": "application/json",
        }),
        body: JSON.stringify({
          message: clean,
          lang: languageMode,
          model_mode: modelMode,
          messages: nextMessages
            .filter((msg) => msg.role === "user" || msg.role === "assistant")
            .slice(-4)
            .map((msg) => ({
              role: msg.role,
              content: msg.content.slice(0, 900),
            })),
          page_context: pageContext,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text().catch(() => "");
        throw new Error(
          `Assistant request failed: ${response.status} ${errorText}`
        );
      }

      window.clearTimeout(assistantTimeout);

      const data: AssistantApiResponse = await response.json();

      const reply =
        data?.reply ||
        (outputLang === "fr"
          ? "Je n'ai pas pu répondre maintenant. Réessaie."
          : outputLang === "en"
          ? "I could not answer right now. Please try again."
          : "I could not answer right now. Please try again.");

      addAssistantMessage(
        reply,
        {
          toolRequest: null,
        },
        outputLang
      );
    } catch (error: any) {
      window.clearTimeout(assistantTimeout);
      console.error("Assistant chat failed:", error);

      const assistantHealthUrl = `${ASSISTANT_API_BASE}/assistant/health`;
      const msg =
        error?.name === "AbortError"
          ? outputLang === "fr"
            ? "Assistant API a dépassé 12 secondes. J'ai arrêté l'attente pour éviter que l'interface reste bloquée. Utilise les boutons Neural Camera / Put in prompt pour les actions caméra, ou vérifie Ollama si tu veux une réponse chat."
            : "Assistant API took more than 12 seconds. I stopped waiting so the UI does not stay stuck. Use Neural Camera / Put in prompt for camera actions, or check Ollama if you want chat replies."
          : outputLang === "fr"
          ? `Il y a un problème de connexion avec Assistant API. Vérifie le backend: ${assistantHealthUrl}`
          : `There is a connection problem with Assistant API. Check the backend: ${assistantHealthUrl}`;

      addAssistantMessage(msg, {}, outputLang);
    } finally {
      window.clearTimeout(assistantTimeout);
      setIsLoading(false);
      scrollToBottom();
    }
  };

  const approveTool = async (toolRequest: AgentToolRequest) => {
    setIsLoading(true);

    const outputLang = speechLangForMessage(
      toolRequest.description,
      languageMode
    );

    const startedText =
      outputLang === "fr"
        ? `D'accord, je commence : ${toolRequest.title}.`
        : outputLang === "en"
        ? `Okay, I started: ${toolRequest.title}.`
        : `Okay, I started: ${toolRequest.title}.`;

    setMessages((prev) => [
      ...prev.map((message) =>
        message.toolRequest?.id === toolRequest.id
          ? { ...message, toolRequest: null }
          : message
      ),
      {
        role: "user",
        content: `Approved: ${toolRequest.title}`,
      },
      {
        role: "assistant",
        content: startedText,
      },
    ]);

    speak(startedText, outputLang);
    scrollToBottom();

    try {
      const result = await executeAgentTool(
        toolRequest,
        lastResultUrl,
        lastToolRequest
          ? async () => executeAgentTool(lastToolRequest, lastResultUrl, null)
          : null
      );

      let finalResult = result;

      if (result.ok && result.generationId && !result.resultUrl) {
        const waitText =
          outputLang === "fr"
            ? "L'opération a commencé. J'attends le résultat. Cela peut prendre un peu de temps."
            : outputLang === "en"
            ? "The operation has started. I am waiting for the result. This may take some time."
            : "The operation has started. I am waiting for the result. This may take some time.";

        addAssistantMessage(waitText, {}, outputLang);
        finalResult = await pollGenerationResult(result.generationId);
      }

      if (finalResult.resultUrl) {
        setLastResultUrl(finalResult.resultUrl);
      }

      if (
        finalResult.ok &&
        (toolRequest.tool === "generate_image")
      ) {
        setLastToolRequest(toolRequest);
      }

      const reply = finalResult.ok
        ? outputLang === "fr"
          ? `${finalResult.message}

Est-ce que le résultat te plaît ? Je peux le télécharger ou le régénérer.`
          : `${finalResult.message}

Do you like the result? I can download it or regenerate it.`
        : outputLang === "fr"
        ? `L'opération a échoué : ${finalResult.message}`
        : `The operation failed: ${finalResult.message}`;

      addAssistantMessage(
        reply,
        {
          resultUrl: finalResult.resultUrl || null,
        },
        outputLang
      );

      if (
        finalResult.ok &&
        finalResult.resultUrl &&
        toolRequest.args?.persona_workflow_stage === "identity_expression_board" &&
        pendingPersonaStage2
      ) {
        setPersonaStage2Ready(true);
        const stage2Text =
          outputLang === "fr"
            ? "Étape 1 terminée. Vérifie que l'identité du visage est correcte. Si elle te convient, approuve maintenant l'étape 2 pour générer les directions de poses et de tenues."
            : "Step 1 is complete. Review the facial identity. If it looks correct, approve step 2 to generate pose and outfit directions.";
        addAssistantMessage(stage2Text, { toolRequest: pendingPersonaStage2 }, outputLang);
        setPendingPersonaStage2(null);
      }

      if (finalResult.ok && toolRequest.args?.persona_workflow_stage === "pose_style_direction") {
        setPersonaStage2Ready(false);
      }
    } catch (error: any) {
      console.error("Assistant action failed:", error);

      const msg =
        error?.message ||
        (outputLang === "fr"
          ? "L'opération a échoué. Vérifie la console du backend et du frontend."
          : outputLang === "en"
          ? "The operation failed. Check backend and frontend console."
          : "The operation failed. Check the backend and frontend consoles.");

      addAssistantMessage(msg, {}, outputLang);
    } finally {
      setIsLoading(false);
      scrollToBottom();
    }
  };

  const rejectTool = (toolRequest: AgentToolRequest) => {
    setMessages((prev) => [
      ...prev.map((message) =>
        message.toolRequest?.id === toolRequest.id
          ? { ...message, toolRequest: null }
          : message
      ),
      {
        role: "user",
        content: `Rejected: ${toolRequest.title}`,
      },
    ]);

    addAssistantMessage(
      languageMode === "fr"
        ? "D'accord, je n'exécute rien. Donne-moi une autre commande ou modifie le prompt."
        : "Okay, I did not run anything. Give me a new command or change the prompt.",
      {},
      languageMode === "fr" ? "fr" : "en"
    );
  };

  const quickDownload = async () => {
    const result = await executeAgentTool(
      {
        id: `download_${Date.now()}`,
        tool: "download",
        title: "Download result",
        description: "Download last generated result",
        requires_approval: false,
        args: {},
      },
      lastResultUrl,
      null
    );

    addAssistantMessage(result.message);
  };

  const quickRegenerate = async () => {
    if (!lastToolRequest) {
      addAssistantMessage(
        languageMode === "fr"
          ? "Aucune opération précédente à régénérer. Donne-moi un nouveau prompt."
          : "There is no previous operation to regenerate. Give me a new prompt.",
        {},
        languageMode === "fr" ? "fr" : "en"
      );
      return;
    }

    await approveTool(lastToolRequest);
  };

  const handleKeyDown = (e: any) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <>
      {!isOpen && (
        <button
          type="button"
          onClick={openAgent}
          className="fixed bottom-6 right-6 z-[9999] group flex items-center gap-3 rounded-full border border-fuchsia-400/30 bg-black/90 px-4 py-3 text-white shadow-[0_0_35px_rgba(217,70,239,0.35)] backdrop-blur-xl transition hover:scale-[1.03] hover:border-fuchsia-300/60 hover:bg-[#120617]"
        >
          <span className="relative flex h-11 w-11 items-center justify-center rounded-full bg-gradient-to-br from-fuchsia-500 to-cyan-400 shadow-[0_0_25px_rgba(217,70,239,0.45)]">
            <Bot className="h-6 w-6 text-white" />
            <span className="absolute -right-0.5 -top-0.5 h-3.5 w-3.5 rounded-full border-2 border-black bg-emerald-400" />
          </span>

          <span className="hidden sm:block text-left">
            <span className="block text-sm font-bold leading-none">
              Assistant
            </span>
            <span className="mt-1 block text-xs text-white/55">
              Text-first • Tools • Projects
            </span>
          </span>

          <span className="hidden h-2 w-2 rounded-full bg-cyan-300 sm:block" />
        </button>
      )}

      {isOpen && (
        <div className="fixed bottom-6 right-6 z-[9999] w-[calc(100vw-32px)] max-w-[500px] overflow-hidden rounded-[28px] border border-white/10 bg-black text-white shadow-[0_0_70px_rgba(217,70,239,0.25)] backdrop-blur-2xl">
          <div className="pointer-events-none absolute inset-0">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(217,70,239,0.22),transparent_35%),radial-gradient(circle_at_bottom_right,rgba(34,211,238,0.16),transparent_35%),linear-gradient(180deg,#080808_0%,#050505_100%)]" />

            <div
              className="absolute inset-0 opacity-[0.12]"
              style={{
                backgroundImage:
                  "radial-gradient(rgba(255,255,255,0.55) 0.6px, transparent 0.6px)",
                backgroundSize: "22px 22px",
              }}
            />
          </div>

          <div className="relative z-10">
            <div className="flex items-center justify-between border-b border-white/10 p-4">
              <div className="flex items-center gap-3">
                <div className="relative flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-fuchsia-500 to-cyan-400 shadow-[0_0_28px_rgba(217,70,239,0.35)]">
                  <Bot className="h-6 w-6 text-white" />
                  <span className="absolute -right-1 -top-1 h-4 w-4 rounded-full border-2 border-black bg-emerald-400" />
                </div>

                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold leading-none">Assistant</h3>
                    <span className="rounded-full border border-emerald-400/25 bg-emerald-400/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-300">
                      Online
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-white/55">
                    Text/Voice optional • {LANGUAGE_LABELS[languageMode]} • Project tools
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    const next = !voiceEnabled;
                    setVoiceEnabled(next);
                    if (!next) stopSpeaking();
                  }}
                  className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/5 text-white/70 transition hover:bg-white/10 hover:text-white"
                  title={voiceEnabled ? "Disable assistant voice" : "Enable assistant voice (EN / FR only)"}
                >
                  {voiceEnabled ? (
                    <Volume2 className="h-4 w-4" />
                  ) : (
                    <VolumeX className="h-4 w-4" />
                  )}
                </button>

                <button
                  type="button"
                  onClick={closeAgent}
                  className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/5 text-white/70 transition hover:bg-white/10 hover:text-white"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div
              ref={scrollRef}
              className="max-h-[440px] min-h-[350px] space-y-3 overflow-y-auto p-4"
            >
              {messages.map((message, index) => {
                const isUser = message.role === "user";

                return (
                  <div
                    key={`${message.role}-${index}`}
                    className={`flex ${
                      isUser ? "justify-end" : "justify-start"
                    }`}
                  >
                    <div
                      className={`max-w-[88%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-6 ${
                        isUser
                          ? "bg-fuchsia-600 text-white shadow-[0_0_22px_rgba(217,70,239,0.25)]"
                          : "border border-white/10 bg-white/[0.06] text-white/85"
                      }`}
                    >
                      {message.content}

                      {message.resultUrl && (
                        <div className="mt-3 overflow-hidden rounded-xl border border-white/10 bg-black/40">
                          {message.resultUrl.toLowerCase().includes(".mp4") ? (
                            <video
                              src={message.resultUrl}
                              controls
                              className="max-h-52 w-full"
                            />
                          ) : (
                            <img
                              src={message.resultUrl}
                              alt="Generated result"
                              className="max-h-52 w-full object-contain"
                            />
                          )}

                          <div className="grid grid-cols-2 gap-2 p-2">
                            <Button
                              type="button"
                              size="sm"
                              onClick={quickDownload}
                              className="bg-emerald-600 text-white hover:bg-emerald-500"
                            >
                              <Download className="mr-1 h-3.5 w-3.5" />
                              Download
                            </Button>

                            <Button
                              type="button"
                              size="sm"
                              onClick={quickRegenerate}
                              className="bg-fuchsia-600 text-white hover:bg-fuchsia-500"
                            >
                              <RefreshCw className="mr-1 h-3.5 w-3.5" />
                              Regenerate
                            </Button>
                          </div>
                        </div>
                      )}

                      {message.toolRequest && (
                        <div className="mt-3 rounded-2xl border border-fuchsia-400/25 bg-fuchsia-500/10 p-3">
                          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-fuchsia-100">
                            {message.toolRequest.tool ===
                              "generate_image" ? (
                              <ImageIcon className="h-4 w-4" />
                            ) : (
                              <Bot className="h-4 w-4" />
                            )}

                            {message.toolRequest.title}
                          </div>

                          <p className="mb-3 text-xs text-white/65">
                            {message.toolRequest.description}
                          </p>

                          <div className="grid grid-cols-2 gap-2">
                            <Button
                              type="button"
                              size="sm"
                              onClick={() => approveTool(message.toolRequest!)}
                              className="bg-emerald-600 text-white hover:bg-emerald-500"
                            >
                              <CheckCircle2 className="mr-1 h-3.5 w-3.5" />
                              Approve
                            </Button>

                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              onClick={() => rejectTool(message.toolRequest!)}
                              className="border-white/10 bg-white/5 text-white hover:bg-white/10"
                            >
                              <XCircle className="mr-1 h-3.5 w-3.5" />
                              Cancel
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {isLoading && (
                <div className="flex justify-start">
                  <div className="flex items-center gap-2 rounded-2xl border border-white/10 bg-white/[0.06] px-4 py-3 text-sm text-white/65">
                    <Loader2 className="h-4 w-4 animate-spin text-fuchsia-300" />
                    Assistant is thinking...
                  </div>
                </div>
              )}
            </div>

            <div className="border-t border-white/10 p-4">
              <div className="rounded-2xl border border-white/10 bg-black/40 p-2">
                <Textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={languageMode === "fr" ? "Écris en français, tunisien ou Arabizi..." : "Write in English, Tunisian Arabic or Arabizi..."}
                  className="min-h-[72px] resize-none border-0 bg-transparent text-white placeholder:text-white/35 focus-visible:ring-0"
                  disabled={isLoading}
                />

                {(listening || speechError) && (
                  <div className="px-2 pb-2 text-xs">
                    {listening && (
                      <span className="text-fuchsia-300">
                        🎤 Listening... speak now
                      </span>
                    )}
                    {speechError && (
                      <span className="text-red-400">
                        Voice error: {speechError}
                      </span>
                    )}
                  </div>
                )}

                <div className="mt-2 flex flex-col gap-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 text-xs text-white/40">
                      <MessageCircle className="h-3.5 w-3.5 shrink-0" />
                      <span className="leading-tight">
                        Permission required before actions
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <select
                        value={modelMode}
                        onChange={(e) => setModelMode(e.target.value as ModelMode)}
                        className="h-10 shrink-0 rounded-xl border border-white/10 bg-black/70 px-2 text-xs text-white outline-none"
                        title="Local AI model"
                      >
                        <option value="auto">AI Auto</option>
                        <option value="fast">Fast</option>
                        <option value="advanced">Advanced</option>
                      </select>

                      <select
                        value={languageMode}
                        onChange={(e) =>
                          handleLanguageChange(e.target.value as LanguageMode)
                        }
                        className="h-10 shrink-0 rounded-xl border border-white/10 bg-black/70 px-2 text-xs text-white outline-none"
                        title="Assistant language"
                      >
                        <option value="en">EN</option>
                        <option value="fr">FR</option>
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-6 gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setAudienceMirrorOpen(true)}
                      disabled={isLoading}
                      className="h-11 rounded-xl border-white/10 bg-white/5 p-0 text-white hover:bg-white/10"
                      title="Audience Mirror"
                    >
                      <Users className="h-4 w-4" />
                    </Button>

                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setBrandStudioOpen(true)}
                      disabled={isLoading}
                      className="h-11 rounded-xl border-white/10 bg-white/5 p-0 text-white hover:bg-white/10"
                      title="Launch Pack - Brand Studio"
                    >
                      <Briefcase className="h-4 w-4" />
                    </Button>

                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setDirectorOpen(true)}
                      disabled={isLoading}
                      className="h-11 rounded-xl border-white/10 bg-white/5 p-0 text-white hover:bg-white/10"
                      title="Director Mode + Prompt Doctor"
                    >
                      <Clapperboard className="h-4 w-4" />
                    </Button>

                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setImageCheckOpen(true)}
                      disabled={isLoading}
                      className="h-11 rounded-xl border-white/10 bg-white/5 p-0 text-white hover:bg-white/10"
                      title="Neural Camera Analysis"
                    >
                      <Camera className="h-4 w-4" />
                    </Button>

                    <Button
                      type="button"
                      variant="outline"
                      onClick={
                        listening
                          ? stopListening
                          : requestMicrophonePermission
                      }
                      disabled={!supported || isLoading}
                      className={`h-11 rounded-xl border-white/10 bg-white/5 p-0 text-white hover:bg-white/10 ${
                        listening ? "border-red-400/40 text-red-300" : ""
                      }`}
                      title="Microphone input (EN / FR only)"
                    >
                      {listening ? (
                        <MicOff className="h-4 w-4" />
                      ) : (
                        <Mic className="h-4 w-4" />
                      )}
                    </Button>

                    <Button
                      type="button"
                      onClick={sendMessage}
                      disabled={isLoading || !input.trim()}
                      className="h-11 rounded-xl bg-fuchsia-600 p-0 text-white shadow-[0_0_24px_rgba(217,70,239,0.28)] hover:bg-fuchsia-500"
                      title="Send"
                    >
                      {isLoading ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Send className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                </div>
              </div>

              <p className="mt-3 text-center text-[11px] text-white/35">
                Assistant answers with EN / FR voice only, supports Auto / Fast / Advanced local AI models, uses Director Mode + Prompt Doctor, Neural Camera Analysis, and asks permission
                before actions.
              </p>
            </div>
          </div>
        </div>
      )}

      <ImageCheckModal
        open={imageCheckOpen}
        lang={languageMode}
        apiBase={ASSISTANT_API_BASE}
        onClose={() => setImageCheckOpen(false)}
        onUseSuggestion={handleImageCheckSuggestion}
        onSendPromptToInput={(prompt, result) => {
          setImageCheckOpen(false);
          if (result) setPendingImageCheckReference(buildImageCheckReferenceArgs(result));
          setInput(prompt);
        }}
      />

      <DirectorModeModal
        open={directorOpen}
        lang={languageMode}
        apiBase={ASSISTANT_API_BASE}
        onClose={() => setDirectorOpen(false)}
        onUseSuggestion={handleDirectorSuggestion}
        onSendPromptToInput={(prompt) => {
          setDirectorOpen(false);
          setInput(prompt);
        }}
      />


      <AudienceMirrorModal
        open={audienceMirrorOpen}
        lang={languageMode}
        apiBase={ASSISTANT_API_BASE}
        initialContent={input}
        initialTitle="Project content"
        onClose={() => setAudienceMirrorOpen(false)}
        onUseSuggestion={handleAudienceSuggestion}
        onSendPromptToInput={(prompt) => {
          setAudienceMirrorOpen(false);
          setInput(prompt);
        }}
      />

      <BrandStudioModal
        open={brandStudioOpen}
        lang={languageMode}
        apiBase={ASSISTANT_API_BASE}
        onClose={() => setBrandStudioOpen(false)}
        onUseSuggestion={handleBrandSuggestion}
        onSendPromptToInput={(prompt) => {
          setBrandStudioOpen(false);
          setInput(prompt);
        }}
      />
    </>
  );
}
