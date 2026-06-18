export type NodeKind =
  | "trigger"
  | "ai_strategist"
  | "creative_director"
  | "prompt_engineer"
  | "model_advisor"
  | "approval"
  | "image_generation"
  | "vision_analyzer"
  | "quality_critic"
  | "auto_improve"
  | "condition"
  | "output";

export type NodeStatus = "idle" | "queued" | "running" | "success" | "error" | "warning";

export type NodePort = "input" | "output";

export type WorkflowNode = {
  id: string;
  kind: NodeKind;
  title: string;
  description: string;
  x: number;
  y: number;
  width: number;
  status: NodeStatus;
  progress: number;
  elapsedMs: number;
  previewUrl?: string;
  previewType?: "image" | "video" | "text";
  outputText?: string;
  error?: string;
  config: Record<string, string | number | boolean>;
};

export type WorkflowEdge = {
  id: string;
  from: string;
  to: string;
};

export type WorkflowLog = {
  id: string;
  level: "info" | "success" | "warning" | "error";
  message: string;
  timestamp: string;
};

export type WorkflowPayload = {
  title: string;
  goal: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
};

export type RunResponse = {
  ok: boolean;
  run_id: string;
  summary: string;
  logs: WorkflowLog[];
  node_outputs: Record<string, any>;
};
