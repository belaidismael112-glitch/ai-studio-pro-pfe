"use client";

import { normalizeBackendRoot } from "@/lib/url-config";

import { ReactNode, useEffect, useMemo, useRef, useState } from "react";
import {
  Camera,
  Upload,
  X,
  Loader2,
  ImageIcon,
  Video,
  RefreshCw,
  Copy,
  Send,
  SlidersHorizontal,
  Sparkles,
  Brain,
  Radar,
  History,
  Settings,
  Cpu,
  ScanFace,
  SunMedium,
  Focus,
  ShieldCheck,
  Wifi,
  Aperture,
  BadgeCheck,
  Activity,
  Layers3,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { withAuthHeaders } from "@/lib/auth-fetch";

export type MagicLensAction = "generate_image" | "make_prompt";

export type MagicLensSuggestion = {
  action: MagicLensAction;
  title: string;
  prompt: string;
  negative_prompt?: string | null;
  width?: number | null;
  height?: number | null;
  duration?: number | null;
  description?: string | null;
  workflow_stage?: "identity_expression_board" | "pose_style_direction" | "subject_lock_prompt" | null;
  generation_mode?: "person_identity" | "auto" | null;
  strength?: number | null;
  layout?: string | null;
};

export type FaceAlignmentMasterStatus = {
  active?: boolean | null;
  status?: string | null;
  vendor_present?: boolean | null;
  vendor_path?: string | null;
  source?: string | null;
  import_ok?: boolean | null;
  version?: string | null;
  device?: string | null;
  detector?: string | null;
  landmark_count?: number | null;
  used_for_pose?: boolean | null;
  error?: string | null;
  install_hint?: string | null;
};

export type LandmarkAnalysis = {
  landmark_count?: number | null;
  yaw_label?: string | null;
  eye_line?: string | null;
  roll_degrees?: number | null;
  eye_distance_percent_of_landmark_face_width?: number | null;
  mouth_width_percent_of_landmark_face_width?: number | null;
  prompt_features?: string[] | null;
};

export type RealFaceAnalysis = {
  face_detected?: boolean | null;
  face_count?: number | null;
  detector?: string | null;
  face_alignment_master?: FaceAlignmentMasterStatus | null;
  landmark_analysis?: LandmarkAnalysis | null;
  primary_face_bbox_label?: string | null;
  alignment_score?: number | null;
  identity_reliability_score?: number | null;
  generation_confidence_score?: number | null;
  multi_face_ambiguity?: string | null;
  face_position?: {
    coverage_percent?: number | null;
    center_offset_x_percent?: number | null;
    center_offset_y_percent?: number | null;
    center_distance_percent?: number | null;
    framing_label?: string | null;
  } | null;
  pose_estimate?: {
    yaw_label?: string | null;
    pitch_label?: string | null;
    roll_degrees?: number | null;
    eye_line?: string | null;
    eye_distance_percent_of_face_width?: number | null;
  } | null;
  eye_analysis?: {
    detected_count?: number | null;
    eyes?: unknown[] | null;
  } | null;
  mouth_analysis?: {
    detected?: boolean | null;
    label?: string | null;
  } | null;
  face_region_quality?: {
    lighting_label?: string | null;
    temperature_label?: string | null;
    contrast_label?: string | null;
    sharpness_laplacian?: number | null;
    sharpness_label?: string | null;
  } | null;
  professional_notes?: string[] | null;
  features_for_prompt?: string[] | null;
};

export type ProductionAssessment = {
  grade?: string | null;
  readiness?: string | null;
  headline?: string | null;
  summary?: string | null;
  alignment_score?: number | null;
  identity_reliability_score?: number | null;
  generation_confidence_score?: number | null;
  multi_face_ambiguity?: string | null;
  strengths?: string[] | null;
  risks?: string[] | null;
  recommendations?: string[] | null;
  requires_face_crop?: boolean | null;
  hard_block_generation?: boolean | null;
  warning_level?: string | null;
  can_generate?: boolean | null;
  can_generate_confidently?: boolean | null;
};

export type SubjectAnalysis = {
  subject_type?: string | null;
  preservation_mode?: string | null;
  primary_subject_detected?: boolean | null;
  subject_count?: number | null;
  primary_subject_bbox_label?: string | null;
  primary_subject_coverage_percent?: number | null;
  reference_quality_score?: number | null;
  subject_preservation_score?: number | null;
  shape_clarity_score?: number | null;
  color_fidelity_readiness?: number | null;
  sharpness_score?: number | null;
  hard_block_generation?: boolean | null;
  can_generate?: boolean | null;
  can_generate_confidently?: boolean | null;
  warning_level?: string | null;
  risks?: string[] | null;
  recommendations?: string[] | null;
  primary_subject_crop_url?: string | null;
  quality_flags?: Record<string, any> | null;
  background_analysis?: Record<string, any> | null;
  small_object_analysis?: Record<string, any> | null;
  product_analysis?: Record<string, any> | null;
  full_body_analysis?: Record<string, any> | null;
  capability_matrix?: Record<string, any> | null;
  semantic_vision?: Record<string, any> | null;
  semantic_prompt_focus?: string | null;
};

export type FaceAlignmentProfile = {
  image_size?: string | null;
  source_image_size?: string | null;
  output_size?: string | null;
  orientation?: string | null;
  framing?: string | null;
  lighting?: string | null;
  color_temperature?: string | null;
  contrast?: string | null;
  sharpness_note?: string | null;
  likely_subject_region?: string | null;
  alignment_notes?: string[] | null;
  user_selected_settings?: Record<string, string> | null;
  real_face_analysis?: RealFaceAnalysis | null;
  production_assessment?: ProductionAssessment | null;
  subject_analysis?: SubjectAnalysis | null;
  generation_gate?: {
    allowed?: boolean | null;
    status?: string | null;
    subject_type?: string | null;
    reference_quality_score?: number | null;
    subject_preservation_score?: number | null;
    subject_coverage_percent?: number | null;
    required_action?: string | null;
  } | null;
  primary_subject_crop_url?: string | null;
  primary_face_crop_url?: string | null;
  readable_summary_en?: string | null;
  readable_summary_fr?: string | null;
  detected_face_prompt_en?: string | null;
  detected_face_prompt_fr?: string | null;
  error?: string | null;
};


export type PersonaWorkflowStage = {
  order: number;
  key: "identity_expression_board" | "pose_style_direction";
  title: string;
  description: string;
  output_intent: string;
  prompt: string;
  width: number;
  height: number;
  generation_mode: "person_identity";
  strength: number;
  requires_identity_review: boolean;
};

export type PersonaWorkflow = {
  enabled: boolean;
  status: "ready" | "blocked";
  title: string;
  summary: string;
  identity_source: string;
  stages: PersonaWorkflowStage[];
  delivery_note: string;
};

export type MagicLensAnalyzeResult = {
  success: boolean;
  provider: string;
  image_url?: string | null;
  description: string;
  detected_language: string;
  suggestions: MagicLensSuggestion[];
  error?: string | null;
  face_profile?: FaceAlignmentProfile | null;
  face_prompt?: string | null;
  persona_workflow?: PersonaWorkflow | null;
  code_version?: string | null;
};

type MagicLensModalProps = {
  open: boolean;
  lang: "auto" | "en" | "fr";
  apiBase?: string;
  onClose: () => void;
  onUseSuggestion: (suggestion: MagicLensSuggestion, result: MagicLensAnalyzeResult) => void;
  onSendPromptToInput?: (prompt: string, result?: MagicLensAnalyzeResult) => void;
};

type FaceSettingKey = "size" | "orientation" | "lighting" | "temperature" | "contrast";

type FaceSettings = Record<FaceSettingKey, string>;

type LiveFaceBox = {
  leftPct: number;
  topPct: number;
  widthPct: number;
  heightPct: number;
  detected: boolean;
};

type CameraDeviceOption = {
  deviceId: string;
  label: string;
  isDji: boolean;
};

type SettingOption = {
  value: string;
  label: string;
};

const DEFAULT_API_BASE = normalizeBackendRoot(
  process.env.NEXT_PUBLIC_ASSISTANT_API_URL || process.env.NEXT_PUBLIC_BACKEND_URL
);

const DEFAULT_FACE_SETTINGS: FaceSettings = {
  size: "1280x720",
  orientation: "landscape",
  lighting: "balanced",
  temperature: "neutral",
  contrast: "medium contrast",
};

const FACE_SETTING_OPTIONS: Record<FaceSettingKey, SettingOption[]> = {
  size: [
    { value: "1280x720", label: "1280 × 720 · HD landscape" },
    { value: "1920x1080", label: "1920 × 1080 · Full HD" },
    { value: "1536x1024", label: "1536 × 1024 · wide editorial" },
    { value: "1024x1024", label: "1024 × 1024 · square" },
    { value: "1024x1536", label: "1024 × 1536 · portrait" },
    { value: "720x1280", label: "720 × 1280 · vertical story" },
  ],
  orientation: [
    { value: "landscape", label: "Landscape" },
    { value: "portrait", label: "Portrait" },
    { value: "square/near-square", label: "Square / near-square" },
  ],
  lighting: [
    { value: "balanced", label: "Balanced" },
    { value: "studio soft", label: "Studio soft" },
    { value: "cinematic", label: "Cinematic" },
    { value: "low-key / dark", label: "Low-key / dark" },
    { value: "bright / high-key", label: "Bright / high-key" },
  ],
  temperature: [
    { value: "neutral", label: "Neutral" },
    { value: "warm", label: "Warm" },
    { value: "cool", label: "Cool" },
  ],
  contrast: [
    { value: "medium contrast", label: "Medium contrast" },
    { value: "soft contrast", label: "Soft contrast" },
    { value: "strong contrast", label: "Strong contrast" },
  ],
};

function isArabicLang(_lang: string) {
  return false;
}

function uiText(lang: string) {
  if (lang === "fr") {
    return {
      title: "Neural Camera Analysis",
      subtitle: "Visage → persona → expressions → poses et styles",
      startCamera: "Ouvrir caméra",
      capture: "Capturer",
      retake: "Reprendre",
      upload: "Importer",
      analyze: "Analyser",
      analyzing: "Analyse en cours...",
      close: "Fermer",
      noCamera: "Caméra indisponible. Utilise l'import image.",
      hint: "Indice optionnel: chien blanc, produit, poster, style...",
      result: "Analyse lisible",
      personaWorkflow: "Workflow persona en deux étapes",
      personaActions: "Actions persona",
      stageLabel: "Étape",
      resultEmpty: "Importe une image, choisis les réglages, puis lance l'analyse. Le prompt sera grand, clair et prêt pour Ollama/ComfyUI.",
      faceDetails: "Réglages face-alignment",
      facePrompt: "Prompt visage précis",
      settingsTitle: "Réglages choisis par l'utilisateur",
      settingsSubtitle: "Ces valeurs sont envoyées au backend. Elles ne sont plus bloquées en valeurs par défaut.",
      size: "Taille",
      orientation: "Orientation",
      lighting: "Lumière",
      temperature: "Température",
      contrast: "Contraste",
      previewReady: "Image prête",
      previewIdle: "Importe ou capture une référence",
      previewHint: "L'écran noir est remplacé par un visuel neuron/radar animé.",
      use: "Utiliser",
      promptOnly: "Mettre dans le prompt",
      sourceSize: "Source",
      realFaceAnalysis: "Analyse réelle du visage",
      faceDetected: "Visage détecté",
      detector: "Détecteur",
      faces: "Visages",
      coverage: "Couverture",
      centerOffset: "Décalage centre",
      pose: "Pose",
      eyeLine: "Ligne yeux",
      eyes: "Yeux",
      mouth: "Bouche",
      sharpness: "Netteté",
      alignmentScore: "Score alignement",
      professionalNotes: "Notes pro",
      productionVerdict: "Verdict production",
      strengths: "Points forts",
      risks: "Risques",
      recommendations: "Recommandations",
      generateReadiness: "Prêt génération",
      faceAlignmentMaster: "face-alignment-master",
      engineStatus: "Statut moteur",
      landmarks: "Landmarks",
      usedForPose: "Utilisé pour pose",
    };
  }

  return {
    title: "Neural Camera Analysis",
    subtitle: "Face → persona → expressions → poses and styles",
    startCamera: "Open camera",
    capture: "Capture",
    retake: "Retake",
    upload: "Upload",
    analyze: "Analyze",
    analyzing: "Analyzing...",
    close: "Close",
    noCamera: "Camera unavailable. Use image upload.",
    hint: "Optional hint: white dog, product, poster, style...",
    result: "Readable analysis",
    personaWorkflow: "Two-stage persona workflow",
    personaActions: "Persona actions",
    stageLabel: "Step",
    resultEmpty: "Upload an image, choose the settings, then analyze. The prompt will stay large, clear, and ready for Ollama/ComfyUI.",
    faceDetails: "Face-alignment settings",
    facePrompt: "Precise face prompt",
    settingsTitle: "User-selected settings",
    settingsSubtitle: "These values are sent to the backend. They are no longer locked as hidden defaults.",
    size: "Size",
    orientation: "Orientation",
    lighting: "Lighting",
    temperature: "Temperature",
    contrast: "Contrast",
    previewReady: "Image ready",
    previewIdle: "Upload or capture a reference",
    previewHint: "The black screen is replaced with an animated neuron/radar visual.",
    use: "Use",
    promptOnly: "Put in prompt",
    sourceSize: "Source",
    realFaceAnalysis: "Real face analysis",
    faceDetected: "Face detected",
    detector: "Detector",
    faces: "Faces",
    coverage: "Coverage",
    centerOffset: "Center offset",
    pose: "Pose",
    eyeLine: "Eye line",
    eyes: "Eyes",
    mouth: "Mouth",
    sharpness: "Sharpness",
    alignmentScore: "Alignment score",
    professionalNotes: "Pro notes",
    productionVerdict: "Production verdict",
    strengths: "Strengths",
    risks: "Risks",
    recommendations: "Recommendations",
    generateReadiness: "Generation readiness",
    faceAlignmentMaster: "face-alignment-master",
    engineStatus: "Engine status",
    landmarks: "Landmarks",
    usedForPose: "Used for pose",
  };
}

function settingLabel(key: FaceSettingKey, value: string) {
  return FACE_SETTING_OPTIONS[key].find((option) => option.value === value)?.label || value;
}

function detectDjiCameraLabel(label: string) {
  const lowered = label.toLowerCase();
  return lowered.includes("dji") || lowered.includes("osmo") || lowered.includes("pocket 3");
}

function uniqueStrings(items: Array<string | null | undefined>) {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const item of items) {
    const text = String(item || "").trim();
    if (!text) continue;
    const key = text.toLowerCase().replace(/\s+/g, " ");
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(text);
  }
  return result;
}

function NeuralRadianceBackdrop() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-[32px]">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_22%_14%,rgba(34,211,238,0.24),transparent_28%),radial-gradient(circle_at_76%_20%,rgba(217,70,239,0.22),transparent_30%),linear-gradient(135deg,rgba(2,6,23,0.98),rgba(15,23,42,0.94)_48%,rgba(6,11,22,0.98))]" />
      <div className="neuro-grid absolute inset-0 opacity-45" />
      <div className="neuro-orb neuro-orb-a" />
      <div className="neuro-orb neuro-orb-b" />
      <div className="neuro-ring neuro-ring-a" />
      <div className="neuro-ring neuro-ring-b" />
      <div className="neuro-beam neuro-beam-a" />
      <div className="neuro-beam neuro-beam-b" />
      <style jsx>{`
        .neuro-grid {
          background-image:
            linear-gradient(rgba(103, 232, 249, 0.12) 1px, transparent 1px),
            linear-gradient(90deg, rgba(217, 70, 239, 0.12) 1px, transparent 1px);
          background-size: 42px 42px;
          animation: neuro-drift 18s linear infinite;
          mask-image: radial-gradient(circle at 46% 42%, black 0%, transparent 70%);
        }
        .neuro-orb {
          position: absolute;
          width: 420px;
          height: 420px;
          border-radius: 9999px;
          filter: blur(18px);
          opacity: 0.36;
          background: conic-gradient(from 0deg, rgba(34,211,238,0), rgba(34,211,238,0.74), rgba(217,70,239,0.65), rgba(34,211,238,0));
          animation: neuro-spin 18s linear infinite;
        }
        .neuro-orb-a { left: -130px; top: -150px; }
        .neuro-orb-b { right: -160px; bottom: -190px; animation-duration: 24s; animation-direction: reverse; }
        .neuro-ring {
          position: absolute;
          border-radius: 9999px;
          border: 1px solid rgba(125, 249, 255, 0.22);
          box-shadow: 0 0 34px rgba(34, 211, 238, 0.16), inset 0 0 34px rgba(217,70,239,0.12);
          animation: neuro-pulse 4.8s ease-in-out infinite;
        }
        .neuro-ring-a { width: 360px; height: 360px; left: 13%; top: 21%; }
        .neuro-ring-b { width: 520px; height: 520px; right: 4%; top: 8%; animation-delay: 1.4s; }
        .neuro-beam {
          position: absolute;
          height: 2px;
          width: 60%;
          transform-origin: left center;
          background: linear-gradient(90deg, transparent, rgba(103,232,249,0.76), rgba(217,70,239,0.46), transparent);
          filter: blur(0.4px);
          animation: neuro-sweep 5.5s ease-in-out infinite;
        }
        .neuro-beam-a { left: 12%; top: 39%; transform: rotate(17deg); }
        .neuro-beam-b { right: 6%; bottom: 30%; transform: rotate(-16deg); animation-delay: 2.2s; }
        @keyframes neuro-drift {
          from { transform: translate3d(0, 0, 0); }
          to { transform: translate3d(42px, 42px, 0); }
        }
        @keyframes neuro-spin {
          to { transform: rotate(360deg); }
        }
        @keyframes neuro-pulse {
          0%, 100% { transform: scale(0.96); opacity: 0.22; }
          50% { transform: scale(1.07); opacity: 0.58; }
        }
        @keyframes neuro-sweep {
          0%, 100% { opacity: 0.18; clip-path: inset(0 85% 0 0); }
          50% { opacity: 0.82; clip-path: inset(0 0 0 0); }
        }
        @keyframes neuralWave {
          0% { background-position: 0% 50%; }
          100% { background-position: 100% 50%; }
        }
        @keyframes ultraFloatNode {
          0%, 100% { transform: translate3d(0, 0, 0) scale(0.78); opacity: .42; }
          30% { transform: translate3d(18px, -22px, 0) scale(1.15); opacity: .95; }
          60% { transform: translate3d(-16px, 12px, 0) scale(.95); opacity: .62; }
        }
        @keyframes ultraCubeSpin {
          0% { transform: rotateX(62deg) rotateY(0deg) rotateZ(18deg); }
          100% { transform: rotateX(62deg) rotateY(360deg) rotateZ(18deg); }
        }
        @keyframes ultraDataRain {
          0% { transform: translateY(-30%); opacity: 0; }
          18% { opacity: .65; }
          100% { transform: translateY(120%); opacity: 0; }
        }
        @keyframes ultraEnergyWave {
          0% { transform: translateX(-120%) skewX(-18deg); opacity: 0; }
          25% { opacity: .75; }
          100% { transform: translateX(120%) skewX(-18deg); opacity: 0; }
        }
      `}</style>
    </div>
  );
}


function HoloParticleField() {
  const particles = [
    [12, 18, 0, 7], [18, 72, 0.7, 9], [27, 26, 1.3, 8], [34, 64, 2.1, 10],
    [42, 16, 0.4, 11], [51, 78, 1.6, 8], [59, 22, 2.4, 9], [68, 68, 0.9, 12],
    [76, 28, 1.8, 8], [84, 58, 2.8, 10], [91, 20, 1.1, 9], [7, 52, 2.5, 11],
    [23, 47, 3.1, 10], [38, 36, 1.9, 12], [57, 48, 2.7, 9], [73, 42, 3.4, 11],
    [86, 80, 0.2, 10], [14, 84, 3.6, 12], [46, 92, 2.2, 9], [63, 8, 3.0, 11],
  ];

  return (
    <div className="absolute inset-0">
      {particles.map(([left, top, delay, duration], index) => (
        <span
          key={`ultra-node-${index}`}
          className="absolute h-1.5 w-1.5 rounded-full bg-cyan-200/90 shadow-[0_0_16px_rgba(103,232,249,0.9)]"
          style={{
            left: `${left}%`,
            top: `${top}%`,
            animation: `ultraFloatNode ${duration}s ease-in-out ${delay}s infinite`,
          }}
        />
      ))}
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full opacity-55">
        <g stroke="rgba(34,211,238,0.18)" strokeWidth="0.12">
          <path d="M12 18 L27 26 L42 16 L59 22 L76 28 L91 20" />
          <path d="M7 52 L23 47 L38 36 L57 48 L73 42 L84 58" />
          <path d="M18 72 L34 64 L51 78 L68 68 L86 80" />
          <path d="M23 47 L27 26 M38 36 L42 16 M57 48 L59 22 M73 42 L76 28" />
          <path d="M34 64 L38 36 M51 78 L57 48 M68 68 L73 42" />
        </g>
      </svg>
    </div>
  );
}

function HolographicCube3D() {
  return (
    <div className="absolute right-[7%] bottom-[18%] hidden h-28 w-28 lg:block" style={{ perspective: "700px" }}>
      <div className="relative h-full w-full" style={{ transformStyle: "preserve-3d", animation: "ultraCubeSpin 9s linear infinite" }}>
        <div className="absolute inset-0 border border-cyan-300/45 bg-cyan-300/5 shadow-[0_0_28px_rgba(34,211,238,0.18)]" style={{ transform: "translateZ(56px)" }} />
        <div className="absolute inset-0 border border-cyan-300/28 bg-cyan-300/5" style={{ transform: "rotateY(90deg) translateZ(56px)" }} />
        <div className="absolute inset-0 border border-cyan-300/28 bg-cyan-300/5" style={{ transform: "rotateY(-90deg) translateZ(56px)" }} />
        <div className="absolute inset-0 border border-cyan-300/28 bg-cyan-300/5" style={{ transform: "rotateX(90deg) translateZ(56px)" }} />
        <div className="absolute inset-0 border border-cyan-300/28 bg-cyan-300/5" style={{ transform: "rotateX(-90deg) translateZ(56px)" }} />
        <div className="absolute inset-0 border border-cyan-300/28 bg-cyan-300/5" style={{ transform: "rotateY(180deg) translateZ(56px)" }} />
      </div>
      <div className="absolute left-1/2 top-1/2 h-36 w-36 -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-300/10 shadow-[0_0_40px_rgba(34,211,238,0.16)]" />
    </div>
  );
}

function HolographicCameraOverlay({ faceBox }: { faceBox?: LiveFaceBox | null }) {
  const faceLockStyle = faceBox?.detected
    ? {
        left: `${faceBox.leftPct}%`,
        top: `${faceBox.topPct}%`,
        width: `${faceBox.widthPct}%`,
        height: `${faceBox.heightPct}%`,
      }
    : {
        left: "50%",
        top: "50%",
        width: "34%",
        height: "48%",
        transform: "translate(-50%, -50%)",
      };

  return (
    <>
      <style>{`
        @keyframes neuralScanBar {
          0% { transform: translateY(-180px); opacity: 0; }
          15% { opacity: 0.85; }
          50% { opacity: 1; }
          100% { transform: translateY(180px); opacity: 0; }
        }
        @keyframes neuralRotate {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @keyframes neuralPulseSoft {
          0%,100% { opacity: .42; transform: scale(.98); }
          50% { opacity: .9; transform: scale(1.02); }
        }
        @keyframes neuralBlink {
          0%,100% { opacity: .66; }
          50% { opacity: 1; }
        }
        @keyframes neuralWave {
          0% { background-position: 0% 50%; }
          100% { background-position: 100% 50%; }
        }
        @keyframes ultraFloatNode {
          0%, 100% { transform: translate3d(0, 0, 0) scale(0.78); opacity: .42; }
          30% { transform: translate3d(18px, -22px, 0) scale(1.15); opacity: .95; }
          60% { transform: translate3d(-16px, 12px, 0) scale(.95); opacity: .62; }
        }
        @keyframes ultraCubeSpin {
          0% { transform: rotateX(62deg) rotateY(0deg) rotateZ(18deg); }
          100% { transform: rotateX(62deg) rotateY(360deg) rotateZ(18deg); }
        }
        @keyframes ultraDataRain {
          0% { transform: translateY(-30%); opacity: 0; }
          18% { opacity: .65; }
          100% { transform: translateY(120%); opacity: 0; }
        }
        @keyframes ultraEnergyWave {
          0% { transform: translateX(-120%) skewX(-18deg); opacity: 0; }
          25% { opacity: .75; }
          100% { transform: translateX(120%) skewX(-18deg); opacity: 0; }
        }
        @keyframes ultraOrbit {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
      <div className="pointer-events-none absolute inset-0 z-20 overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_40%,rgba(14,165,233,0.12),transparent_20%),linear-gradient(180deg,rgba(2,6,23,0.08),rgba(2,6,23,0.46))]" />
        <div className="absolute inset-0 bg-[linear-gradient(rgba(34,211,238,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(34,211,238,0.05)_1px,transparent_1px)] bg-[size:38px_38px] opacity-40" />
        <HoloParticleField />
        <HolographicCube3D />

        <div
          className="absolute rounded-[30px] border border-cyan-200/70 bg-cyan-300/[0.03] shadow-[0_0_36px_rgba(34,211,238,0.24),inset_0_0_28px_rgba(34,211,238,0.08)] transition-all duration-300"
          style={faceLockStyle}
        >
          <div className="absolute -left-3 -top-3 h-12 w-12 border-l-2 border-t-2 border-cyan-200 shadow-[0_0_14px_rgba(34,211,238,0.7)]" />
          <div className="absolute -right-3 -top-3 h-12 w-12 border-r-2 border-t-2 border-cyan-200 shadow-[0_0_14px_rgba(34,211,238,0.7)]" />
          <div className="absolute -bottom-3 -left-3 h-12 w-12 border-b-2 border-l-2 border-cyan-200 shadow-[0_0_14px_rgba(34,211,238,0.7)]" />
          <div className="absolute -bottom-3 -right-3 h-12 w-12 border-b-2 border-r-2 border-cyan-200 shadow-[0_0_14px_rgba(34,211,238,0.7)]" />
          <div className="absolute left-1/2 top-1/2 h-[112%] w-[112%] -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-300/20" style={{ animation: 'ultraOrbit 6s linear infinite' }} />
          <div className="absolute left-1/2 top-1/2 h-[128%] w-[128%] -translate-x-1/2 -translate-y-1/2 rounded-full border border-fuchsia-300/12" style={{ animation: 'ultraOrbit 9s linear infinite reverse' }} />
          <div className="absolute left-3 top-3 rounded-full border border-cyan-300/20 bg-slate-950/70 px-3 py-1.5 text-[10px] font-black uppercase tracking-[0.22em] text-cyan-50 backdrop-blur-xl">
            {faceBox?.detected ? "Real face lock" : "Center guide"}
          </div>
        </div>

        <div className="absolute left-0 top-1/3 h-24 w-full bg-gradient-to-r from-transparent via-cyan-300/18 to-transparent blur-sm" style={{ animation: 'ultraEnergyWave 4.2s ease-in-out infinite' }} />
        <div className="absolute right-[22%] top-0 h-full w-20 overflow-hidden opacity-35">
          {["0101", "FACE", "DEPTH", "68PT", "LOCK", "POSE"].map((item, index) => (
            <div key={item} className="absolute text-[10px] font-black tracking-[0.26em] text-cyan-200/70" style={{ left: `${index * 13}%`, animation: `ultraDataRain ${6 + index}s linear ${index * 0.55}s infinite` }}>
              {item}<br />{item}<br />{item}<br />{item}
            </div>
          ))}
        </div>
        <div className="absolute inset-x-0 bottom-0 h-28 bg-[linear-gradient(180deg,transparent,rgba(14,165,233,0.14))]" />

        <div className="absolute left-4 top-4 flex items-center gap-3 rounded-2xl border border-cyan-300/20 bg-slate-950/62 px-4 py-2.5 backdrop-blur-xl">
          <span className="inline-flex h-3 w-3 rounded-full bg-emerald-300 shadow-[0_0_18px_rgba(110,231,183,0.95)]" style={{ animation: 'neuralBlink 1.8s ease-in-out infinite' }} />
          <span className="text-sm font-black uppercase tracking-[0.24em] text-white">Live</span>
          <span className="text-sm font-semibold text-cyan-100/80">Camera stream</span>
        </div>

        <div className="absolute right-5 top-5 w-[190px] rounded-2xl border border-cyan-300/20 bg-slate-950/56 p-3 backdrop-blur-xl">
          <div className="mb-2 text-[11px] font-black uppercase tracking-[0.24em] text-cyan-100/80">Live preview status</div>
          <div className="space-y-2">
            <AnalyzeItem label="Face lock" value={faceBox?.detected ? "Detected" : "Guide"} />
            <AnalyzeItem label="Landmarks" value={faceBox?.detected ? "Await backend" : "After analyze"} />
            <AnalyzeItem label="Depth HUD" value="Visual" />
            <AnalyzeItem label="Focus" value="Measured later" />
            <AnalyzeItem label="Identity score" value="After analyze" />
          </div>
        </div>

        <div className="absolute left-4 top-1/2 flex w-[110px] -translate-y-1/2 flex-col gap-4">
          <div className="rounded-[24px] border border-cyan-300/20 bg-slate-950/56 p-3 backdrop-blur-xl">
            <div className="mb-2 text-[10px] font-black uppercase tracking-[0.22em] text-cyan-100/75">Face mesh</div>
            <div className="relative h-28 rounded-2xl border border-cyan-300/12 bg-[radial-gradient(circle_at_50%_40%,rgba(34,211,238,0.15),transparent_40%)]">
              <svg viewBox="0 0 90 120" className="absolute inset-3 h-[calc(100%-24px)] w-[calc(100%-24px)] opacity-80">
                <g fill="none" stroke="rgba(56,189,248,0.82)" strokeWidth="0.6">
                  <ellipse cx="45" cy="46" rx="24" ry="31" />
                  <path d="M22 34 C30 28 36 25 45 24 C54 25 60 28 68 34" />
                  <path d="M28 49 C32 44 37 42 45 42 C53 42 58 44 62 49" />
                  <path d="M33 77 C38 82 42 84 45 84 C48 84 52 82 57 77" />
                  <path d="M45 32 L45 74" />
                  <path d="M24 58 H66" />
                  <path d="M25 26 L65 26 M22 90 L68 90" />
                </g>
                <g fill="rgba(165,243,252,0.92)">
                  <circle cx="25" cy="26" r="1.2" /><circle cx="65" cy="26" r="1.2" />
                  <circle cx="45" cy="24" r="1.4" /><circle cx="45" cy="84" r="1.2" />
                  <circle cx="33" cy="47" r="1.2" /><circle cx="57" cy="47" r="1.2" />
                  <circle cx="45" cy="58" r="1.1" />
                </g>
              </svg>
            </div>
          </div>
          <div className="rounded-[24px] border border-cyan-300/20 bg-slate-950/56 p-3 backdrop-blur-xl">
            <div className="mb-2 text-[10px] font-black uppercase tracking-[0.22em] text-cyan-100/75">Depth map</div>
            <div className="relative h-28 rounded-2xl border border-cyan-300/12 bg-[radial-gradient(circle_at_50%_40%,rgba(34,211,238,0.15),transparent_40%)]">
              <div className="absolute bottom-3 left-3 top-3 w-[4px] rounded-full bg-[linear-gradient(180deg,rgba(34,211,238,1),rgba(56,189,248,.2))] shadow-[0_0_18px_rgba(34,211,238,0.8)]" />
              <svg viewBox="0 0 90 120" className="absolute inset-3 h-[calc(100%-24px)] w-[calc(100%-24px)] opacity-70">
                <g fill="rgba(56,189,248,0.85)">
                  <circle cx="45" cy="22" r="1.2" /><circle cx="36" cy="30" r="1.2" /><circle cx="54" cy="30" r="1.2" /><circle cx="28" cy="42" r="1.2" /><circle cx="62" cy="42" r="1.2" />
                  <circle cx="24" cy="58" r="1.2" /><circle cx="66" cy="58" r="1.2" /><circle cx="29" cy="74" r="1.2" /><circle cx="61" cy="74" r="1.2" /><circle cx="45" cy="88" r="1.2" />
                </g>
              </svg>
              <div className="absolute bottom-2 right-2 text-[10px] font-bold text-white/68">Near</div>
              <div className="absolute top-2 right-2 text-[10px] font-bold text-white/50">Far</div>
            </div>
          </div>
        </div>

        <div className="absolute left-1/2 top-1/2 h-[76%] w-[58%] -translate-x-1/2 -translate-y-1/2">
          <div className="absolute inset-0 rounded-full border border-cyan-300/20" style={{ animation: 'neuralPulseSoft 3.8s ease-in-out infinite' }} />
          <div className="absolute inset-[9%] rounded-full border border-cyan-300/55 shadow-[0_0_70px_rgba(34,211,238,0.18)]" />
          <div className="absolute inset-[18%] rounded-full border border-cyan-300/35" />
          <div className="absolute inset-[27%] rounded-full border border-cyan-300/18" />
          <div className="absolute left-[10%] top-[10%] h-[80%] w-[80%] rounded-full border border-cyan-300/15" style={{ animation: 'neuralRotate 18s linear infinite' }} />
          <div className="absolute left-[16%] top-[16%] h-[68%] w-[68%] rounded-full border border-cyan-300/10" style={{ animation: 'neuralRotate 14s linear infinite reverse' }} />
          <div className="absolute left-1/2 top-1/2 h-[2px] w-[80%] -translate-x-1/2 -translate-y-1/2 bg-gradient-to-r from-transparent via-cyan-300 to-transparent shadow-[0_0_22px_rgba(34,211,238,0.82)]" style={{ animation: 'neuralScanBar 2.8s linear infinite' }} />
          <div className="absolute left-1/2 top-1/2 h-[66%] w-[44%] -translate-x-1/2 -translate-y-1/2 rounded-[34px] border border-cyan-300/50">
            <div className="absolute -left-3 top-1/2 h-20 w-3 -translate-y-1/2 border-y border-l border-cyan-300/75" />
            <div className="absolute -right-3 top-1/2 h-20 w-3 -translate-y-1/2 border-y border-r border-cyan-300/75" />
            <div className="absolute left-1/2 top-4 h-[calc(100%-32px)] w-px -translate-x-1/2 bg-gradient-to-b from-transparent via-cyan-300/50 to-transparent" />
            <div className="absolute left-4 right-4 top-1/2 h-px -translate-y-1/2 bg-gradient-to-r from-transparent via-cyan-300/45 to-transparent" />
          </div>
          <svg viewBox="0 0 500 500" className="absolute inset-[18%] h-[64%] w-[64%] opacity-95">
            <g fill="rgba(165,243,252,0.96)">
              <circle cx="250" cy="86" r="3.2" /><circle cx="177" cy="125" r="2.6" /><circle cx="323" cy="125" r="2.6" />
              <circle cx="152" cy="192" r="2.6" /><circle cx="348" cy="192" r="2.6" />
              <circle cx="173" cy="278" r="2.6" /><circle cx="327" cy="278" r="2.6" />
              <circle cx="250" cy="224" r="2.6" /><circle cx="250" cy="320" r="2.6" />
              <circle cx="202" cy="196" r="2.4" /><circle cx="298" cy="196" r="2.4" /><circle cx="250" cy="270" r="2.2" />
              <circle cx="217" cy="337" r="2.4" /><circle cx="283" cy="337" r="2.4" />
            </g>
            <g stroke="rgba(125,211,252,0.86)" strokeWidth="2" fill="none">
              <path d="M250 86 C196 92 164 124 150 188 C144 221 144 268 161 305 C177 343 205 372 250 393 C295 372 323 343 339 305 C356 268 356 221 350 188 C336 124 304 92 250 86 Z" />
              <path d="M198 197 C210 185 226 178 250 178 C274 178 290 185 302 197" />
              <path d="M198 215 C212 227 226 233 250 233 C274 233 288 227 302 215" strokeWidth="1.3" opacity=".65" />
              <path d="M220 332 C231 345 241 350 250 350 C259 350 269 345 280 332" stroke="rgba(251,191,36,0.82)" />
              <path d="M250 178 L250 308" stroke="rgba(125,211,252,0.38)" strokeDasharray="7 8" />
              <path d="M172 248 H328" stroke="rgba(125,211,252,0.34)" strokeDasharray="7 8" />
              <circle cx="201" cy="198" r="24" /><circle cx="299" cy="198" r="24" />
            </g>
            <g stroke="rgba(56,189,248,0.34)" strokeWidth="1.2">
              <path d="M250 86 L177 125" /><path d="M250 86 L323 125" /><path d="M177 125 L152 192" /><path d="M323 125 L348 192" />
              <path d="M152 192 L173 278" /><path d="M348 192 L327 278" /><path d="M173 278 L217 337" /><path d="M327 278 L283 337" />
              <path d="M217 337 L250 393" /><path d="M283 337 L250 393" />
            </g>
          </svg>
        </div>

        <div className="absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-4 rounded-[28px] border border-cyan-300/20 bg-slate-950/66 px-6 py-3 backdrop-blur-xl">
          <Camera className="h-5 w-5 text-cyan-100/90" />
          <Video className="h-5 w-5 text-cyan-100/70" />
          <div className="grid h-16 w-16 place-items-center rounded-full border border-cyan-300/40 bg-cyan-400/12 shadow-[0_0_30px_rgba(34,211,238,0.24)]">
            <Brain className="h-7 w-7 text-cyan-100" />
          </div>
          <ImageIcon className="h-5 w-5 text-cyan-100/70" />
          <SunMedium className="h-5 w-5 text-cyan-100/70" />
        </div>

        <div className="absolute bottom-4 left-4 right-4 grid grid-cols-5 gap-3 text-white/88 max-md:hidden">
          {[
            ['Resolution', '1280 × 720'],
            ['Mode', faceBox?.detected ? 'Face lock' : 'Guide'],
            ['Tracking', faceBox?.detected ? 'Browser face' : 'Visual HUD'],
            ['Backend', 'Analyze required'],
            ['Connection', 'Stable'],
          ].map(([label, value], idx) => (
            <div key={label} className={`rounded-2xl border border-cyan-300/10 bg-slate-950/55 px-4 py-3 backdrop-blur-xl ${idx === 4 ? 'text-emerald-200' : ''}`}>
              <div className="text-[11px] font-black uppercase tracking-[0.18em] text-white/44">{label}</div>
              <div className="mt-1 text-sm font-bold">{value}</div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function NeuralPreviewPlaceholder({ title, body }: { title: string; body: string }) {
  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center overflow-hidden rounded-3xl bg-slate-950 text-center">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_42%,rgba(34,211,238,0.25),transparent_30%),radial-gradient(circle_at_38%_58%,rgba(217,70,239,0.18),transparent_32%)]" />
      <div className="absolute h-52 w-52 rounded-full border border-cyan-200/25 shadow-[0_0_60px_rgba(34,211,238,0.25)] animate-ping" />
      <div className="absolute h-72 w-72 rounded-full border border-fuchsia-200/15 shadow-[0_0_70px_rgba(217,70,239,0.18)]" />
      <div className="relative grid h-28 w-28 place-items-center rounded-[2rem] border border-white/15 bg-white/10 shadow-[0_0_45px_rgba(34,211,238,0.22)] backdrop-blur-xl">
        <Camera className="h-11 w-11 text-cyan-100" />
      </div>
      <div className="relative mt-6 max-w-sm px-5">
        <p className="text-base font-black tracking-wide text-white">{title}</p>
        <p className="mt-2 text-sm leading-6 text-cyan-50/82">{body}</p>
      </div>
    </div>
  );
}

function SettingSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: SettingOption[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="block rounded-2xl border border-white/10 bg-white/[0.07] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]">
      <span className="mb-2 block text-[11px] font-black uppercase tracking-[0.24em] text-cyan-100/80">
        {label}
      </span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2.5 text-sm font-semibold text-white outline-none transition focus:border-cyan-300/50 focus:ring-2 focus:ring-cyan-300/15"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function DetailRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-slate-950/45 px-3 py-2">
      <span className="text-xs font-black uppercase tracking-[0.18em] text-cyan-100/70">{label}</span>
      <span className="text-right text-sm font-bold text-white">{value || "-"}</span>
    </div>
  );
}


function displayValue(value: string | number | boolean | null | undefined, suffix = "") {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return `${value}${suffix}`;
}

function MetricTile({ label, value }: { label: string; value: string | number | boolean | null | undefined }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-3">
      <div className="text-[10px] font-black uppercase tracking-[0.22em] text-cyan-100/70">{label}</div>
      <div className="mt-1 text-sm font-black leading-6 text-white">{displayValue(value)}</div>
    </div>
  );
}


function CapabilityPill({ label, value }: { label: string; value?: any }) {
  const available = Boolean(value?.available ?? value?.detected ?? value);
  const confidence = value?.confidence ?? value?.small_object_confidence ?? null;
  const extra = value?.label || value?.source || value?.object_scale_label || null;
  return (
    <div className={available ? "rounded-2xl border border-emerald-300/18 bg-emerald-400/10 px-3 py-2" : "rounded-2xl border border-white/8 bg-white/[0.03] px-3 py-2"}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-black uppercase tracking-[0.16em] text-white/62">{label}</span>
        <span className={available ? "text-xs font-black text-emerald-200" : "text-xs font-black text-white/45"}>{available ? "Detected" : "No risk"}</span>
      </div>
      <div className="mt-1 text-sm font-bold text-white/88">{confidence !== null && confidence !== undefined ? `${confidence}/100` : extra || "—"}</div>
      {extra && <div className="mt-0.5 truncate text-[11px] font-semibold text-white/46">{extra}</div>}
    </div>
  );
}

function ProductionAssessmentCard({ assessment, labels }: { assessment: ProductionAssessment; labels: ReturnType<typeof uiText> }) {
  const strengths = assessment.strengths || [];
  const risks = assessment.risks || [];
  const recommendations = assessment.recommendations || [];
  const readinessTone = assessment.readiness === "production_ready" || assessment.readiness === "good_with_minor_risk"
    ? "border-emerald-200/25 bg-emerald-950/20"
    : assessment.readiness === "needs_improvement"
    ? "border-amber-200/25 bg-amber-950/20"
    : "border-rose-200/25 bg-rose-950/20";

  return (
    <div className={`rounded-3xl p-4 shadow-[0_0_40px_rgba(34,211,238,0.08)] ${readinessTone}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-black text-white">{labels.productionVerdict}</div>
          <div className="mt-1 text-lg font-black text-white">{assessment.headline || "-"}</div>
          {assessment.summary && <p className="mt-2 text-sm leading-6 text-white/82">{assessment.summary}</p>}
        </div>
        <div className="rounded-2xl border border-white/10 bg-slate-950/45 px-4 py-3 text-right">
          <div className="text-[10px] font-black uppercase tracking-[0.22em] text-cyan-100/70">Grade</div>
          <div className="mt-1 text-2xl font-black text-white">{assessment.grade || "-"}</div>
          <div className="mt-1 text-xs font-semibold text-white/70">{assessment.can_generate_confidently ? "High confidence" : assessment.can_generate ? "Usable with caution" : "Retake / fix"}</div>
        </div>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        <MetricTile label={labels.generateReadiness} value={assessment.readiness} />
        <MetricTile label={labels.productionVerdict} value={assessment.can_generate !== null && assessment.can_generate !== undefined ? (assessment.can_generate ? "Can generate" : "Retake recommended") : "-"} />
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
          <div className="mb-2 text-[11px] font-black uppercase tracking-[0.22em] text-emerald-100/70">{labels.strengths}</div>
          <ul className="space-y-1 text-sm leading-6 text-white/85">
            {strengths.length > 0 ? strengths.slice(0, 4).map((item, index) => <li key={`s-${index}`}>• {item}</li>) : <li>• -</li>}
          </ul>
        </div>
        <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
          <div className="mb-2 text-[11px] font-black uppercase tracking-[0.22em] text-amber-100/70">{labels.risks}</div>
          <ul className="space-y-1 text-sm leading-6 text-white/85">
            {risks.length > 0 ? risks.slice(0, 4).map((item, index) => <li key={`r-${index}`}>• {item}</li>) : <li>• -</li>}
          </ul>
        </div>
        <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
          <div className="mb-2 text-[11px] font-black uppercase tracking-[0.22em] text-cyan-100/70">{labels.recommendations}</div>
          <ul className="space-y-1 text-sm leading-6 text-white/85">
            {recommendations.length > 0 ? recommendations.slice(0, 4).map((item, index) => <li key={`c-${index}`}>• {item}</li>) : <li>• -</li>}
          </ul>
        </div>
      </div>
    </div>
  );
}

function FaceAlignmentMasterCard({ analysis, labels }: { analysis: RealFaceAnalysis; labels: ReturnType<typeof uiText> }) {
  const engine = analysis.face_alignment_master || {};
  const landmarks = analysis.landmark_analysis || {};
  const tone = engine.status === "landmarks_active" || engine.status === "active" || engine.status === "active_cached"
    ? "border-cyan-200/25 bg-cyan-950/25"
    : "border-amber-200/25 bg-amber-950/20";

  return (
    <div className={`rounded-3xl p-4 shadow-[0_0_38px_rgba(34,211,238,0.10)] ${tone}`}>
      <div className="mb-3 flex items-center gap-2 text-sm font-black text-cyan-50">
        <Sparkles className="h-4 w-4 text-cyan-200" />
        {labels.faceAlignmentMaster}
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <MetricTile label={labels.engineStatus} value={engine.status} />
        <MetricTile label={labels.landmarks} value={landmarks.landmark_count || engine.landmark_count || "-"} />
        <MetricTile label="Version" value={engine.version} />
        <MetricTile label="Device" value={engine.device} />
        <MetricTile label={labels.usedForPose} value={engine.used_for_pose} />
        <MetricTile label="Roll" value={landmarks.roll_degrees !== undefined && landmarks.roll_degrees !== null ? `${landmarks.roll_degrees}°` : "-"} />
        <MetricTile label="Yaw" value={landmarks.yaw_label} />
        <MetricTile label={labels.eyeLine} value={landmarks.eye_line} />
      </div>
      {engine.error && (
        <p className="mt-3 rounded-2xl border border-white/10 bg-slate-950/45 p-3 text-sm font-semibold leading-6 text-amber-50/90">
          {engine.error}
        </p>
      )}
      {engine.install_hint && (
        <p className="mt-2 rounded-2xl border border-white/10 bg-slate-950/45 p-3 text-sm font-semibold leading-6 text-cyan-50/86">
          {engine.install_hint}
        </p>
      )}
    </div>
  );
}

function RealFaceAnalysisCard({ analysis, labels }: { analysis: RealFaceAnalysis; labels: ReturnType<typeof uiText> }) {
  const position = analysis.face_position || {};
  const pose = analysis.pose_estimate || {};
  const eyes = analysis.eye_analysis || {};
  const mouth = analysis.mouth_analysis || {};
  const quality = analysis.face_region_quality || {};
  const notes = analysis.professional_notes || [];
  const centerOffset =
    position.center_offset_x_percent !== undefined || position.center_offset_y_percent !== undefined
      ? `x ${displayValue(position.center_offset_x_percent, "%")} / y ${displayValue(position.center_offset_y_percent, "%")}`
      : "-";
  const poseText = [pose.yaw_label, pose.pitch_label].filter(Boolean).join(" · ") || "-";
  const sharpnessText = quality.sharpness_label
    ? `${quality.sharpness_label}${quality.sharpness_laplacian ? ` · ${quality.sharpness_laplacian}` : ""}`
    : "-";

  return (
    <div className="rounded-3xl border border-emerald-200/20 bg-emerald-950/20 p-4 shadow-[0_0_38px_rgba(16,185,129,0.11)]">
      <div className="mb-3 flex items-center gap-2 text-sm font-black text-emerald-50">
        <Sparkles className="h-4 w-4 text-emerald-200" />
        {labels.realFaceAnalysis}
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <MetricTile label={labels.faceDetected} value={analysis.face_detected} />
        <MetricTile label={labels.faces} value={analysis.face_count} />
        <MetricTile label={labels.detector} value={analysis.detector} />
        <MetricTile label={labels.alignmentScore} value={analysis.alignment_score !== undefined && analysis.alignment_score !== null ? `${analysis.alignment_score}/100` : "-"} />
        <MetricTile label={labels.coverage} value={position.coverage_percent !== undefined && position.coverage_percent !== null ? `${position.coverage_percent}%` : "-"} />
        <MetricTile label={labels.centerOffset} value={centerOffset} />
        <MetricTile label={labels.pose} value={poseText} />
        <MetricTile label={labels.eyeLine} value={pose.roll_degrees !== undefined && pose.roll_degrees !== null ? `${pose.eye_line || "-"} · ${pose.roll_degrees}°` : pose.eye_line} />
        <MetricTile label={labels.eyes} value={eyes.detected_count} />
        <MetricTile label={labels.mouth} value={mouth.label} />
        <MetricTile label={labels.sharpness} value={sharpnessText} />
      </div>

      {position.framing_label && (
        <p className="mt-3 rounded-2xl border border-white/10 bg-slate-950/45 p-3 text-sm font-semibold leading-6 text-emerald-50/90">
          {position.framing_label}
        </p>
      )}

      {notes.length > 0 && (
        <div className="mt-3 rounded-2xl border border-white/10 bg-slate-950/45 p-3">
          <div className="mb-2 text-[11px] font-black uppercase tracking-[0.22em] text-emerald-100/70">{labels.professionalNotes}</div>
          <ul className="space-y-1 text-sm font-medium leading-6 text-white/86">
            {notes.slice(0, 4).map((note, index) => (
              <li key={`${note}-${index}`}>• {note}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function PromptCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-3xl border border-fuchsia-200/20 bg-fuchsia-950/25 p-4 shadow-[0_0_36px_rgba(217,70,239,0.10)]">
      <div className="mb-3 flex items-center gap-2 text-sm font-black text-fuchsia-50">
        <Sparkles className="h-4 w-4 text-fuchsia-200" />
        {title}
      </div>
      <div className="max-h-48 overflow-auto whitespace-pre-wrap rounded-2xl border border-white/10 bg-slate-950/70 p-4 text-sm leading-7 text-white/92">
        {children}
      </div>
    </div>
  );
}

function clampPercent(value?: number | null, fallback = 0) {
  const numeric = typeof value === "number" && Number.isFinite(value) ? value : fallback;
  return Math.max(0, Math.min(100, Math.round(numeric)));
}

function NeuralSideRail() {
  const items = [
    { icon: Camera, label: "Camera", status: "Live input" },
    { icon: Radar, label: "Analysis", status: "Backend score" },
    { icon: ScanFace, label: "Landmarks", status: "FAN 68-point" },
    { icon: ShieldCheck, label: "Identity", status: "Risk score" },
    { icon: Settings, label: "Settings", status: "User values" },
  ];

  return (
    <div className="hidden xl:block">
      <div className="rounded-[28px] border border-cyan-300/15 bg-slate-950/85 p-4 shadow-[0_0_44px_rgba(34,211,238,0.08)] backdrop-blur-xl">
        <div className="space-y-3">
          {items.map((item, index) => {
            const Icon = item.icon;
            return (
              <div
                key={item.label}
                className={`rounded-2xl border px-3 py-4 text-center transition ${
                  index === 0
                    ? "border-cyan-300/35 bg-cyan-400/14 text-cyan-100 shadow-[0_0_30px_rgba(34,211,238,0.14)]"
                    : "border-white/8 bg-white/[0.03] text-white/70"
                }`}
              >
                <div className="mx-auto grid h-11 w-11 place-items-center rounded-2xl bg-cyan-400/10">
                  <Icon className="h-5 w-5" />
                </div>
                <div className="mt-2 text-xs font-black tracking-wide">{item.label}</div>
                <div className="mt-1 text-[10px] font-semibold text-white/48">{item.status}</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}


function AnalyzeItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 text-sm font-medium text-cyan-50/82">
      <div className="flex items-center gap-2">
        <span className="h-1.5 w-1.5 rounded-full bg-cyan-300 shadow-[0_0_12px_rgba(34,211,238,0.95)]" />
        <span>{label}</span>
      </div>
      <span className="font-black text-white">{value}</span>
    </div>
  );
}


function ResultProgressCard({
  icon: Icon,
  title,
  subtitle,
  value,
  status,
}: {
  icon: any;
  title: string;
  subtitle: string;
  value: number | null | undefined;
  status: string;
}) {
  const pct = value === null || value === undefined ? null : clampPercent(value, 0);

  return (
    <div className="rounded-[24px] border border-cyan-300/12 bg-slate-950/82 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
      <div className="mb-3 flex items-start gap-3">
        <div className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl border border-cyan-300/15 bg-cyan-400/10 text-cyan-100">
          <Icon className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-lg font-black text-white">{title}</div>
              <div className="mt-1 text-sm font-medium text-white/55">{subtitle}</div>
            </div>
            <div className="text-right">
              <div className={`text-[30px] font-black leading-none ${pct !== null && pct >= 75 ? "text-emerald-300" : pct !== null && pct >= 50 ? "text-amber-300" : "text-rose-300"}`}>
                {pct === null ? "—" : `${pct}%`}
              </div>
              <div className="mt-1 text-sm font-bold text-white/70">{status}</div>
            </div>
          </div>
          <div className="mt-4 h-2.5 overflow-hidden rounded-full bg-white/8">
            <div
              className={`h-full rounded-full ${pct !== null && pct >= 75 ? "bg-gradient-to-r from-cyan-400 via-emerald-300 to-emerald-400" : pct !== null && pct >= 50 ? "bg-gradient-to-r from-cyan-400 via-amber-300 to-amber-400" : "bg-gradient-to-r from-rose-400 via-amber-300 to-cyan-400"}`}
              style={{ width: `${pct ?? 0}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}


function PersonaWorkflowCard({ workflow, labels }: { workflow: PersonaWorkflow; labels: ReturnType<typeof uiText> }) {
  return (
    <div className="rounded-[26px] border border-fuchsia-300/18 bg-fuchsia-950/18 p-5">
      <div className="mb-3 flex items-center gap-2 text-sm font-black uppercase tracking-[0.22em] text-fuchsia-100/85">
        <Brain className="h-5 w-5 text-fuchsia-200" />
        {labels.personaWorkflow}
      </div>
      <p className="text-sm leading-7 text-white/80">{workflow.summary}</p>
      <div className="mt-4 space-y-3">
        {workflow.stages.map((stage) => (
          <div key={stage.key} className="rounded-2xl border border-white/10 bg-black/22 p-4">
            <div className="text-xs font-black uppercase tracking-[0.18em] text-fuchsia-200/75">{labels.stageLabel} {stage.order}</div>
            <div className="mt-1 text-sm font-black text-white">{stage.title}</div>
            <p className="mt-2 text-sm leading-6 text-white/68">{stage.description}</p>
            <div className="mt-2 text-xs font-semibold text-cyan-100/72">{stage.output_intent}</div>
            {stage.order === 2 && (
              <div className="mt-2 rounded-xl border border-amber-300/15 bg-amber-950/20 px-3 py-2 text-xs font-semibold leading-5 text-amber-100/82">
                Locked until step 1 is generated and the facial identity is reviewed.
              </div>
            )}
          </div>
        ))}
      </div>
      <p className="mt-4 rounded-2xl border border-amber-300/14 bg-amber-950/18 px-3 py-2 text-xs leading-5 text-amber-100/80">{workflow.delivery_note}</p>
    </div>
  );
}

function NeuralResultsSidebar({
  result,
  labels,
  onUseSuggestion,
  onSendPromptToInput,
}: {
  result: MagicLensAnalyzeResult | null;
  labels: ReturnType<typeof uiText>;
  onUseSuggestion: (suggestion: MagicLensSuggestion, result: MagicLensAnalyzeResult) => void;
  onSendPromptToInput?: (prompt: string, result?: MagicLensAnalyzeResult) => void;
}) {
  const analysis = result?.face_profile?.real_face_analysis;
  const assessment = result?.face_profile?.production_assessment;
  const subject = result?.face_profile?.subject_analysis;
  const capabilities = subject?.capability_matrix || {};
  const backgroundAnalysis = subject?.background_analysis || {};
  const productAnalysis = subject?.product_analysis || {};
  const fullBodyAnalysis = subject?.full_body_analysis || {};
  const smallObjectAnalysis = subject?.small_object_analysis || {};
  const semanticVision = subject?.semantic_vision || {};
  const quality = analysis?.face_region_quality;
  const position = analysis?.face_position;
  const engine = analysis?.face_alignment_master;
  const alignment = assessment?.alignment_score ?? analysis?.alignment_score ?? null;
  const identity = assessment?.identity_reliability_score ?? analysis?.identity_reliability_score ?? null;
  const generation = assessment?.generation_confidence_score ?? analysis?.generation_confidence_score ?? null;
  const subjectQuality = subject?.reference_quality_score ?? null;
  const subjectPreservation = subject?.subject_preservation_score ?? null;
  const subjectBlocked = Boolean(
    subject?.hard_block_generation ||
      subject?.can_generate === false ||
      result?.face_profile?.generation_gate?.allowed === false
  );
  const verdictHeadline = assessment?.headline || "Usable with auto-crop and result review";
  const verdictGrade = assessment?.grade || "-";
  const verdictReadiness = assessment?.readiness || subject?.warning_level || "allowed_with_review";
  const faceCount = analysis?.face_count;
  const suggestions = result?.suggestions || [];
  const personaWorkflow = result?.persona_workflow || null;

  const landmarkStatus = engine?.status === "active" || engine?.status === "active_cached" || engine?.status === "landmarks_active"
    ? "Active"
    : engine?.status || "Pending";

  return (
    <div className="rounded-[30px] border border-cyan-300/14 bg-slate-950/86 p-4 shadow-[0_0_64px_rgba(34,211,238,0.08)] backdrop-blur-2xl">
      <div className="mb-5 flex items-center justify-between gap-3">
        <div>
          <div className="text-xs font-black uppercase tracking-[0.28em] text-cyan-200/72">Analysis Results</div>
          <div className="mt-2 text-2xl font-black tracking-tight text-white">Pro full subject-lock report</div>
        </div>
        <div className="rounded-2xl border border-cyan-300/15 bg-cyan-400/10 px-3 py-2 text-xs font-black uppercase tracking-[0.24em] text-cyan-100">
          {result ? (result.success ? "Measured" : "Failed") : "Waiting"}
        </div>
      </div>

      {!result ? (
        <div className="rounded-[26px] border border-white/10 bg-white/[0.04] p-5 text-base leading-8 text-white/78">
          {labels.resultEmpty}
        </div>
      ) : !result.success ? (
        <div className="rounded-[26px] border border-rose-300/25 bg-rose-500/12 p-5 text-base leading-8 text-rose-50">
          {result.error || result.description || "Neural Camera Analysis failed. Check backend/auth and retry with a PNG/JPEG/WEBP image."}
        </div>
      ) : (
        <div className="space-y-4">
          {personaWorkflow && <PersonaWorkflowCard workflow={personaWorkflow} labels={labels} />}
          <ResultProgressCard icon={Layers3} title="Subject Preservation" subtitle={subject?.subject_type || "Detecting subject"} value={subjectPreservation} status={subject?.hard_block_generation ? "Blocked" : subject?.can_generate_confidently ? "Client-ready" : subject?.can_generate ? "Review" : "Waiting"} />
          <ResultProgressCard icon={Activity} title="Reference Quality" subtitle={subject?.preservation_mode || "Universal subject lock"} value={subjectQuality} status={subjectBlocked ? "Blocked" : subject?.warning_level || "Pending"} />
          <ResultProgressCard icon={Focus} title="Alignment Score" subtitle="Pose, eyes, centering, sharpness" value={alignment} status={alignment !== null && alignment !== undefined ? "Measured" : "Missing"} />
          <ResultProgressCard icon={ShieldCheck} title="Identity Reliability" subtitle="Reference suitability for same-person img2img" value={identity} status={identity !== null && identity >= 75 ? "Good" : identity !== null && identity >= 50 ? "Risk" : "Weak"} />
          <ResultProgressCard icon={ScanFace} title="Generation Confidence" subtitle="Conservative score, not final likeness proof" value={generation} status={generation !== null && generation >= 85 ? "Client-ready" : generation !== null && generation >= 50 ? "Review" : "Retake"} />
          <ResultProgressCard icon={SunMedium} title="Lighting" subtitle={quality?.lighting_label || "Not measured"} value={quality?.lighting_label === "balanced" ? 85 : quality?.lighting_label ? 60 : null} status={quality?.lighting_label || "Pending"} />
          <ResultProgressCard icon={Aperture} title="Sharpness" subtitle={quality?.sharpness_label || "Not measured"} value={quality?.sharpness_laplacian ? Math.min(100, Math.round(quality.sharpness_laplacian)) : null} status={quality?.sharpness_label || "Pending"} />

          <div className="rounded-[26px] border border-cyan-300/12 bg-slate-950/82 p-5">
            <div className="mb-3 text-sm font-black uppercase tracking-[0.24em] text-cyan-100/80">Meaningful runtime status</div>
            <div className="grid gap-2 text-sm text-white/78">
              <div className="flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.03] px-3 py-2">
                <span>Subject type</span>
                <span className="font-black text-cyan-100">{subject?.subject_type || "—"}</span>
              </div>
              <div className="flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.03] px-3 py-2">
                <span>Subject coverage</span>
                <span className="font-black text-white">{subject?.primary_subject_coverage_percent !== undefined && subject?.primary_subject_coverage_percent !== null ? `${subject.primary_subject_coverage_percent}%` : "—"}</span>
              </div>
              <div className="flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.03] px-3 py-2">
                <span>Generation gate</span>
                <span className={subject?.hard_block_generation ? "font-black text-rose-200" : "font-black text-emerald-200"}>{subject?.hard_block_generation ? "Blocked" : subject?.can_generate ? "Allowed" : "Review"}</span>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                <CapabilityPill label="Person" value={capabilities.person} />
                <CapabilityPill label="Face" value={capabilities.face} />
                <CapabilityPill label="Full body" value={capabilities.full_body || fullBodyAnalysis} />
                <CapabilityPill label="Product" value={capabilities.product || productAnalysis} />
                <CapabilityPill label="Small/far object" value={capabilities.small_object || smallObjectAnalysis} />
                <CapabilityPill label="Background" value={capabilities.background || backgroundAnalysis} />
                <CapabilityPill label="Dark image" value={capabilities.dark_image} />
                <CapabilityPill label="Blurry image" value={capabilities.blurry_image} />
                <CapabilityPill label="Multi-person" value={capabilities.multi_person} />
                <CapabilityPill label="Far subject" value={capabilities.far_subject} />
              </div>
              <div className="flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.03] px-3 py-2">
                <span>Semantic vision</span>
                <span className={semanticVision?.used ? "font-black text-emerald-200" : "font-black text-amber-200"}>{semanticVision?.used ? semanticVision?.provider || "Enabled" : semanticVision?.provider || "Local CV only"}</span>
              </div>
              <div className="flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.03] px-3 py-2">
                <span>Background label</span>
                <span className="font-black text-white">{backgroundAnalysis?.semantic_label || backgroundAnalysis?.local_background_label || "—"}</span>
              </div>
              <div className="flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.03] px-3 py-2">
                <span>Face count</span>
                <span className={faceCount === 1 ? "font-black text-emerald-200" : "font-black text-amber-200"}>{faceCount ?? "—"}</span>
              </div>
              <div className="flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.03] px-3 py-2">
                <span>face-alignment-master</span>
                <span className="font-black text-white">{landmarkStatus}</span>
              </div>
              <div className="flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.03] px-3 py-2">
                <span>Multi-face ambiguity</span>
                <span className="font-black text-white">{assessment?.multi_face_ambiguity || analysis?.multi_face_ambiguity || "—"}</span>
              </div>
              <div className="flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.03] px-3 py-2">
                <span>Coverage</span>
                <span className="font-black text-white">{position?.coverage_percent !== undefined && position?.coverage_percent !== null ? `${position.coverage_percent}%` : "—"}</span>
              </div>
            </div>
          </div>

          {((assessment?.risks?.length || 0) > 0 || (subject?.risks?.length || 0) > 0) && (
            <div className="rounded-[26px] border border-amber-300/18 bg-amber-950/18 p-5">
              <div className="mb-3 text-sm font-black uppercase tracking-[0.24em] text-amber-100/80">Risks to fix</div>
              <ul className="space-y-2 text-sm leading-6 text-white/82">
                {uniqueStrings([...(subject?.risks || []), ...(assessment?.risks || [])]).slice(0, 6).map((risk, index) => <li key={`risk-${index}`}>• {risk}</li>)}
              </ul>
            </div>
          )}

          <div className="rounded-[26px] border border-cyan-300/12 bg-slate-950/82 p-5">
            <div className="mb-3 flex items-center gap-2 text-sm font-black uppercase tracking-[0.24em] text-cyan-100/80">
              <BadgeCheck className="h-4 w-4 text-cyan-200" />
              Recommendation
            </div>
            <p className="text-sm leading-7 text-white/82">{subject?.recommendations?.[0] || assessment?.recommendations?.[0] || "Use a clear, sharp, tightly framed reference before client-facing generation."}</p>
          </div>

          <div className="rounded-[26px] border border-cyan-300/12 bg-slate-950/82 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-black uppercase tracking-[0.24em] text-cyan-100/80">Production verdict</div>
                <div className="mt-1 text-lg font-black text-white">{verdictHeadline}</div>
              </div>
              <div className={subjectBlocked ? "rounded-2xl border border-rose-300/25 bg-rose-500/10 px-3 py-2 text-rose-100" : "rounded-2xl border border-emerald-300/20 bg-emerald-400/10 px-3 py-2 text-emerald-200"}>
                <div className="text-xs font-semibold uppercase tracking-[0.18em]">Grade</div>
                <div className="text-2xl font-black">{verdictGrade}</div>
              </div>
            </div>
            <div className="rounded-2xl border border-white/8 bg-white/[0.03] px-3 py-2">
              <div className="text-xs font-black uppercase tracking-[0.16em] text-white/45">Readiness</div>
              <div className="mt-1 font-semibold text-white">{verdictReadiness}</div>
            </div>
          </div>

          {suggestions.length > 0 && (
            <div className="space-y-3 rounded-[26px] border border-cyan-300/12 bg-slate-950/82 p-4">
              <div className="flex items-center gap-2 text-sm font-black uppercase tracking-[0.22em] text-cyan-100/80">
                <Layers3 className="h-5 w-5 text-cyan-200" />
                {labels.personaActions}
              </div>
              {suggestions.map((suggestion, index) => (
                <div key={`${suggestion.action}-${index}`} className="rounded-2xl border border-white/10 bg-black/25 p-3">
                  <div className="mb-2 text-sm font-black text-white">{suggestion.title}</div>
                  <div className="mb-3 max-h-24 overflow-auto whitespace-pre-wrap rounded-xl border border-white/8 bg-black/20 p-3 text-xs leading-6 text-white/68">
                    {suggestion.prompt}
                  </div>
                  <div className="grid gap-2">
                    <Button type="button" onClick={() => onUseSuggestion(suggestion, result)} className="rounded-2xl bg-cyan-400 py-4 font-black text-slate-950 hover:bg-cyan-300">
                      <Sparkles className="mr-2 h-4 w-4" />
                      {suggestion.action === "make_prompt" ? labels.promptOnly : labels.use}
                    </Button>
                    {suggestion.action === "make_prompt" && onSendPromptToInput && (
                      <Button type="button" variant="outline" onClick={() => onSendPromptToInput(suggestion.prompt, result)} className="rounded-2xl border-white/15 bg-white/10 py-4 font-black text-white hover:bg-white/15">
                        {labels.promptOnly}
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}


export function MagicLensModal({
  open,
  lang,
  apiBase = DEFAULT_API_BASE,
  onClose,
  onUseSuggestion,
  onSendPromptToInput,
}: MagicLensModalProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [cameraError, setCameraError] = useState<string | null>(null);
  const [cameraActive, setCameraActive] = useState(false);
  const [capturedFile, setCapturedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [hint, setHint] = useState("");
  const [faceSettings, setFaceSettings] = useState<FaceSettings>(DEFAULT_FACE_SETTINGS);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MagicLensAnalyzeResult | null>(null);
  const [liveFaceBox, setLiveFaceBox] = useState<LiveFaceBox | null>(null);
  const [cameraDevices, setCameraDevices] = useState<CameraDeviceOption[]>([]);
  const [selectedCameraId, setSelectedCameraId] = useState<string>("");

  const updatePreviewFromFile = (file: File) => {
    setPreviewUrl((prev) => {
      if (prev?.startsWith("blob:")) URL.revokeObjectURL(prev);
      return URL.createObjectURL(file);
    });
  };

  const t = uiText(lang);
  const rtl = isArabicLang(lang);
  const analysisState = loading
    ? "Analyzing"
    : result
    ? result.success ? "Measured" : "Failed"
    : cameraActive
    ? "Camera guide"
    : previewUrl
    ? "Ready to analyze"
    : "Idle";
  const analysisDotClass = loading
    ? "bg-amber-300 shadow-[0_0_18px_rgba(252,211,77,0.95)]"
    : result?.success
    ? "bg-emerald-300 shadow-[0_0_18px_rgba(110,231,183,0.95)]"
    : result
    ? "bg-rose-300 shadow-[0_0_18px_rgba(253,164,175,0.85)]"
    : "bg-cyan-300/65 shadow-[0_0_14px_rgba(103,232,249,0.55)]";

  const selectedSettingSummary = useMemo(
    () => [
      `${t.size}: ${faceSettings.size}`,
      `${t.orientation}: ${faceSettings.orientation}`,
      `${t.lighting}: ${faceSettings.lighting}`,
      `${t.temperature}: ${faceSettings.temperature}`,
      `${t.contrast}: ${faceSettings.contrast}`,
    ].join(" · "),
    [faceSettings, t.contrast, t.lighting, t.orientation, t.size, t.temperature]
  );

  const updateFaceSetting = (key: FaceSettingKey, value: string) => {
    setFaceSettings((prev) => ({ ...prev, [key]: value }));
    setResult(null);
  };

  const loadCameraDevices = async () => {
    if (!navigator.mediaDevices?.enumerateDevices) {
      return;
    }

    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const videos = devices
        .filter((device) => device.kind === "videoinput")
        .map((device, index) => ({
          deviceId: device.deviceId,
          label: device.label || `Camera ${index + 1}`,
          isDji: detectDjiCameraLabel(device.label || ""),
        }));

      setCameraDevices(videos);
      setSelectedCameraId((prev) => {
        if (prev && videos.some((item) => item.deviceId === prev)) {
          return prev;
        }
        const preferred = videos.find((item) => item.isDji) || videos[0];
        return preferred?.deviceId || "";
      });
    } catch {
      // no-op
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    setCameraActive(false);
    setLiveFaceBox(null);
  };

  const reset = () => {
    stopCamera();
    setCameraError(null);
    setCapturedFile(null);
    setPreviewUrl((prev) => {
      if (prev?.startsWith("blob:")) URL.revokeObjectURL(prev);
      return null;
    });
    setHint("");
    setLoading(false);
    setResult(null);
  };

  useEffect(() => {
    if (!open) {
      reset();
    }

    return () => {
      stopCamera();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    loadCameraDevices();
  }, [open]);

  useEffect(() => {
    if (!cameraActive || previewUrl) {
      setLiveFaceBox(null);
      return;
    }

    let alive = true;
    let timer: number | null = null;

    const bootLiveFaceDetector = async () => {
      const detectorClass = typeof window !== "undefined" ? (window as any).FaceDetector : null;

      if (!detectorClass) {
        setLiveFaceBox(null);
        return;
      }

      let detector: any;

      try {
        detector = new detectorClass({ fastMode: true, maxDetectedFaces: 1 });
      } catch {
        setLiveFaceBox(null);
        return;
      }

      timer = window.setInterval(async () => {
        const video = videoRef.current;

        if (!alive || !video || video.readyState < 2 || !video.videoWidth || !video.videoHeight) {
          return;
        }

        try {
          const faces = await detector.detect(video);
          const box = faces?.[0]?.boundingBox;

          if (!box) {
            setLiveFaceBox(null);
            return;
          }

          setLiveFaceBox({
            leftPct: Math.max(0, Math.min(100, (box.x / video.videoWidth) * 100)),
            topPct: Math.max(0, Math.min(100, (box.y / video.videoHeight) * 100)),
            widthPct: Math.max(5, Math.min(100, (box.width / video.videoWidth) * 100)),
            heightPct: Math.max(5, Math.min(100, (box.height / video.videoHeight) * 100)),
            detected: true,
          });
        } catch {
          setLiveFaceBox(null);
        }
      }, 280);
    };

    bootLiveFaceDetector();

    return () => {
      alive = false;
      if (timer) window.clearInterval(timer);
    };
  }, [cameraActive, previewUrl]);

  const openCamera = async () => {
    setCameraError(null);
    setResult(null);

    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error(t.noCamera);
      }

      const [requestedWidth, requestedHeight] = faceSettings.size
        .split("x")
        .map((part) => Number.parseInt(part, 10));
      const selectedDevice = cameraDevices.find((item) => item.deviceId === selectedCameraId);
      const djiOrExternalCamera = Boolean(selectedDevice?.isDji || selectedCameraId);

      // Capture quality is independent from final output size. DJI/external webcams
      // should be requested at 1080p when possible so Neural Camera has a strong
      // source image for identity/source-lock analysis.
      const videoConstraints: MediaTrackConstraints = {
        width: { ideal: djiOrExternalCamera ? 1920 : Math.max(Number.isFinite(requestedWidth) ? requestedWidth : 1280, 1280) },
        height: { ideal: djiOrExternalCamera ? 1080 : Math.max(Number.isFinite(requestedHeight) ? requestedHeight : 720, 720) },
        frameRate: { ideal: 30, max: 60 },
      };

      if (selectedCameraId) {
        videoConstraints.deviceId = { exact: selectedCameraId };
      } else {
        videoConstraints.facingMode = "user";
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        video: videoConstraints,
        audio: false,
      });

      streamRef.current = stream;
      setCameraActive(true);

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }

      await loadCameraDevices();
    } catch (error: any) {
      setCameraError(error?.message || t.noCamera);
    }
  };

  const capturePhoto = async () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;

    if (!video || !canvas) return;

    const width = video.videoWidth || 1280;
    const height = video.videoHeight || 720;

    canvas.width = width;
    canvas.height = height;

    const context = canvas.getContext("2d");
    if (!context) return;

    context.drawImage(video, 0, 0, width, height);

    canvas.toBlob(
      (blob) => {
        if (!blob) return;

        const file = new File([blob], `magic_lens_${Date.now()}.jpg`, {
          type: "image/jpeg",
        });

        setCapturedFile(file);
        updatePreviewFromFile(file);
        setResult(null);
        stopCamera();
      },
      "image/jpeg",
      0.97
    );
  };

  const handleFile = (file: File | null) => {
    if (!file) return;

    setCapturedFile(file);
    updatePreviewFromFile(file);
    setResult(null);
    stopCamera();
  };

  const analyze = async () => {
    if (!capturedFile || loading) return;

    setLoading(true);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("image", capturedFile);
      formData.append("hint", hint);
      formData.append("lang", lang);
      formData.append("alignment_size", faceSettings.size);
      formData.append("alignment_orientation", faceSettings.orientation);
      formData.append("alignment_lighting", faceSettings.lighting);
      formData.append("alignment_temperature", faceSettings.temperature);
      formData.append("alignment_contrast", faceSettings.contrast);

      const response = await fetch(`${apiBase}/assistant/vision/analyze`, {
        method: "POST",
        headers: withAuthHeaders(),
        body: formData,
      });

      const data = (await response.json()) as MagicLensAnalyzeResult;

      if (!response.ok || !data.success) {
        throw new Error(data?.error || `Neural Camera Analysis failed: ${response.status}`);
      }

      setResult(data);
    } catch (error: any) {
      setResult({
        success: false,
        provider: "frontend_error",
        description: error?.message || "Neural Camera Analysis failed",
        detected_language: lang,
        suggestions: [],
        error: error?.message || "Neural Camera Analysis failed",
      });
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[10000] flex items-center justify-center bg-slate-950/90 p-3 text-white backdrop-blur-xl sm:p-5">
      <div
        dir={rtl ? "rtl" : "ltr"}
        className="relative max-h-[96vh] w-full max-w-[1700px] overflow-hidden rounded-[34px] border border-cyan-300/14 bg-[#050b17] text-white shadow-[0_0_140px_rgba(34,211,238,0.16)]"
      >
        <NeuralRadianceBackdrop />

        <div className="relative z-10 border-b border-cyan-300/10 bg-slate-950/50 px-5 py-5 backdrop-blur-2xl sm:px-6">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <div className="flex items-center gap-4">
              <div className="grid h-16 w-16 shrink-0 place-items-center rounded-[22px] border border-cyan-300/20 bg-cyan-400/10 text-cyan-100 shadow-[0_0_34px_rgba(34,211,238,0.18)]">
                <Brain className="h-8 w-8" />
              </div>
              <div>
                <h2 className="text-3xl font-black tracking-tight text-white sm:text-4xl">Neural Camera Analysis</h2>
                <p className="mt-1 text-sm font-medium text-cyan-100/70 sm:text-base">Camera guide · Backend-measured face quality · Identity-lock readiness</p>
              </div>
            </div>

            <div className="flex items-center gap-3 self-start xl:self-auto">
              <div className="rounded-2xl border border-cyan-300/20 bg-slate-950/62 px-4 py-3 backdrop-blur-xl">
                <div className="flex items-center gap-3">
                  <span className={`inline-flex h-3.5 w-3.5 rounded-full ${analysisDotClass}`} />
                  <span className="text-[13px] font-black uppercase tracking-[0.22em] text-cyan-100">{analysisState}</span>
                </div>
              </div>
              <div
                className={`hidden h-12 w-56 rounded-2xl border border-cyan-300/16 bg-[linear-gradient(90deg,rgba(34,211,238,0)_0%,rgba(34,211,238,.85)_50%,rgba(34,211,238,0)_100%)] bg-[length:160%_100%] transition-opacity md:block ${loading ? "opacity-100" : "opacity-25"}`}
                style={{ animation: loading ? 'neuralWave 2.2s linear infinite' : 'none' }}
              />
              <div
                className="grid h-12 w-12 place-items-center rounded-2xl border border-cyan-300/16 bg-slate-950/62 text-white/85"
                title="Settings"
              >
                <Settings className="h-5 w-5" />
              </div>
              <button
                type="button"
                onClick={onClose}
                className="grid h-12 w-12 place-items-center rounded-2xl border border-white/12 bg-white/[0.04] text-white/80 transition hover:bg-white/10 hover:text-white"
                title={t.close}
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          </div>
        </div>

        <div className="relative z-10 max-h-[calc(96vh-114px)] overflow-y-auto p-4 sm:p-5">
          <div className="grid gap-5 xl:grid-cols-[104px_minmax(0,1.45fr)_460px]">
            <NeuralSideRail />

            <div className="space-y-5">
              <div className="rounded-[30px] border border-cyan-300/14 bg-slate-950/70 p-4 shadow-[0_0_54px_rgba(34,211,238,0.05)] backdrop-blur-2xl">
                <div className="relative flex aspect-[16/10] min-h-[420px] items-center justify-center overflow-hidden rounded-[32px] border border-cyan-300/16 bg-slate-950/82 shadow-[inset_0_0_140px_rgba(34,211,238,0.08),0_28px_80px_rgba(0,0,0,0.34)] [transform-style:preserve-3d]">
                  {previewUrl ? (
                    <img src={previewUrl} alt="Neural Camera Analysis preview" className="relative z-10 h-full w-full object-cover" />
                  ) : (
                    <video ref={videoRef} className="relative z-10 h-full w-full object-cover" playsInline muted />
                  )}

                  {!previewUrl && cameraActive && <HolographicCameraOverlay faceBox={liveFaceBox} />}

                  {!previewUrl && !cameraActive && (
                    <NeuralPreviewPlaceholder title={t.previewIdle} body={t.previewHint} />
                  )}

                  {previewUrl && (
                    <div className="absolute left-4 top-4 z-20 rounded-2xl border border-emerald-200/25 bg-emerald-400/12 px-4 py-2 text-xs font-black uppercase tracking-[0.22em] text-emerald-100 backdrop-blur-xl">
                      {t.previewReady}
                    </div>
                  )}
                </div>

                <div className="mt-4 grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
                  <div className="rounded-[24px] border border-cyan-300/12 bg-slate-950/74 p-4 backdrop-blur-xl">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-sm font-black uppercase tracking-[0.22em] text-cyan-100/82">DJI / Camera source</div>
                        <div className="mt-1 text-sm leading-6 text-white/68">
                          Connect your DJI Osmo Pocket 3 by USB-C, switch the camera to <span className="font-black text-cyan-100">Webcam</span> mode, then select it here.
                        </div>
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        onClick={loadCameraDevices}
                        className="rounded-2xl border-white/15 bg-white/[0.04] px-4 py-2 font-black text-white hover:bg-white/10"
                      >
                        <RefreshCw className="mr-2 h-4 w-4" />
                        Refresh
                      </Button>
                    </div>

                    <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_220px]">
                      <label className="block">
                        <span className="mb-2 block text-xs font-black uppercase tracking-[0.18em] text-white/48">Camera source</span>
                        <select
                          value={selectedCameraId}
                          onChange={(event) => setSelectedCameraId(event.target.value)}
                          className="w-full rounded-2xl border border-white/15 bg-slate-950/75 px-4 py-3 text-sm font-semibold text-white outline-none focus:border-cyan-300/50 focus:ring-2 focus:ring-cyan-300/15"
                        >
                          <option value="">Default camera</option>
                          {cameraDevices.map((device) => (
                            <option key={device.deviceId} value={device.deviceId}>
                              {device.isDji ? `DJI · ${device.label}` : device.label}
                            </option>
                          ))}
                        </select>
                      </label>

                      <div className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3">
                        <div className="text-xs font-black uppercase tracking-[0.18em] text-white/48">Recommended mode</div>
                        <div className="mt-1 text-sm font-bold text-cyan-100">USB-C Webcam</div>
                        <div className="mt-1 text-xs leading-5 text-white/58">Best for DJI Osmo Pocket 3 inside the browser.</div>
                      </div>
                    </div>

                    <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold text-white/62">
                      <span className="rounded-full border border-cyan-300/12 bg-cyan-400/8 px-3 py-1.5">1. Connect USB-C</span>
                      <span className="rounded-full border border-cyan-300/12 bg-cyan-400/8 px-3 py-1.5">2. Choose Webcam mode</span>
                      <span className="rounded-full border border-cyan-300/12 bg-cyan-400/8 px-3 py-1.5">3. Click Open camera</span>
                    </div>
                  </div>

                  <div className="rounded-[24px] border border-cyan-300/12 bg-slate-950/74 p-4 backdrop-blur-xl">
                    <div className="text-sm font-black uppercase tracking-[0.22em] text-cyan-100/82">Live source status</div>
                    <div className="mt-3 space-y-2 text-sm text-white/76">
                      <div className="flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.03] px-3 py-2">
                        <span>Detected cameras</span>
                        <span className="font-black text-white">{cameraDevices.length}</span>
                      </div>
                      <div className="flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.03] px-3 py-2">
                        <span>DJI source</span>
                        <span className="font-black text-white">{cameraDevices.some((item) => item.isDji) ? "Available" : "Not detected"}</span>
                      </div>
                      <div className="flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.03] px-3 py-2">
                        <span>Selected input</span>
                        <span className="max-w-[180px] truncate text-right font-black text-cyan-100">{cameraDevices.find((item) => item.deviceId === selectedCameraId)?.label || "Default camera"}</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="mt-4 grid gap-3 md:grid-cols-[1fr_1fr_auto]">
                  {!previewUrl ? (
                    <Button type="button" onClick={openCamera} className="rounded-2xl bg-cyan-400 py-6 text-base font-black text-slate-950 hover:bg-cyan-300">
                      <Camera className="mr-2 h-5 w-5" />
                      {t.startCamera}
                    </Button>
                  ) : (
                    <Button type="button" onClick={reset} variant="outline" className="rounded-2xl border-white/15 bg-white/[0.04] py-6 text-base font-black text-white hover:bg-white/10">
                      <RefreshCw className="mr-2 h-5 w-5" />
                      {t.retake}
                    </Button>
                  )}

                  {!previewUrl && cameraActive ? (
                    <Button type="button" onClick={capturePhoto} className="rounded-2xl bg-emerald-400 py-6 text-base font-black text-slate-950 hover:bg-emerald-300">
                      <Send className="mr-2 h-5 w-5" />
                      {t.capture}
                    </Button>
                  ) : (
                    <Button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      variant="outline"
                      className="rounded-2xl border-white/15 bg-white/[0.04] py-6 text-base font-black text-white hover:bg-white/10"
                    >
                      <Upload className="mr-2 h-5 w-5" />
                      {t.upload}
                    </Button>
                  )}

                  <Button
                    type="button"
                    disabled={!capturedFile || loading}
                    onClick={analyze}
                    className="rounded-2xl bg-gradient-to-r from-cyan-400 via-sky-400 to-emerald-300 px-6 py-6 text-base font-black text-slate-950 hover:opacity-95 disabled:opacity-45"
                  >
                    {loading ? <Loader2 className="mr-2 h-5 w-5 animate-spin" /> : <Radar className="mr-2 h-5 w-5" />}
                    {loading ? t.analyzing : t.analyze}
                  </Button>
                </div>

                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  className="hidden"
                  onChange={(event) => handleFile(event.target.files?.[0] || null)}
                />
              </div>

              {cameraError && (
                <div className="rounded-2xl border border-red-300/25 bg-red-500/15 p-4 text-sm font-semibold leading-6 text-red-50">
                  {cameraError}
                </div>
              )}

              <div className="grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
                <div className="rounded-[28px] border border-cyan-300/12 bg-slate-950/74 p-5 backdrop-blur-2xl">
                  <div className="mb-4 flex items-start gap-3">
                    <div className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-cyan-400/12 text-cyan-100">
                      <SlidersHorizontal className="h-5 w-5" />
                    </div>
                    <div>
                      <h3 className="text-xl font-black text-white">{t.settingsTitle}</h3>
                      <p className="mt-1 text-sm leading-6 text-cyan-50/70">{t.settingsSubtitle}</p>
                    </div>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <SettingSelect label={t.size} value={faceSettings.size} options={FACE_SETTING_OPTIONS.size} onChange={(value) => updateFaceSetting("size", value)} />
                    <SettingSelect label={t.orientation} value={faceSettings.orientation} options={FACE_SETTING_OPTIONS.orientation} onChange={(value) => updateFaceSetting("orientation", value)} />
                    <SettingSelect label={t.lighting} value={faceSettings.lighting} options={FACE_SETTING_OPTIONS.lighting} onChange={(value) => updateFaceSetting("lighting", value)} />
                    <SettingSelect label={t.temperature} value={faceSettings.temperature} options={FACE_SETTING_OPTIONS.temperature} onChange={(value) => updateFaceSetting("temperature", value)} />
                    <SettingSelect label={t.contrast} value={faceSettings.contrast} options={FACE_SETTING_OPTIONS.contrast} onChange={(value) => updateFaceSetting("contrast", value)} />
                  </div>

                  <div className="mt-4 rounded-2xl border border-cyan-300/12 bg-cyan-400/8 px-4 py-3 text-sm font-semibold leading-6 text-cyan-50">
                    {selectedSettingSummary}
                  </div>
                </div>

                <div className="rounded-[28px] border border-cyan-300/12 bg-slate-950/74 p-5 backdrop-blur-2xl">
                  <div className="mb-4 flex items-start gap-3">
                    <div className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-cyan-400/12 text-cyan-100">
                      <Activity className="h-5 w-5" />
                    </div>
                    <div>
                      <h3 className="text-xl font-black text-white">Prompt & Guidance</h3>
                      <p className="mt-1 text-sm leading-6 text-cyan-50/70">Optional production hint for better generation guidance.</p>
                    </div>
                  </div>

                  <input
                    value={hint}
                    onChange={(event) => setHint(event.target.value)}
                    placeholder={t.hint}
                    className="w-full rounded-2xl border border-white/15 bg-slate-950/75 px-4 py-4 text-base font-medium text-white outline-none placeholder:text-white/45 focus:border-cyan-300/50 focus:ring-2 focus:ring-cyan-300/15"
                  />

                  <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                      <div className="text-xs font-black uppercase tracking-[0.18em] text-white/45">Resolution</div>
                      <div className="mt-1 text-lg font-black text-white">{faceSettings.size}</div>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                      <div className="text-xs font-black uppercase tracking-[0.18em] text-white/45">Lighting</div>
                      <div className="mt-1 text-lg font-black text-white">{faceSettings.lighting}</div>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 sm:col-span-2 xl:col-span-1">
                      <div className="text-xs font-black uppercase tracking-[0.18em] text-white/45">Identity mode</div>
                      <div className="mt-1 text-lg font-black text-emerald-200">Locked</div>
                    </div>
                  </div>
                </div>
              </div>

              {result && (
                <div className="space-y-4 rounded-[28px] border border-cyan-300/12 bg-slate-950/74 p-5 backdrop-blur-2xl">
                  {result.face_profile?.production_assessment && (
                    <ProductionAssessmentCard assessment={result.face_profile.production_assessment} labels={t} />
                  )}

                  {result.face_profile?.real_face_analysis?.face_alignment_master && (
                    <FaceAlignmentMasterCard analysis={result.face_profile.real_face_analysis} labels={t} />
                  )}

                  {result.face_profile?.real_face_analysis && (
                    <RealFaceAnalysisCard analysis={result.face_profile.real_face_analysis} labels={t} />
                  )}

                  {result.face_profile && (
                    <div className="rounded-3xl border border-cyan-200/20 bg-cyan-950/30 p-4 shadow-[0_0_38px_rgba(34,211,238,0.10)]">
                      <div className="mb-3 flex items-center gap-2 text-sm font-black text-cyan-50">
                        <SlidersHorizontal className="h-4 w-4 text-cyan-200" />
                        {t.faceDetails}
                      </div>
                      <div className="grid gap-2 md:grid-cols-2">
                        <DetailRow label={t.size} value={result.face_profile.output_size || result.face_profile.image_size} />
                        {result.face_profile.source_image_size && result.face_profile.source_image_size !== (result.face_profile.output_size || result.face_profile.image_size) && (
                          <DetailRow label={t.sourceSize} value={result.face_profile.source_image_size} />
                        )}
                        <DetailRow label={t.orientation} value={result.face_profile.orientation} />
                        <DetailRow label={t.lighting} value={result.face_profile.lighting} />
                        <DetailRow label={t.temperature} value={result.face_profile.color_temperature} />
                        <DetailRow label={t.contrast} value={result.face_profile.contrast} />
                      </div>
                    </div>
                  )}

                  {result.face_prompt && <PromptCard title={t.facePrompt}>{result.face_prompt}</PromptCard>}
                </div>
              )}
            </div>

            <NeuralResultsSidebar result={result} labels={t} onUseSuggestion={onUseSuggestion} onSendPromptToInput={onSendPromptToInput} />
          </div>
        </div>

        <canvas ref={canvasRef} className="hidden" />
      </div>
    </div>
  );
}

export default MagicLensModal;
