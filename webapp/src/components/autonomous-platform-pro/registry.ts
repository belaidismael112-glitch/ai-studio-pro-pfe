import {
  Bot,
  BrainCircuit,
  Brush,
  CheckCircle2,
  Eye,
  GitBranch,
  Image,
  Lightbulb,
  MessageSquareText,
  ShieldCheck,
  TimerReset,
  Zap,
} from "lucide-react";
import type { NodeKind } from "./types";

export const NODE_META: Record<NodeKind, {
  label: string;
  role: string;
  icon: any;
  color: string;
  description: string;
  defaults: Record<string, string | number | boolean>;
}> = {
  trigger: {
    label: "User Trigger",
    role: "START",
    icon: Zap,
    color: "from-cyan-400/25 to-blue-500/10",
    description: "Receives the user request and launches the autonomous workflow.",
    defaults: { command: "Create a campaign with one approved hero image." },
  },
  ai_strategist: {
    label: "Planner",
    role: "STRATEGY",
    icon: BrainCircuit,
    color: "from-violet-400/25 to-fuchsia-500/10",
    description: "Extracts business goal, audience, tone, offer and campaign direction.",
    defaults: { audience: "project users", objective: "campaign", tone: "clean" },
  },
  creative_director: {
    label: "Art Direction",
    role: "ART DIRECTION",
    icon: Brush,
    color: "from-fuchsia-400/20 to-orange-400/10",
    description: "Defines composition, lighting, visual identity and visual style.",
    defaults: { camera: "85mm", lighting: "clean", mood: "calm" },
  },
  prompt_engineer: {
    label: "Prompt Engineer",
    role: "PROMPT",
    icon: Brush,
    color: "from-emerald-400/25 to-cyan-500/10",
    description: "Turns rough ideas into professional prompts and negative prompts.",
    defaults: { style: "clean commercial", negative: "low quality, blurry, distorted" },
  },
  model_advisor: {
    label: "Model Advisor",
    role: "MODEL",
    icon: BrainCircuit,
    color: "from-sky-400/20 to-cyan-500/10",
    description: "Selects local model/settings based on GPU, quality, cost and task type.",
    defaults: { gpu: "6GB", steps: 8, cfg: 1, resolution: "768x768" },
  },
  approval: {
    label: "Human Approval",
    role: "PERMISSION",
    icon: ShieldCheck,
    color: "from-amber-300/25 to-red-500/10",
    description: "Stops before spending credits or launching generation.",
    defaults: { required: true, maxCredits: 60 },
  },
  image_generation: {
    label: "Generate Image",
    role: "IMAGE",
    icon: Image,
    color: "from-cyan-400/25 to-fuchsia-500/10",
    description: "Calls the existing image-generation endpoint after backend validation and human approval, then displays the result preview.",
    defaults: { prompt: "clean campaign hero image", width: 768, height: 768 },
  },
  vision_analyzer: {
    label: "Neural Camera Handoff",
    role: "REVIEW HANDOFF",
    icon: Eye,
    color: "from-cyan-400/20 to-emerald-500/10",
    description: "Prepares a real review handoff. Open Neural Camera Analysis on the generated asset for pixel-level defect analysis.",
    defaults: { model: "moondream", check: "composition, clarity, subject, brand" },
  },
  quality_critic: {
    label: "Quality Checklist",
    role: "REVIEW CHECKLIST",
    icon: Lightbulb,
    color: "from-yellow-300/25 to-orange-500/10",
    description: "Prepares the quality checklist and minimum score. A score is shown only after real image analysis.",
    defaults: { minScore: 80, dimensions: "quality, alignment, brand, composition" },
  },
  auto_improve: {
    label: "Auto Improve",
    role: "IMPROVE",
    icon: TimerReset,
    color: "from-emerald-400/20 to-fuchsia-500/10",
    description: "Applies an explicit deterministic prompt improvement before a new approved generation run.",
    defaults: { iterations: 2, improve: "sharper, clearer subject" },
  },
  condition: {
    label: "Condition Marker",
    role: "REVIEW RULE",
    icon: GitBranch,
    color: "from-indigo-400/20 to-cyan-500/10",
    description: "Registers a review-only condition. Automatic IF / ELSE branching is not executed until a real metric and a branch runner are available.",
    defaults: { condition: "quality_score >= 80" },
  },
  output: {
    label: "Final Output",
    role: "RESULT",
    icon: MessageSquareText,
    color: "from-white/15 to-cyan-500/10",
    description: "Collects final assets, prompts, logs, scores and recommendations.",
    defaults: { includePrompt: true, includeAssets: true, includeScore: true },
  },
};

export const NODE_ORDER: NodeKind[] = [
  "trigger",
  "ai_strategist",
  "creative_director",
  "prompt_engineer",
  "model_advisor",
  "approval",
  "image_generation",
  "vision_analyzer",
  "quality_critic",
  "auto_improve",
  "condition",
  "output",
];
