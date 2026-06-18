"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, BrainCircuit, Play, Save, Loader2 } from "lucide-react";
import { OperatorPipelineBackdrop } from "@/components/OperatorPipelineBackdrop";
import { FocusModeToggle } from "@/components/layout/focus-mode-toggle";
import NodePalette from "./node-palette";
import WorkflowCanvasPro from "./workflow-canvas-pro";
import InspectorPro from "./inspector-pro";
import ExecutionPanelPro from "./execution-panel-pro";
import ResultReviewPanel from "./result-review-panel";
import { createNode, defaultWorkflow, makeId, topoSort } from "./workflow-utils";
import {
  callGeneration,
  extractAssetUrl,
  extractGenerationId,
  pollGenerationResult,
  planAutonomousPlatform,
  runAutonomousPlatform,
} from "@/lib/autonomous-platform-pro-api";
import type { NodeKind, WorkflowEdge, WorkflowLog, WorkflowNode } from "./types";

const STORAGE_KEY = "ai-studio-autonomous-platform-pro-v5-image-first";

type ReviewState = {
  nodeId: string;
  title: string;
  kind: "image";
  url: string;
};

function ts() {
  return new Date().toLocaleTimeString();
}

function makeLog(level: WorkflowLog["level"], message: string): WorkflowLog {
  return { id: makeId("log"), level, message, timestamp: ts() };
}

export default function AutonomousPlatformPro() {
  const initial = useMemo(() => defaultWorkflow(), []);
  const [title, setTitle] = useState("Workflow Builder");
  const [goal, setGoal] = useState("Create a complete campaign workflow.");
  const [nodes, setNodes] = useState<WorkflowNode[]>(initial.nodes);
  const [edges, setEdges] = useState<WorkflowEdge[]>(initial.edges);
  const [selectedId, setSelectedId] = useState<string | null>(initial.nodes[0]?.id || null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [connectingFrom, setConnectingFrom] = useState<string | null>(null);
  const [logs, setLogs] = useState<WorkflowLog[]>([]);
  const [running, setRunning] = useState(false);
  const [reviewState, setReviewState] = useState<ReviewState | null>(null);
  const [regeneratingId, setRegeneratingId] = useState<string | null>(null);
  const [pendingApproval, setPendingApproval] = useState(false);
  const [serverEstimatedCredits, setServerEstimatedCredits] = useState<number | null>(null);
  const [lastBackendOutputs, setLastBackendOutputs] = useState<Record<string, Record<string, any>>>({});

  const selected = useMemo(() => nodes.find((n) => n.id === selectedId) || null, [nodes, selectedId]);
  const localEstimatedCredits = useMemo(
    () => nodes.filter((node) => node.kind === "image_generation").length * 10,
    [nodes]
  );
  const estimatedCredits = serverEstimatedCredits ?? localEstimatedCredits;
  const hasCreditActions = estimatedCredits > 0;


  useEffect(() => {
    setServerEstimatedCredits(null);
  }, [nodes, edges]);

  useEffect(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed.nodes) && Array.isArray(parsed.edges)) {
        setTitle(parsed.title || "Workflow Builder");
        setGoal(parsed.goal || "Create a complete campaign workflow.");
        setNodes(parsed.nodes);
        setEdges(parsed.edges);
      }
    } catch {}
  }, []);

  function updateNode(next: WorkflowNode) {
    setNodes((prev) => prev.map((n) => (n.id === next.id ? next : n)));
  }

  function patchNode(id: string, patch: Partial<WorkflowNode>) {
    setNodes((prev) => prev.map((n) => (n.id === id ? { ...n, ...patch } : n)));
  }

  function add(kind: NodeKind) {
    const node = createNode(kind, 150 + Math.random() * 600, 160 + Math.random() * 320);
    setNodes((prev) => [...prev, node]);
    setSelectedId(node.id);
    setSelectedEdgeId(null);
  }

  function connect(to: string) {
    if (!connectingFrom || connectingFrom === to) return;

    setEdges((prev) => {
      const exists = prev.some((e) => e.from === connectingFrom && e.to === to);
      if (exists) return prev;
      return [...prev, { id: makeId("edge"), from: connectingFrom, to }];
    });

    setConnectingFrom(null);
    setSelectedEdgeId(null);
  }

  function deleteEdge(id: string) {
    setEdges((prev) => prev.filter((e) => e.id !== id));
    setSelectedEdgeId(null);
  }

  function remove(id: string) {
    setNodes((prev) => prev.filter((n) => n.id !== id));
    setEdges((prev) => prev.filter((e) => e.from !== id && e.to !== id));
    setSelectedId(null);
    setSelectedEdgeId(null);
    if (reviewState?.nodeId === id) setReviewState(null);
  }

  function duplicate(id: string) {
    const node = nodes.find((n) => n.id === id);
    if (!node) return;
    const copy = {
      ...node,
      id: makeId(node.kind),
      title: `${node.title} Copy`,
      x: node.x + 80,
      y: node.y + 80,
      status: "idle" as const,
      progress: 0,
      elapsedMs: 0,
      error: undefined,
      previewUrl: undefined,
      outputText: undefined,
    };
    setNodes((prev) => [...prev, copy]);
    setSelectedId(copy.id);
    setSelectedEdgeId(null);
  }

  function save() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ title, goal, nodes, edges }));
    setLogs((prev) => [...prev, makeLog("success", "Workflow saved locally.")]);
  }

  async function executeSingleNode(node: WorkflowNode, approvalConfirmed: boolean, backendOutput?: Record<string, any>): Promise<boolean> {
    const start = Date.now();

    patchNode(node.id, {
      status: "running",
      progress: 5,
      elapsedMs: 0,
      error: undefined,
      outputText: undefined,
    });

    const timer = setInterval(() => {
      const elapsed = Date.now() - start;
      setNodes((prev) =>
        prev.map((n) =>
          n.id === node.id ? { ...n, elapsedMs: elapsed, progress: Math.min(92, n.progress + 2) } : n
        )
      );
    }, 300);

    try {
      if (node.kind === "image_generation") {
        if (!approvalConfirmed) {
          throw new Error("Human approval is required before any credit-spending image generation.");
        }

        const kind = "image" as const;
        setLogs((prev) => [...prev, makeLog("info", `Calling image generation endpoint for ${node.title}...`)]);

        const preparedPayload = (backendOutput?.generation_payload || {}) as Record<string, any>;
        const payload: Record<string, any> = {
          ...preparedPayload,
          prompt: String(preparedPayload.prompt || node.config?.prompt || goal),
          negative_prompt: String(preparedPayload.negative_prompt || node.config?.negative || "low quality, blurry"),
          width: Number(preparedPayload.width || node.config?.width || 768),
          height: Number(preparedPayload.height || node.config?.height || 768),
          node_id: node.id,
          source: "autonomous-platform",
        };

        const data = await callGeneration(payload);
        let assetUrl = extractAssetUrl(data);
        const generationId = extractGenerationId(data);

        if (!assetUrl && generationId) {
          patchNode(node.id, {
            outputText: `Generation queued. Waiting for preview from job ${generationId}...`,
          });
          setLogs((prev) => [...prev, makeLog("info", `${node.title} queued. Polling preview...`)]);
          const polled = await pollGenerationResult(generationId, { attempts: 30, delayMs: 2000 });
          assetUrl = polled.assetUrl;
        }

        const previewReady = Boolean(assetUrl);
        patchNode(node.id, {
          status: previewReady ? "success" : "warning",
          progress: 100,
          elapsedMs: Date.now() - start,
          previewUrl: assetUrl,
          previewType: kind,
          outputText: assetUrl
            ? "Image generated successfully."
            : generationId
            ? `Generation queued with ID ${generationId}. Preview is still processing; check History shortly.`
            : "Generation request succeeded, but no preview URL was returned by the backend.",
        });

        if (assetUrl) {
          setReviewState({ nodeId: node.id, title: node.title, kind, url: assetUrl });
        }

        setLogs((prev) => [
          ...prev,
          makeLog(
            previewReady ? "success" : "warning",
            `${node.title} ${previewReady ? "completed. Preview ready for user review." : "was queued, but the preview is not ready yet. Check History."}`
          ),
        ]);
      } else {
        if (!backendOutput) {
          throw new Error(`Backend semantic output is missing for ${node.title}.`);
        }
        const warning = backendOutput.status === "warning";
        const message =
          node.kind === "approval" && approvalConfirmed
            ? "Human approval confirmed before credit-spending actions."
            : String(backendOutput.message || `${node.title} completed.`);
        patchNode(node.id, {
          status: warning ? "warning" : "success",
          progress: 100,
          elapsedMs: Date.now() - start,
          outputText: message,
        });
        setLogs((prev) => [...prev, makeLog(warning ? "warning" : "success", `${node.title}: ${message}`)]);
      }
      return true;
    } catch (error: any) {
      patchNode(node.id, {
        status: "error",
        progress: 100,
        elapsedMs: Date.now() - start,
        error: error?.message || "Node execution failed.",
      });

      setLogs((prev) => [
        ...prev,
        makeLog("error", `${node.title}: ${error?.message || "failed"}`),
        ...(String(error?.message || "").toLowerCase().includes("invalid authentication credentials")
          ? [makeLog("warning", "Your login token is invalid or expired. Log out and sign in again, then rerun generation.")]
          : []),
      ]);
      return false;
    } finally {
      clearInterval(timer);
    }
  }

  async function executeWorkflow(approvalConfirmed: boolean) {
    setRunning(true);
    setReviewState(null);
    setPendingApproval(false);
    setLogs([makeLog("info", "Starting validated image-first workflow...")]);
    setNodes((prev) =>
      prev.map((n) => ({
        ...n,
        status: "idle",
        progress: 0,
        elapsedMs: 0,
        error: undefined,
        previewUrl: undefined,
        outputText: undefined,
      }))
    );

    try {
      const ordered = topoSort(nodes, edges);
      const preflight = await runAutonomousPlatform({ title, goal, nodes, edges });
      const backendLogs = Array.isArray((preflight as any)?.logs) ? (preflight as any).logs : [];
      const backendOutputs = ((preflight as any)?.node_outputs || {}) as Record<string, Record<string, any>>;
      setLastBackendOutputs(backendOutputs);
      const workflowMeta = (backendOutputs?.workflow_meta || {}) as Record<string, any>;
      if (typeof workflowMeta.estimated_credits === "number") setServerEstimatedCredits(workflowMeta.estimated_credits);
      setLogs((prev) => [...prev, ...backendLogs, makeLog("success", (preflight as any)?.summary || "Backend semantic preflight ready.")]);

      for (const node of ordered) {
        const ok = await executeSingleNode(node, approvalConfirmed, backendOutputs[node.id]);
        if (!ok) {
          setLogs((prev) => [...prev, makeLog("error", "Workflow stopped after a failed node. Fix the issue before rerunning.")]);
          return;
        }
      }

      setLogs((prev) => [...prev, makeLog("success", "Workflow execution finished without fabricated node results.")]);
    } catch (error: any) {
      setLogs((prev) => [...prev, makeLog("error", error?.message || "Workflow validation failed.")]);
    } finally {
      setRunning(false);
    }
  }

  async function requestRun() {
    if (running || regeneratingId !== null) return;
    setRunning(true);
    setPendingApproval(false);
    setLogs([makeLog("info", "Validating workflow graph and production semantics with the backend...")]);
    try {
      const planned = await planAutonomousPlatform({ title, goal, nodes, edges });
      const outputs = (planned?.node_outputs || {}) as Record<string, Record<string, any>>;
      const meta = (outputs?.workflow_meta || {}) as Record<string, any>;
      const credits = typeof meta.estimated_credits === "number" ? meta.estimated_credits : localEstimatedCredits;
      setServerEstimatedCredits(credits);
      setLastBackendOutputs(outputs);
      setLogs((prev) => [...prev, ...(planned.logs || []), makeLog("success", planned.summary || "Workflow validation ready.")]);
      if (Boolean(meta.requires_approval) || credits > 0) {
        setPendingApproval(true);
        setLogs((prev) => [...prev, makeLog("warning", `Human approval required before spending approximately ${credits} credits.`)]);
        return;
      }
    } catch (error: any) {
      setLogs((prev) => [...prev, makeLog("error", error?.message || "Workflow validation failed.")]);
      return;
    } finally {
      setRunning(false);
    }
    void executeWorkflow(false);
  }

  function approveAndRun() {
    if (running) return;
    void executeWorkflow(true);
  }

  function cancelRun() {
    setPendingApproval(false);
    setLogs((prev) => [...prev, makeLog("info", "Workflow run cancelled before generation. No credits were spent.")]);
  }

  async function regenerateReviewResult() {
    if (!reviewState) return;
    const node = nodes.find((n) => n.id === reviewState.nodeId);
    if (!node) return;

    setRegeneratingId(node.id);
    setLogs((prev) => [...prev, makeLog("info", `Review panel requested regeneration for ${node.title}...`)]);
    const approved = window.confirm("Regenerating creates a new image and spends credits. Continue?");
    if (!approved) {
      setLogs((prev) => [...prev, makeLog("info", "Regeneration cancelled. No credits were spent.")]);
      setRegeneratingId(null);
      return;
    }
    try {
      await executeSingleNode(node, true, lastBackendOutputs[node.id]);
    } finally {
      setRegeneratingId(null);
    }
  }

  function keepReviewResult() {
    if (!reviewState) return;
    setLogs((prev) => [...prev, makeLog("success", `User approved ${reviewState.kind} result from ${reviewState.title}.`)]);
    setReviewState(null);
  }

  function openPreview(node: WorkflowNode) {
    if (!node.previewUrl || !node.previewType) return;
    setReviewState({
      nodeId: node.id,
      title: node.title,
      kind: "image",
      url: node.previewUrl,
    });
  }

  return (
    <div className="human-made-screen relative min-h-[calc(100vh-120px)] overflow-hidden rounded-[32px] border border-white/10 bg-black/18 text-white shadow-[0_35px_160px_rgba(0,0,0,0.48)]">
      <OperatorPipelineBackdrop />
      <div className="pointer-events-none absolute inset-0 z-[1] bg-[radial-gradient(circle_at_20%_10%,rgba(34,211,238,0.10),transparent_30%),radial-gradient(circle_at_80%_18%,rgba(217,70,239,0.10),transparent_30%),linear-gradient(180deg,rgba(2,2,4,0.22),rgba(3,7,18,0.10)_50%,rgba(2,2,4,0.26))]" />

      <div className="relative z-10 flex min-h-[calc(100vh-120px)] flex-col">
        <header className="border-b border-white/10 bg-black/30 p-5 shadow-[0_22px_90px_rgba(0,0,0,0.28)] backdrop-blur-md">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/10 px-4 py-2 text-[11px] uppercase tracking-[0.26em] text-cyan-100">
                <BrainCircuit className="h-4 w-4" />
                Workflow Builder
              </div>
              <div className="mt-3 flex flex-col gap-3 lg:flex-row">
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full rounded-2xl border border-white/10 bg-black/[0.46] px-4 py-3 text-3xl font-black text-white outline-none lg:w-[560px]"
                />
                <input
                  value={goal}
                  onChange={(e) => setGoal(e.target.value)}
                  className="w-full rounded-2xl border border-white/10 bg-black/[0.46] px-4 py-3 text-sm text-white/85 outline-none lg:w-[560px]"
                />
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <FocusModeToggle className="h-[46px] rounded-2xl bg-cyan-300/10 px-5 text-sm" />
              <Link href="/dashboard" className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-black/[0.34] px-4 py-3 text-sm font-bold text-white/90 hover:bg-white/[0.08]">
                <ArrowLeft className="h-4 w-4" />
                Back to Dashboard
              </Link>
              <button onClick={save} className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-black/[0.34] px-4 py-3 text-sm font-bold text-white/90 hover:bg-white/[0.08]">
                <Save className="h-4 w-4" />
                Save
              </button>
              <button
                disabled={running || regeneratingId !== null}
                onClick={requestRun}
                className="inline-flex items-center gap-2 rounded-2xl bg-gradient-to-r from-fuchsia-600 to-cyan-500 px-5 py-3 text-sm font-black text-white shadow-[0_0_35px_rgba(34,211,238,0.20)] hover:brightness-110 disabled:opacity-60"
              >
                {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                {running ? "Running..." : hasCreditActions ? "Review & Run" : "Run Workflow"}
              </button>
            </div>
          </div>
        </header>


        {pendingApproval && (
          <div className="border-b border-amber-300/20 bg-amber-300/10 px-5 py-5 backdrop-blur-xl">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <div className="text-[11px] font-bold uppercase tracking-[0.24em] text-amber-100/75">Human approval required</div>
                <h3 className="mt-2 text-xl font-black text-white">Approve the credit-spending workflow before generation</h3>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-white/75">
                  This workflow contains image-generation nodes and may spend approximately {estimatedCredits} credits. Nothing has been queued yet.
                </p>
              </div>
              <div className="flex flex-wrap gap-3">
                <button onClick={cancelRun} className="rounded-2xl border border-red-300/20 bg-red-400/10 px-5 py-3 text-sm font-black text-red-100 hover:bg-red-400/15">
                  Cancel
                </button>
                <button onClick={approveAndRun} className="rounded-2xl bg-emerald-500 px-5 py-3 text-sm font-black text-white hover:brightness-110">
                  Approve & Run
                </button>
              </div>
            </div>
          </div>
        )}

        <ResultReviewPanel
          open={!!reviewState}
          title={reviewState?.title || "Generated result"}
          kind={reviewState?.kind || "image"}
          url={reviewState?.url || ""}
          busy={regeneratingId !== null}
          onKeep={keepReviewResult}
          onRegenerate={regenerateReviewResult}
          onClose={() => setReviewState(null)}
        />

        <div className="flex min-h-0 flex-1">
          <NodePalette onAdd={add} />
          <div className="flex min-w-0 flex-1 flex-col">
            <WorkflowCanvasPro
              nodes={nodes}
              edges={edges}
              selectedId={selectedId}
              selectedEdgeId={selectedEdgeId}
              connectingFrom={connectingFrom}
              onSelect={setSelectedId}
              onSelectEdge={setSelectedEdgeId}
              onNodeChange={updateNode}
              onConnectStart={(id) => {
                setConnectingFrom(id);
                setSelectedEdgeId(null);
              }}
              onConnectFinish={connect}
              onDeleteEdge={deleteEdge}
              onOpenPreview={openPreview}
            />
            <div className="border-t border-white/10 bg-black/[0.34] p-4">
              <ExecutionPanelPro logs={logs} />
            </div>
          </div>
          <InspectorPro node={selected} onChange={updateNode} onDelete={remove} onDuplicate={duplicate} />
        </div>
      </div>
    </div>
  );
}
