import { NODE_META } from "./registry";
import type { NodeKind, WorkflowEdge, WorkflowNode } from "./types";

export function makeId(prefix: string) {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

export function createNode(kind: NodeKind, x = 120, y = 120): WorkflowNode {
  const meta = NODE_META[kind];
  return {
    id: makeId(kind),
    kind,
    title: meta.label,
    description: meta.description,
    x,
    y,
    width: 270,
    status: "idle",
    progress: 0,
    elapsedMs: 0,
    config: { ...meta.defaults },
  };
}

export function defaultWorkflow(): { nodes: WorkflowNode[]; edges: WorkflowEdge[] } {
  const nodes: WorkflowNode[] = [
    { ...createNode("trigger", 80, 220), id: "n_trigger", title: "User Request" },
    { ...createNode("ai_strategist", 390, 150), id: "n_strategy" },
    { ...createNode("creative_director", 700, 150), id: "n_director" },
    { ...createNode("prompt_engineer", 1010, 150), id: "n_prompt" },
    { ...createNode("model_advisor", 1010, 380), id: "n_model" },
    { ...createNode("approval", 1320, 250), id: "n_approval" },
    { ...createNode("image_generation", 1640, 140), id: "n_image" },
    { ...createNode("vision_analyzer", 1960, 140), id: "n_vision" },
    { ...createNode("quality_critic", 1960, 370), id: "n_critic" },
    { ...createNode("output", 2280, 250), id: "n_output" },
  ];

  const edges: WorkflowEdge[] = [
    { id: "e_1", from: "n_trigger", to: "n_strategy" },
    { id: "e_2", from: "n_strategy", to: "n_director" },
    { id: "e_3", from: "n_director", to: "n_prompt" },
    { id: "e_4", from: "n_prompt", to: "n_model" },
    { id: "e_5", from: "n_prompt", to: "n_approval" },
    { id: "e_6", from: "n_model", to: "n_approval" },
    { id: "e_7", from: "n_approval", to: "n_image" },
    { id: "e_9", from: "n_image", to: "n_vision" },
    { id: "e_11", from: "n_vision", to: "n_critic" },
    { id: "e_12", from: "n_critic", to: "n_output" },
  ];

  return { nodes, edges };
}

export function topoSort(nodes: WorkflowNode[], edges: WorkflowEdge[]): WorkflowNode[] {
  const map = new Map(nodes.map((node) => [node.id, node]));
  const incoming = new Map(nodes.map((node) => [node.id, 0]));
  const outgoing = new Map<string, string[]>();

  edges.forEach((edge) => {
    if (!map.has(edge.from) || !map.has(edge.to)) return;
    outgoing.set(edge.from, [...(outgoing.get(edge.from) || []), edge.to]);
    incoming.set(edge.to, (incoming.get(edge.to) || 0) + 1);
  });

  const queue = nodes.filter((node) => (incoming.get(node.id) || 0) === 0);
  const out: WorkflowNode[] = [];

  while (queue.length) {
    const node = queue.shift()!;
    out.push(node);
    for (const target of outgoing.get(node.id) || []) {
      incoming.set(target, (incoming.get(target) || 0) - 1);
      if ((incoming.get(target) || 0) === 0) {
        const targetNode = map.get(target);
        if (targetNode) queue.push(targetNode);
      }
    }
  }

  const missing = nodes.filter((node) => !out.some((item) => item.id === node.id));
  if (missing.length > 0) {
    throw new Error("Workflow graph contains a cycle. Remove the loop before running.");
  }
  return out;
}

export function formatMs(ms: number) {
  const seconds = Math.floor(ms / 1000);
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function extractAssetUrl(data: any): string | undefined {
  if (!data) return undefined;
  if (typeof data === "string" && (data.startsWith("http") || data.startsWith("/"))) return data;

  const candidates = [
    data.url,
    data.image_url,
    data.video_url,
    data.output_url,
    data.file_url,
    data.result_url,
    data.path,
    data.image_path,
    data.video_path,
    data?.data?.url,
    data?.data?.image_url,
    data?.data?.video_url,
    data?.generation?.url,
    data?.generation?.image_url,
    data?.generation?.video_url,
  ];

  for (const value of candidates) {
    if (typeof value === "string" && value.length > 0) return value;
  }

  if (Array.isArray(data.outputs) && data.outputs[0]) return extractAssetUrl(data.outputs[0]);
  if (Array.isArray(data.images) && data.images[0]) return extractAssetUrl(data.images[0]);
  if (Array.isArray(data.videos) && data.videos[0]) return extractAssetUrl(data.videos[0]);

  return undefined;
}
