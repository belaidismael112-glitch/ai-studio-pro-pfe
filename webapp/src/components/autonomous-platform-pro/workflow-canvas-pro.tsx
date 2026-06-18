"use client";

import { LocateFixed, Minus, Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import WorkflowNodeCard from "./workflow-node-card";
import type { WorkflowEdge, WorkflowNode } from "./types";

type Props = {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  selectedId: string | null;
  selectedEdgeId: string | null;
  connectingFrom: string | null;
  onSelect: (id: string | null) => void;
  onSelectEdge: (id: string | null) => void;
  onNodeChange: (node: WorkflowNode) => void;
  onConnectStart: (id: string | null) => void;
  onConnectFinish: (id: string) => void;
  onDeleteEdge: (id: string) => void;
  onOpenPreview?: (node: WorkflowNode) => void;
};

type Point = { x: number; y: number };

const CANVAS_WIDTH = 3400;
const CANVAS_HEIGHT = 2200;
const HANDLE_Y = 86;

function isInteractiveElement(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false;
  return !!target.closest("button,a,input,textarea,select,video,[data-no-drag='true']");
}

export default function WorkflowCanvasPro({
  nodes,
  edges,
  selectedId,
  selectedEdgeId,
  connectingFrom,
  onSelect,
  onSelectEdge,
  onNodeChange,
  onConnectStart,
  onConnectFinish,
  onDeleteEdge,
  onOpenPreview,
}: Props) {
  const [zoom, setZoom] = useState(0.78);
  const [pan, setPan] = useState<Point>({ x: 0, y: 0 });
  const [draggingNode, setDraggingNode] = useState<{ id: string; dx: number; dy: number } | null>(null);
  const [panning, setPanning] = useState<{ sx: number; sy: number; px: number; py: number } | null>(null);
  const [connectionMouse, setConnectionMouse] = useState<Point | null>(null);

  const viewportRef = useRef<HTMLDivElement>(null);
  const activePointerIdRef = useRef<number | null>(null);

  const zoomRef = useRef(zoom);
  const panRef = useRef(pan);
  const nodesRef = useRef(nodes);
  const draggingNodeRef = useRef(draggingNode);
  const panningRef = useRef(panning);
  const connectingFromRef = useRef(connectingFrom);

  const nodeMap = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);

  const stopDragAndPan = useCallback(() => {
    draggingNodeRef.current = null;
    panningRef.current = null;
    activePointerIdRef.current = null;
    setDraggingNode(null);
    setPanning(null);
    document.body.style.userSelect = "";
    document.body.style.cursor = "";
  }, []);

  useEffect(() => {
    zoomRef.current = zoom;
    panRef.current = pan;
    nodesRef.current = nodes;
    draggingNodeRef.current = draggingNode;
    panningRef.current = panning;
    connectingFromRef.current = connectingFrom;
  }, [zoom, pan, nodes, draggingNode, panning, connectingFrom]);

  const viewportPointFromClient = useCallback((clientX: number, clientY: number): Point => {
    const rect = viewportRef.current?.getBoundingClientRect();
    return {
      x: clientX - (rect?.left || 0),
      y: clientY - (rect?.top || 0),
    };
  }, []);

  const screenToWorldFromClient = useCallback((clientX: number, clientY: number): Point => {
    const p = viewportPointFromClient(clientX, clientY);
    return {
      x: (p.x - panRef.current.x) / zoomRef.current,
      y: (p.y - panRef.current.y) / zoomRef.current,
    };
  }, [viewportPointFromClient]);

  useEffect(() => {
    function onWindowPointerMove(event: PointerEvent) {
      const currentDrag = draggingNodeRef.current;
      const currentPan = panningRef.current;
      const currentConnecting = connectingFromRef.current;

      /*
        IMPORTANT FIX:
        If the browser misses pointerup, pointermove still fires but event.buttons becomes 0.
        That was the reason the node stayed stuck to the cursor.
      */
      if ((currentDrag || currentPan) && event.buttons !== 1) {
        stopDragAndPan();
        return;
      }

      if (currentDrag) {
        event.preventDefault();

        const node = nodesRef.current.find((n) => n.id === currentDrag.id);
        if (!node) {
          stopDragAndPan();
          return;
        }

        const world = screenToWorldFromClient(event.clientX, event.clientY);

        onNodeChange({
          ...node,
          x: Math.max(20, Math.min(CANVAS_WIDTH - node.width - 20, world.x - currentDrag.dx)),
          y: Math.max(20, Math.min(CANVAS_HEIGHT - 120, world.y - currentDrag.dy)),
        });

        return;
      }

      if (currentPan) {
        event.preventDefault();

        const nextPan = {
          x: currentPan.px + (event.clientX - currentPan.sx),
          y: currentPan.py + (event.clientY - currentPan.sy),
        };

        panRef.current = nextPan;
        setPan(nextPan);
        return;
      }

      if (currentConnecting) {
        setConnectionMouse(screenToWorldFromClient(event.clientX, event.clientY));
      }
    }

    function onWindowPointerUp() {
      stopDragAndPan();
    }

    function onWindowMouseUp() {
      stopDragAndPan();
    }

    function onWindowBlur() {
      stopDragAndPan();
      onConnectStart(null);
      setConnectionMouse(null);
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        stopDragAndPan();
        onConnectStart(null);
        setConnectionMouse(null);
        onSelectEdge(null);
      }

      if ((event.key === "Delete" || event.key === "Backspace") && selectedEdgeId) {
        event.preventDefault();
        onDeleteEdge(selectedEdgeId);
      }
    }

    window.addEventListener("pointermove", onWindowPointerMove, { passive: false });
    window.addEventListener("pointerup", onWindowPointerUp, true);
    window.addEventListener("pointercancel", onWindowPointerUp, true);
    window.addEventListener("mouseup", onWindowMouseUp, true);
    window.addEventListener("blur", onWindowBlur);
    window.addEventListener("keydown", onKeyDown);

    return () => {
      window.removeEventListener("pointermove", onWindowPointerMove);
      window.removeEventListener("pointerup", onWindowPointerUp, true);
      window.removeEventListener("pointercancel", onWindowPointerUp, true);
      window.removeEventListener("mouseup", onWindowMouseUp, true);
      window.removeEventListener("blur", onWindowBlur);
      window.removeEventListener("keydown", onKeyDown);
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
    };
  }, [onConnectStart, onDeleteEdge, onNodeChange, onSelectEdge, screenToWorldFromClient, selectedEdgeId, stopDragAndPan]);

  function clampZoom(next: number) {
    return Math.max(0.35, Math.min(1.8, next));
  }

  function viewportPoint(event: React.PointerEvent | React.WheelEvent): Point {
    return viewportPointFromClient(event.clientX, event.clientY);
  }

  function screenToWorld(event: React.PointerEvent | React.WheelEvent): Point {
    return screenToWorldFromClient(event.clientX, event.clientY);
  }

  function startNodeDrag(event: React.PointerEvent, node: WorkflowNode) {
    event.stopPropagation();

    if (event.button !== 0) return;

    if (isInteractiveElement(event.target)) {
      onSelect(node.id);
      onSelectEdge(null);
      return;
    }

    if (connectingFrom) {
      finishConnection(node.id);
      return;
    }

    const world = screenToWorld(event);
    const dragState = { id: node.id, dx: world.x - node.x, dy: world.y - node.y };

    activePointerIdRef.current = event.pointerId;
    draggingNodeRef.current = dragState;
    setDraggingNode(dragState);

    document.body.style.userSelect = "none";
    document.body.style.cursor = "move";

    onSelect(node.id);
    onSelectEdge(null);
  }

  function startCanvasPan(event: React.PointerEvent) {
    if (event.button !== 0 && event.button !== 1) return;
    if (connectingFrom) return;
    if (isInteractiveElement(event.target)) return;

    const panState = {
      sx: event.clientX,
      sy: event.clientY,
      px: panRef.current.x,
      py: panRef.current.y,
    };

    activePointerIdRef.current = event.pointerId;
    panningRef.current = panState;
    setPanning(panState);

    document.body.style.userSelect = "none";
    document.body.style.cursor = "grabbing";

    onSelect(null);
    onSelectEdge(null);
  }

  function onWheel(event: React.WheelEvent) {
    event.preventDefault();

    const oldZoom = zoomRef.current;
    const nextZoom = clampZoom(oldZoom + (event.deltaY > 0 ? -0.08 : 0.08));
    const mouse = viewportPoint(event);
    const worldBefore = {
      x: (mouse.x - panRef.current.x) / oldZoom,
      y: (mouse.y - panRef.current.y) / oldZoom,
    };

    zoomRef.current = nextZoom;

    const nextPan = {
      x: mouse.x - worldBefore.x * nextZoom,
      y: mouse.y - worldBefore.y * nextZoom,
    };

    panRef.current = nextPan;
    setZoom(nextZoom);
    setPan(nextPan);
  }

  function resetView() {
    zoomRef.current = 0.78;
    panRef.current = { x: 0, y: 0 };
    setZoom(0.78);
    setPan({ x: 0, y: 0 });
    stopDragAndPan();
  }

  function zoomBy(delta: number) {
    setZoom((current) => {
      const next = clampZoom(current + delta);
      zoomRef.current = next;
      return next;
    });
  }

  function startConnection(event: React.PointerEvent, nodeId: string) {
    event.stopPropagation();
    stopDragAndPan();

    onConnectStart(nodeId);
    onSelectEdge(null);
    setConnectionMouse(screenToWorld(event));
  }

  function finishConnection(targetId: string) {
    if (!connectingFrom || connectingFrom === targetId) return;
    onConnectFinish(targetId);
    setConnectionMouse(null);
  }

  function edgePath(from: WorkflowNode, to: WorkflowNode) {
    const x1 = from.x + from.width + 12;
    const y1 = from.y + HANDLE_Y;
    const x2 = to.x - 12;
    const y2 = to.y + HANDLE_Y;
    const c = Math.max(120, Math.abs(x2 - x1) * 0.42);
    return `M ${x1} ${y1} C ${x1 + c} ${y1}, ${x2 - c} ${y2}, ${x2} ${y2}`;
  }

  function edgeMidPoint(from: WorkflowNode, to: WorkflowNode) {
    return { x: (from.x + from.width + to.x) / 2, y: (from.y + to.y) / 2 + HANDLE_Y };
  }

  function connectionTempPath() {
    if (!connectingFrom || !connectionMouse) return null;
    const from = nodeMap.get(connectingFrom);
    if (!from) return null;

    const x1 = from.x + from.width + 12;
    const y1 = from.y + HANDLE_Y;
    const x2 = connectionMouse.x;
    const y2 = connectionMouse.y;
    const c = Math.max(100, Math.abs(x2 - x1) * 0.38);

    return `M ${x1} ${y1} C ${x1 + c} ${y1}, ${x2 - c} ${y2}, ${x2} ${y2}`;
  }

  return (
    <div className="relative h-full min-h-[650px] flex-1 overflow-hidden">
      <div className="absolute left-5 top-5 z-30 flex items-center gap-2 rounded-2xl border border-white/10 bg-black/60 p-2 backdrop-blur-xl">
        <button onClick={() => zoomBy(-0.08)} className="rounded-xl p-2 text-white/65 hover:bg-white/10" title="Zoom out">
          <Minus className="h-4 w-4" />
        </button>
        <span className="min-w-16 text-center text-xs font-bold text-white/70">{Math.round(zoom * 100)}%</span>
        <button onClick={() => zoomBy(0.08)} className="rounded-xl p-2 text-white/65 hover:bg-white/10" title="Zoom in">
          <Plus className="h-4 w-4" />
        </button>
        <button onClick={resetView} className="rounded-xl p-2 text-white/65 hover:bg-white/10" title="Reset view">
          <LocateFixed className="h-4 w-4" />
        </button>
      </div>

      {connectingFrom && (
        <div className="absolute right-5 top-5 z-30 rounded-2xl border border-cyan-300/20 bg-cyan-300/10 px-4 py-3 text-sm font-bold text-cyan-100">
          Drag to another node input. Escape cancels.
        </div>
      )}

      {selectedEdgeId && (
        <button
          onClick={() => onDeleteEdge(selectedEdgeId)}
          className="absolute right-5 top-20 z-30 inline-flex items-center gap-2 rounded-2xl border border-red-400/20 bg-red-500/15 px-4 py-3 text-sm font-bold text-red-100 backdrop-blur-xl hover:bg-red-500/25"
        >
          <Trash2 className="h-4 w-4" />
          Delete selected arrow
        </button>
      )}

      <div
        ref={viewportRef}
        onPointerDown={startCanvasPan}
        onPointerUp={stopDragAndPan}
        onPointerCancel={stopDragAndPan}
        onWheel={onWheel}
        className={`absolute inset-0 overflow-hidden ${
          panning ? "cursor-grabbing" : connectingFrom ? "cursor-crosshair" : draggingNode ? "cursor-move" : "cursor-grab"
        }`}
        style={{ touchAction: "none" }}
      >
        <div
          className="absolute left-0 top-0 origin-top-left"
          style={{
            width: CANVAS_WIDTH,
            height: CANVAS_HEIGHT,
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            backgroundImage:
              "radial-gradient(circle at 1px 1px, rgba(255,255,255,0.12) 1px, transparent 0), linear-gradient(rgba(255,255,255,0.055) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.055) 1px, transparent 1px)",
            backgroundSize: "28px 28px, 56px 56px, 56px 56px",
          }}
        >
          <svg className="absolute inset-0 h-full w-full">
            <defs>
              <marker id="arrowhead" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto">
                <path d="M 0 0 L 12 6 L 0 12 z" fill="#67e8f9" opacity="0.88" />
              </marker>
              <marker id="arrowheadSelected" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto">
                <path d="M 0 0 L 12 6 L 0 12 z" fill="#f0abfc" opacity="1" />
              </marker>
              <linearGradient id="flowLine" x1="0" x2="1" y1="0" y2="0">
                <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.9" />
                <stop offset="100%" stopColor="#d946ef" stopOpacity="0.9" />
              </linearGradient>
            </defs>

            {edges.map((edge) => {
              const from = nodeMap.get(edge.from);
              const to = nodeMap.get(edge.to);
              if (!from || !to) return null;

              const d = edgePath(from, to);
              const selected = selectedEdgeId === edge.id;

              return (
                <g key={edge.id}>
                  <path
                    d={d}
                    stroke="transparent"
                    strokeWidth="18"
                    fill="none"
                    className="cursor-pointer"
                    onPointerDown={(event) => {
                      event.stopPropagation();
                      stopDragAndPan();
                      onSelect(null);
                      onSelectEdge(edge.id);
                    }}
                  />
                  <path d={d} stroke={selected ? "#f0abfc" : "rgba(34,211,238,0.14)"} strokeWidth={selected ? "14" : "12"} fill="none" pointerEvents="none" />
                  <path d={d} stroke={selected ? "#f0abfc" : "url(#flowLine)"} strokeWidth={selected ? "4" : "3"} fill="none" markerEnd={selected ? "url(#arrowheadSelected)" : "url(#arrowhead)"} pointerEvents="none" />
                </g>
              );
            })}

            {connectionTempPath() && (
              <path d={connectionTempPath() || ""} stroke="#67e8f9" strokeWidth="3" strokeDasharray="8 8" fill="none" markerEnd="url(#arrowhead)" pointerEvents="none" />
            )}
          </svg>

          {edges.map((edge) => {
            if (edge.id !== selectedEdgeId) return null;
            const from = nodeMap.get(edge.from);
            const to = nodeMap.get(edge.to);
            if (!from || !to) return null;
            const mid = edgeMidPoint(from, to);

            return (
              <button
                key={`delete-${edge.id}`}
                data-no-drag="true"
                onPointerDown={(event) => event.stopPropagation()}
                onClick={(event) => {
                  event.stopPropagation();
                  stopDragAndPan();
                  onDeleteEdge(edge.id);
                }}
                className="absolute z-20 flex h-8 w-8 items-center justify-center rounded-full border border-red-300/30 bg-red-500/20 text-red-100 shadow-[0_0_24px_rgba(248,113,113,0.35)] hover:bg-red-500/35"
                style={{ left: mid.x - 16, top: mid.y - 16 }}
                title="Delete arrow"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            );
          })}

          {nodes.map((node) => (
            <WorkflowNodeCard
              key={node.id}
              node={node}
              selected={selectedId === node.id}
              connectingFrom={connectingFrom}
              onSelect={() => {
                stopDragAndPan();
                onSelect(node.id);
                onSelectEdge(null);
              }}
              onOpenPreview={onOpenPreview}
              onNodePointerDown={(event) => startNodeDrag(event, node)}
              onNodePointerUp={(event) => {
                event.stopPropagation();
                stopDragAndPan();
                if (connectingFrom && connectingFrom !== node.id) finishConnection(node.id);
              }}
              onOutputPointerDown={(event) => startConnection(event, node.id)}
              onInputPointerUp={(event) => {
                event.stopPropagation();
                stopDragAndPan();
                finishConnection(node.id);
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
