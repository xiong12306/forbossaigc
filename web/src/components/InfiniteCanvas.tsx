import { useState, useRef, useCallback, useEffect, useMemo } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Type,
  Image as ImageIcon,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Wand2,
  X,
  StickyNote,
  Sparkles,
  Upload,
  ChevronDown,
  Loader2,
  Settings2,
  Check,
  Plus,
  MousePointer2,
  Hand,
} from "lucide-react";
import { uploadImage, canvasGenerate } from "@/api";

export type CanvasNodeType = "text" | "image" | "generated" | "sticky" | "generator";

export interface CanvasNode {
  id: string;
  type: CanvasNodeType;
  x: number;
  y: number;
  width: number;
  height: number;
  content: string;
  imageUrl?: string;
  title: string;
  model?: string;
  size?: string;
  preset?: string;
  generating?: boolean;
}

export interface CanvasConnection {
  id: string;
  from: string;
  to: string;
}

interface Point { x: number; y: number; }

interface ContextMenuState {
  visible: boolean;
  screenX: number;
  screenY: number;
  canvasX: number;
  canvasY: number;
}

interface DraggingConnection {
  fromId: string;
  fromPos: Point;
  currentPos: Point;
}

interface ResizeState {
  nodeId: string;
  handle: string;
  startX: number;
  startY: number;
  startNodeX: number;
  startNodeY: number;
  startW: number;
  startH: number;
}

interface DropdownPosition {
  x: number;
  y: number;
  width?: number;
}

const TITLE_HEIGHT = 32;
const MIN_SCALE = 0.2;
const MAX_SCALE = 3;
const MIN_NODE_W = 180;
const MIN_NODE_H = 120;

const MODELS = [
  { id: "modelscope", name: "Qwen-Image", desc: "通义万相", supported: true },
  { id: "nanobanana", name: "Nano Banana Pro", desc: "专业电商", supported: true },
];

const SIZES = [
  { id: "1:1", name: "1:1 方图", w: 1024, h: 1024 },
  { id: "3:4", name: "3:4 竖图", w: 768, h: 1024 },
  { id: "4:3", name: "4:3 横图", w: 1024, h: 768 },
  { id: "16:9", name: "16:9 宽屏", w: 1280, h: 720 },
  { id: "9:16", name: "9:16 竖屏", w: 720, h: 1280 },
  { id: "2k", name: "2K · 3:4", w: 1536, h: 2048 },
];

const PRESETS = [
  { id: "main", name: "商品主图" },
  { id: "detail", name: "详情图" },
  { id: "scene", name: "场景图" },
  { id: "poster", name: "营销海报" },
];

const NODE_LABELS: Record<CanvasNodeType, string> = {
  text: "文本",
  image: "图片",
  generated: "AI 生成",
  sticky: "便签",
  generator: "图片生成器",
};

const NODE_ICON: Record<CanvasNodeType, typeof Type> = {
  text: Type,
  image: ImageIcon,
  generated: Sparkles,
  sticky: StickyNote,
  generator: Wand2,
};

function buildBezierPath(from: Point, to: Point): string {
  const dx = Math.max(40, Math.abs(to.x - from.x) * 0.5);
  return `M ${from.x} ${from.y} C ${from.x + dx} ${from.y}, ${to.x - dx} ${to.y}, ${to.x} ${to.y}`;
}
function getOutputPoint(node: CanvasNode): Point {
  return { x: node.x + node.width, y: node.y + node.height / 2 };
}
function getInputPoint(node: CanvasNode): Point {
  return { x: node.x, y: node.y + node.height / 2 };
}
function genId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

const RESIZE_HANDLES = [
  { id: "nw", cursor: "nwse-resize", style: { left: -5, top: -5 } },
  { id: "n", cursor: "ns-resize", style: { left: "50%", top: -5, transform: "translateX(-50%)" } },
  { id: "ne", cursor: "nesw-resize", style: { right: -5, top: -5 } },
  { id: "e", cursor: "ew-resize", style: { right: -5, top: "50%", transform: "translateY(-50%)" } },
  { id: "se", cursor: "nwse-resize", style: { right: -5, bottom: -5 } },
  { id: "s", cursor: "ns-resize", style: { left: "50%", bottom: -5, transform: "translateX(-50%)" } },
  { id: "sw", cursor: "nesw-resize", style: { left: -5, bottom: -5 } },
  { id: "w", cursor: "ew-resize", style: { left: -5, top: "50%", transform: "translateY(-50%)" } },
];

export default function InfiniteCanvas() {
  const [nodes, setNodes] = useState<CanvasNode[]>([]);
  const [connections, setConnections] = useState<CanvasConnection[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 60, y: 60 });
  const [isPanning, setIsPanning] = useState(false);
  const [isDraggingNode, setIsDraggingNode] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [nodeStart, setNodeStart] = useState({ x: 0, y: 0 });
  const [editingNodeId, setEditingNodeId] = useState<string | null>(null);
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({ visible: false, screenX: 0, screenY: 0, canvasX: 0, canvasY: 0 });
  const [draggingConnection, setDraggingConnection] = useState<DraggingConnection | null>(null);
  const draggingConnectionRef = useRef<DraggingConnection | null>(null);
  const [hoveredInputNodeId, setHoveredInputNodeId] = useState<string | null>(null);
  const [resizing, setResizing] = useState<ResizeState | null>(null);
  const [modelDropdownOpen, setModelDropdownOpen] = useState<string | null>(null);
  const [sizeDropdownOpen, setSizeDropdownOpen] = useState<string | null>(null);
  const [presetDropdownOpen, setPresetDropdownOpen] = useState<string | null>(null);
  const [modelDropdownPos, setModelDropdownPos] = useState<DropdownPosition>({ x: 0, y: 0 });
  const [sizeDropdownPos, setSizeDropdownPos] = useState<DropdownPosition>({ x: 0, y: 0 });
  const [presetDropdownPos, setPresetDropdownPos] = useState<DropdownPosition>({ x: 0, y: 0 });

  // @ 提及状态
  const [mentionState, setMentionState] = useState<{ generatorId: string; startPos: number; query: string; pos: { x: number; y: number } } | null>(null);
  const [mentionIndex, setMentionIndex] = useState(0);

  const canvasRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pendingImagePosRef = useRef<Point | null>(null);
  const promptTextareaRef = useRef<HTMLTextAreaElement | null>(null);

  const selectedNode = nodes.find(n => n.id === selectedNodeId) || null;

  // 缓存：nodeId → 上游节点列表，避免拖动时每帧重复计算
  const upstreamMap = useMemo(() => {
    const map: Record<string, CanvasNode[]> = {};
    for (const conn of connections) {
      const fromNode = nodes.find(n => n.id === conn.from);
      if (fromNode) {
        if (!map[conn.to]) map[conn.to] = [];
        map[conn.to].push(fromNode);
      }
    }
    return map;
  }, [connections, nodes]);

  // @ 提及候选节点
  const mentionCandidates = useMemo(() => {
    if (!mentionState) return [];
    const refs = upstreamMap[mentionState.generatorId] || [];
    const mentionedIds = refs.map(r => r.id);
    return nodes.filter(n =>
      n.id !== mentionState.generatorId &&
      !mentionedIds.includes(n.id) &&
      (n.type === "image" || n.type === "generated" || n.type === "text" || n.type === "sticky")
    ).filter(n => {
      if (!mentionState.query) return true;
      const q = mentionState.query.toLowerCase();
      return n.title.toLowerCase().includes(q) || n.content.toLowerCase().includes(q);
    });
  }, [mentionState, nodes, upstreamMap]);

  const handleSelectMention = useCallback((targetNode: CanvasNode) => {
    if (!mentionState) return;
    const genNodeId = mentionState.generatorId;
    const startPos = mentionState.startPos;
    const qLen = mentionState.query.length;
    const insertText = `@${targetNode.title} `;

    setNodes(prev => {
      const gen = prev.find(n => n.id === genNodeId);
      if (!gen) return prev;
      const before = gen.content.slice(0, startPos);
      const after = gen.content.slice(startPos + qLen + 1);
      return prev.map(n => n.id === genNodeId ? { ...n, content: before + insertText + after } : n);
    });
    setConnections(prev => {
      const exists = prev.some(c => c.from === targetNode.id && c.to === genNodeId);
      if (exists) return prev;
      return [...prev, { id: genId("conn"), from: targetNode.id, to: genNodeId }];
    });
    setMentionState(null);
    setTimeout(() => {
      const newCaret = startPos + insertText.length;
      promptTextareaRef.current?.focus();
      promptTextareaRef.current?.setSelectionRange(newCaret, newCaret);
    }, 0);
  }, [mentionState]);

  const screenToCanvas = useCallback((screenX: number, screenY: number): Point => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return { x: (screenX - rect.left - offset.x) / scale, y: (screenY - rect.top - offset.y) / scale };
  }, [offset, scale]);

  const viewportCenterCanvas = useCallback((): Point => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return { x: (rect.width / 2 - offset.x) / scale, y: (rect.height / 2 - offset.y) / scale };
  }, [offset, scale]);

  const getDropdownPos = useCallback((e: React.MouseEvent<HTMLElement>): DropdownPosition => {
    const rect = e.currentTarget.getBoundingClientRect();
    return { x: rect.left, y: rect.bottom + 4, width: rect.width };
  }, []);

  const closeAllDropdowns = useCallback(() => {
    setModelDropdownOpen(null);
    setSizeDropdownOpen(null);
    setPresetDropdownOpen(null);
  }, []);

  const createNode = useCallback((type: CanvasNodeType, pos: Point) => {
    let node: CanvasNode;
    switch (type) {
      case "text":
        node = { id: genId("text"), type, x: pos.x, y: pos.y, width: 240, height: 140, content: "", title: "文本" };
        break;
      case "sticky":
        node = { id: genId("sticky"), type, x: pos.x, y: pos.y, width: 200, height: 160, content: "", title: "便签" };
        break;
      case "image":
        pendingImagePosRef.current = pos;
        fileInputRef.current?.click();
        return;
      case "generator":
        node = {
          id: genId("gen"), type, x: pos.x, y: pos.y, width: 340, height: 440,
          content: "", title: "图片生成器", model: "modelscope", size: "1:1", preset: "main", generating: false,
        };
        break;
      default:
        return;
    }
    setNodes(prev => [...prev, node]);
    setSelectedNodeId(node.id);
    if (type === "text" || type === "sticky") {
      setTimeout(() => setEditingNodeId(node.id), 60);
    }
  }, []);

  const createImageNodeAt = useCallback(async (file: File, pos: Point) => {
    try {
      const url = await uploadImage(file);
      const img = new Image();
      const finish = (w: number, h: number) => {
        const node: CanvasNode = {
          id: genId("img"), type: "image", x: pos.x, y: pos.y,
          width: w, height: h + TITLE_HEIGHT, content: file.name || "参考图片", imageUrl: url, title: "图片",
        };
        setNodes(prev => [...prev, node]);
        setSelectedNodeId(node.id);
      };
      img.onload = () => {
        const maxW = 280;
        const ratio = img.width / img.height || 1;
        const w = Math.min(maxW, img.width || maxW);
        finish(w, w / ratio);
      };
      img.onerror = () => finish(240, 200);
      img.src = url;
    } catch (err) {
      console.error("上传失败", err);
      alert("图片上传失败，请重试");
    }
  }, []);

  const handleFileUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const pos = pendingImagePosRef.current ?? viewportCenterCanvas();
    pendingImagePosRef.current = null;
    void createImageNodeAt(file, pos);
    e.target.value = "";
  }, [createImageNodeAt, viewportCenterCanvas]);

  const deleteNode = useCallback((id: string) => {
    setNodes(prev => prev.filter(n => n.id !== id));
    setConnections(prev => prev.filter(c => c.from !== id && c.to !== id));
    if (selectedNodeId === id) setSelectedNodeId(null);
    if (editingNodeId === id) setEditingNodeId(null);
    closeAllDropdowns();
  }, [selectedNodeId, editingNodeId, closeAllDropdowns]);

  const deleteConnection = useCallback((id: string) => {
    setConnections(prev => prev.filter(c => c.id !== id));
  }, []);

  const updateNode = useCallback((id: string, patch: Partial<CanvasNode>) => {
    setNodes(prev => prev.map(n => n.id === id ? { ...n, ...patch } : n));
  }, []);

  const updateNodeText = useCallback((id: string, text: string) => {
    updateNode(id, { content: text });
  }, [updateNode]);

  const closeContextMenu = useCallback(() => {
    setContextMenu(prev => prev.visible ? { ...prev, visible: false } : prev);
  }, []);

  const handleCanvasMouseDown = useCallback((e: React.MouseEvent) => {
    if (draggingConnection || resizing) return;
    const target = e.target as HTMLElement;
    if (target === canvasRef.current || target.classList.contains("canvas-bg")) {
      setIsPanning(true);
      setDragStart({ x: e.clientX - offset.x, y: e.clientY - offset.y });
      setSelectedNodeId(null);
      setEditingNodeId(null);
      closeContextMenu();
      closeAllDropdowns();
    }
  }, [offset, draggingConnection, resizing, closeContextMenu, closeAllDropdowns]);

  const handleNodeMouseDown = useCallback((e: React.MouseEvent, node: CanvasNode) => {
    if (draggingConnection || resizing) return;
    if (editingNodeId === node.id) return;
    const target = e.target as HTMLElement;
    if (target.closest(".no-drag")) return;
    e.stopPropagation();
    setIsDraggingNode(true);
    setDragStart({ x: e.clientX, y: e.clientY });
    setNodeStart({ x: node.x, y: node.y });
    setSelectedNodeId(node.id);
    closeContextMenu();
    closeAllDropdowns();
  }, [editingNodeId, draggingConnection, resizing, closeContextMenu, closeAllDropdowns]);

  const startResize = useCallback((e: React.MouseEvent, nodeId: string, handle: string) => {
    e.stopPropagation();
    e.preventDefault();
    const node = nodes.find(n => n.id === nodeId);
    if (!node) return;
    setResizing({
      nodeId, handle,
      startX: e.clientX, startY: e.clientY,
      startNodeX: node.x, startNodeY: node.y,
      startW: node.width, startH: node.height,
    });
    setSelectedNodeId(nodeId);
  }, [nodes]);

  // 拖拽节流：用 rAF 合并连续 mousemove，避免每帧多次 setState
  const rafRef = useRef<number | null>(null);
  const lastMoveRef = useRef<{ clientX: number; clientY: number } | null>(null);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    lastMoveRef.current = { clientX: e.clientX, clientY: e.clientY };
    if (rafRef.current !== null) return;

    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = null;
      const mv = lastMoveRef.current;
      if (!mv) return;

      if (resizing) {
        const dx = (mv.clientX - resizing.startX) / scale;
        const dy = (mv.clientY - resizing.startY) / scale;
        let newX = resizing.startNodeX;
        let newY = resizing.startNodeY;
        let newW = resizing.startW;
        let newH = resizing.startH;

        if (resizing.handle.includes("e")) newW = Math.max(MIN_NODE_W, resizing.startW + dx);
        if (resizing.handle.includes("w")) { newW = Math.max(MIN_NODE_W, resizing.startW - dx); newX = resizing.startNodeX + (resizing.startW - newW); }
        if (resizing.handle.includes("s")) newH = Math.max(MIN_NODE_H, resizing.startH + dy);
        if (resizing.handle.includes("n")) { newH = Math.max(MIN_NODE_H, resizing.startH - dy); newY = resizing.startNodeY + (resizing.startH - newH); }

        setNodes(prev => prev.map(n => n.id === resizing.nodeId ? { ...n, x: newX, y: newY, width: newW, height: newH } : n));
        return;
      }
      if (draggingConnection || draggingConnectionRef.current) {
        const pos = screenToCanvas(mv.clientX, mv.clientY);
        setDraggingConnection(prev => {
          if (!prev) return prev;
          const updated = { ...prev, currentPos: pos };
          draggingConnectionRef.current = updated;
          return updated;
        });
        // 检测鼠标当前悬停在哪个节点上（用于任意区域连接）
        const fromId = draggingConnectionRef.current?.fromId;
        let hitId: string | null = null;
        for (let i = nodes.length - 1; i >= 0; i--) {
          const n = nodes[i];
          if (n.id === fromId) continue;
          if (pos.x >= n.x && pos.x <= n.x + n.width && pos.y >= n.y && pos.y <= n.y + n.height) {
            hitId = n.id;
            break;
          }
        }
        if (hitId !== hoveredInputNodeId) {
          setHoveredInputNodeId(hitId);
        }
        return;
      }
      if (isPanning) {
        setOffset({ x: mv.clientX - dragStart.x, y: mv.clientY - dragStart.y });
      } else if (isDraggingNode && selectedNodeId) {
        const dx = (mv.clientX - dragStart.x) / scale;
        const dy = (mv.clientY - dragStart.y) / scale;
        setNodes(prev => prev.map(n => n.id === selectedNodeId ? { ...n, x: nodeStart.x + dx, y: nodeStart.y + dy } : n));
      }
    });
  }, [resizing, draggingConnection, isPanning, isDraggingNode, dragStart, nodeStart, scale, selectedNodeId, screenToCanvas, nodes, hoveredInputNodeId]);

  const handleMouseUp = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    setIsPanning(false);
    setIsDraggingNode(false);
    setResizing(null);
    if (draggingConnectionRef.current) {
      const conn = draggingConnectionRef.current;
      // 如果在某个节点上释放鼠标，完成连线
      if (hoveredInputNodeId && hoveredInputNodeId !== conn.fromId) {
        const exists = connections.some(c => c.from === conn.fromId && c.to === hoveredInputNodeId);
        if (!exists) {
          setConnections(prev => [...prev, { id: genId("conn"), from: conn.fromId, to: hoveredInputNodeId }]);
        }
      }
      draggingConnectionRef.current = null;
      setDraggingConnection(null);
      setHoveredInputNodeId(null);
    }
  }, [hoveredInputNodeId, connections]);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    const newScale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, scale * delta));
    const rect = canvasRef.current?.getBoundingClientRect();
    if (rect) {
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;
      setOffset({
        x: mouseX - (mouseX - offset.x) * (newScale / scale),
        y: mouseY - (mouseY - offset.y) * (newScale / scale),
      });
    }
    setScale(newScale);
  }, [scale, offset]);

  const resetView = useCallback(() => {
    setScale(1);
    setOffset({ x: 60, y: 60 });
  }, []);

  const startConnection = useCallback((e: React.MouseEvent, node: CanvasNode) => {
    e.stopPropagation();
    e.preventDefault();
    const fromPos = getOutputPoint(node);
    const conn: DraggingConnection = { fromId: node.id, fromPos, currentPos: { ...fromPos } };
    draggingConnectionRef.current = conn;
    setDraggingConnection(conn);
    setHoveredInputNodeId(null);
  }, []);

  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const canvasPos = screenToCanvas(e.clientX, e.clientY);
    setContextMenu({ visible: true, screenX: e.clientX, screenY: e.clientY, canvasX: canvasPos.x, canvasY: canvasPos.y });
    setSelectedNodeId(null);
    setEditingNodeId(null);
  }, [screenToCanvas]);

  useEffect(() => {
    if (!contextMenu.visible) return;
    const handleClose = () => closeContextMenu();
    const handleEsc = (e: KeyboardEvent) => { if (e.key === "Escape") { closeContextMenu(); closeAllDropdowns(); } };
    window.addEventListener("click", handleClose);
    window.addEventListener("keydown", handleEsc);
    return () => { window.removeEventListener("click", handleClose); window.removeEventListener("keydown", handleEsc); };
  }, [contextMenu.visible, closeContextMenu, closeAllDropdowns]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest(".no-drag")) {
        closeAllDropdowns();
      }
    };
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeAllDropdowns();
    };
    if (modelDropdownOpen || sizeDropdownOpen || presetDropdownOpen) {
      setTimeout(() => window.addEventListener("click", handleClickOutside), 0);
      window.addEventListener("keydown", handleEsc);
    }
    return () => {
      window.removeEventListener("click", handleClickOutside);
      window.removeEventListener("keydown", handleEsc);
    };
  }, [modelDropdownOpen, sizeDropdownOpen, presetDropdownOpen, closeAllDropdowns]);

  useEffect(() => {
    const handleGlobalMouseUp = () => {
      setIsPanning(false); setIsDraggingNode(false); setResizing(null);
    };
    window.addEventListener("mouseup", handleGlobalMouseUp);
    return () => window.removeEventListener("mouseup", handleGlobalMouseUp);
  }, []);

  const upstreamNodesOf = useCallback((nodeId: string): CanvasNode[] => {
    return upstreamMap[nodeId] || [];
  }, [upstreamMap]);

  const executeGenerator = useCallback(async (nodeId: string) => {
    const node = nodes.find(n => n.id === nodeId);
    if (!node || node.generating) return;

    const refs = upstreamNodesOf(nodeId);
    const referenceTexts = refs
      .filter(n => n.type === "text" || n.type === "sticky")
      .map(n => n.content)
      .filter(Boolean);
    const referenceImages = refs
      .filter(n => (n.type === "image" || n.type === "generated") && n.imageUrl)
      .map(n => n.imageUrl!)
      .filter(Boolean);

    updateNode(nodeId, { generating: true });
    try {
      const res = await canvasGenerate({
        prompt: node.content,
        reference_texts: referenceTexts,
        reference_images: referenceImages,
        model: node.model,
        size: node.size,
        preset: node.preset,
      });
      if (res.image_url) {
        updateNode(nodeId, {
          imageUrl: res.image_url,
          type: "generated",
          generating: false,
          title: "AI 生成",
        });
      } else {
        updateNode(nodeId, { generating: false });
        alert("未生成图片，请重试");
      }
    } catch (err) {
      console.error("生成失败", err);
      updateNode(nodeId, { generating: false });
      alert(err instanceof Error ? err.message : "生成失败，请重试");
    }
  }, [nodes, upstreamNodesOf, updateNode]);

  const getNodeColors = (type: CanvasNodeType) => {
    switch (type) {
      case "text": return { accent: "text-blue-600", titleBg: "bg-white border-b border-slate-200", bodyBg: "bg-white", border: "border-slate-300", text: "text-slate-800", placeholder: "placeholder:text-slate-400" };
      case "image": return { accent: "text-emerald-600", titleBg: "bg-white border-b border-slate-200", bodyBg: "bg-slate-50", border: "border-slate-300", text: "text-slate-800", placeholder: "placeholder:text-slate-400" };
      case "generated": return { accent: "text-violet-600", titleBg: "bg-gradient-to-r from-violet-50 to-indigo-50 border-b border-violet-200", bodyBg: "bg-white", border: "border-violet-300", text: "text-slate-800", placeholder: "placeholder:text-slate-400" };
      case "sticky": return { accent: "text-amber-700", titleBg: "bg-amber-100 border-b border-amber-200", bodyBg: "bg-amber-50", border: "border-amber-300", text: "text-amber-900", placeholder: "placeholder:text-amber-600" };
      case "generator": return { accent: "text-white", titleBg: "bg-gradient-to-r from-indigo-500 via-blue-500 to-cyan-500", bodyBg: "bg-white", border: "border-blue-400", text: "text-slate-800", placeholder: "placeholder:text-slate-400" };
    }
  };

  const renderGeneratorNode = (node: CanvasNode, colors: ReturnType<typeof getNodeColors>) => {
    const currentModel = MODELS.find(m => m.id === node.model) || MODELS[0];
    const currentSize = SIZES.find(s => s.id === node.size) || SIZES[0];
    const currentPreset = PRESETS.find(p => p.id === node.preset) || PRESETS[0];
    const contentH = node.height - TITLE_HEIGHT;
    const showImage = !!node.imageUrl;

    const refs = upstreamNodesOf(node.id);
    const refImages = refs.filter(n => (n.type === "image" || n.type === "generated") && n.imageUrl);
    const refTexts = refs.filter(n => (n.type === "text" || n.type === "sticky") && n.content.trim());
    const hasRefs = refImages.length > 0 || refTexts.length > 0;

    const openModelDropdown = (e: React.MouseEvent<HTMLElement>) => {
      e.stopPropagation();
      const pos = getDropdownPos(e);
      setModelDropdownPos(pos);
      setSizeDropdownOpen(null);
      setPresetDropdownOpen(null);
      setModelDropdownOpen(modelDropdownOpen === node.id ? null : node.id);
    };

    const openSizeDropdown = (e: React.MouseEvent<HTMLElement>) => {
      e.stopPropagation();
      const pos = getDropdownPos(e);
      setSizeDropdownPos(pos);
      setModelDropdownOpen(null);
      setPresetDropdownOpen(null);
      setSizeDropdownOpen(sizeDropdownOpen === node.id ? null : node.id);
    };

    const openPresetDropdown = (e: React.MouseEvent<HTMLElement>) => {
      e.stopPropagation();
      const pos = getDropdownPos(e);
      setPresetDropdownPos(pos);
      setModelDropdownOpen(null);
      setSizeDropdownOpen(null);
      setPresetDropdownOpen(presetDropdownOpen === node.id ? null : node.id);
    };

    const removeConnection = (fromId: string) => {
      setConnections(prev => prev.filter(c => !(c.from === fromId && c.to === node.id)));
    };

    const handlePromptChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const val = e.target.value;
      updateNodeText(node.id, val);
      const ta = e.target;
      const caret = ta.selectionStart;
      const beforeCaret = val.slice(0, caret);
      const atMatch = beforeCaret.match(/@(\S*)$/);
      if (atMatch) {
        const startPos = caret - atMatch[0].length;
        const taRect = ta.getBoundingClientRect();
        const lineHeight = 14;
        const linesBefore = beforeCaret.split("\n").length - 1;
        const charInLine = beforeCaret.lastIndexOf("\n") >= 0 ? caret - beforeCaret.lastIndexOf("\n") - 1 : caret;
        const charW = 6.5;
        const menuX = taRect.left + Math.min(charInLine * charW, taRect.width - 200);
        const menuY = taRect.top + 24 + linesBefore * lineHeight;
        setMentionState({ generatorId: node.id, startPos, query: atMatch[1], pos: { x: menuX, y: menuY } });
        setMentionIndex(0);
      } else {
        setMentionState(null);
      }
    };

    const handlePromptKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (!mentionState || mentionState.generatorId !== node.id || mentionCandidates.length === 0) {
        if (e.key === "Escape") setMentionState(null);
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setMentionIndex(i => (i + 1) % mentionCandidates.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setMentionIndex(i => (i - 1 + mentionCandidates.length) % mentionCandidates.length);
      } else if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        handleSelectMention(mentionCandidates[mentionIndex]);
      } else if (e.key === "Escape") {
        e.preventDefault();
        setMentionState(null);
      }
    };

    return (
      <>
        <div className={`relative w-full ${colors.bodyBg}`} style={{ height: contentH }}>
          {showImage ? (
            <>
              <img src={node.imageUrl} alt="" className="w-full h-full object-cover pointer-events-none" draggable={false} />
              <div className="absolute top-1.5 left-1.5 px-2 py-0.5 rounded-md bg-violet-500/90 text-[9px] text-white font-semibold tracking-wide backdrop-blur-sm">
                AI 生成
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); updateNode(node.id, { imageUrl: undefined, type: "generator", title: "图片生成器", generating: false }); }}
                className="absolute top-1.5 right-1.5 w-7 h-7 rounded-lg bg-black/60 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition no-drag backdrop-blur-sm hover:bg-black/80"
                title="重新设置"
              >
                <Settings2 className="w-3.5 h-3.5" />
              </button>
            </>
          ) : (
            <div className={`w-full h-full flex flex-col ${colors.bodyBg}`}>
              <div className="relative w-full bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center flex-shrink-0" style={{ height: Math.max(80, contentH * 0.28) }}>
                {node.generating ? (
                  <div className="flex flex-col items-center gap-2">
                    <div className="relative">
                      <div className="w-10 h-10 rounded-full border-2 border-blue-200" />
                      <Loader2 className="w-10 h-10 animate-spin absolute inset-0 text-blue-500" />
                    </div>
                    <span className="text-[11px] font-medium text-blue-600 tracking-wide">AI 创作中</span>
                  </div>
                ) : (
                  <>
                    <div className="flex flex-col items-center gap-1.5">
                      <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-blue-50 to-cyan-50 border border-blue-200 flex items-center justify-center">
                        <Wand2 className="w-5 h-5 text-blue-500" />
                      </div>
                      <span className="text-[10px] text-slate-400 tracking-wide">图片生成器</span>
                    </div>
                    <div className="absolute top-2 left-2 flex items-center gap-1">
                      <span className="px-1.5 py-0.5 rounded bg-white/80 text-[9px] text-slate-500 font-mono font-medium shadow-sm">{currentSize.id}</span>
                    </div>
                  </>
                )}
              </div>

              <div className="flex-1 flex flex-col p-2.5 gap-1.5 overflow-hidden no-drag">
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={openModelDropdown}
                    className="flex-1 flex items-center justify-between px-2.5 py-1.5 text-[11px] bg-white border border-slate-200 rounded-lg hover:border-blue-400 hover:bg-blue-50/30 transition text-slate-700 shadow-sm"
                  >
                    <span className="truncate font-medium">{currentModel.name}</span>
                    <ChevronDown className="w-3 h-3 flex-shrink-0 text-slate-400" />
                  </button>
                  <button
                    onClick={openSizeDropdown}
                    className="flex items-center gap-0.5 px-2.5 py-1.5 text-[11px] bg-white border border-slate-200 rounded-lg hover:border-blue-400 hover:bg-blue-50/30 transition text-slate-700 shadow-sm font-mono"
                  >
                    <span className="font-medium">{currentSize.id}</span>
                    <ChevronDown className="w-3 h-3 flex-shrink-0 text-slate-400" />
                  </button>
                </div>

                <button
                  onClick={openPresetDropdown}
                  className="flex items-center justify-between px-2.5 py-1.5 text-[11px] bg-white border border-slate-200 rounded-lg hover:border-blue-400 hover:bg-blue-50/30 transition text-slate-700 shadow-sm"
                >
                  <span className="flex items-center gap-1.5">
                    <Settings2 className="w-3 h-3 text-slate-400" />
                    <span className="font-medium">{currentPreset.name}</span>
                  </span>
                  <ChevronDown className="w-3 h-3 flex-shrink-0 text-slate-400" />
                </button>

                {hasRefs && (
                  <div className="bg-blue-50/60 border border-blue-200/60 rounded-lg px-2 py-1.5">
                    <div className="flex items-center gap-1 mb-1">
                      <span className="text-[9px] text-blue-600 font-bold tracking-wider">@引用</span>
                      <span className="text-[9px] text-blue-400">
                        {refImages.length > 0 && `${refImages.length}张图`}
                        {refImages.length > 0 && refTexts.length > 0 && " · "}
                        {refTexts.length > 0 && `${refTexts.length}段文本`}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {refImages.map((imgNode, idx) => (
                        <div key={imgNode.id} className="relative group/refimg">
                          <img
                            src={imgNode.imageUrl}
                            alt=""
                            className="w-8 h-8 rounded object-cover border border-blue-300"
                          />
                          <button
                            onClick={(e) => { e.stopPropagation(); removeConnection(imgNode.id); }}
                            className="absolute -top-1 -right-1 w-3.5 h-3.5 rounded-full bg-red-500 text-white flex items-center justify-center opacity-0 group-hover/refimg:opacity-100 transition"
                            title="移除引用"
                          >
                            <X className="w-2 h-2" />
                          </button>
                          {idx === 0 && (
                            <div className="absolute bottom-0 left-0 right-0 bg-black/50 text-white text-[7px] text-center rounded-b truncate px-0.5">
                              参考图
                            </div>
                          )}
                        </div>
                      ))}
                      {refTexts.map((textNode) => (
                        <div key={textNode.id} className="relative group/reftxt flex items-center gap-1 bg-white border border-blue-200 rounded px-1.5 py-0.5">
                          <Type className="w-2.5 h-2.5 text-blue-500 flex-shrink-0" />
                          <span className="text-[9px] text-slate-700 max-w-[80px] truncate">
                            {textNode.content.slice(0, 15)}{textNode.content.length > 15 ? "..." : ""}
                          </span>
                          <button
                            onClick={(e) => { e.stopPropagation(); removeConnection(textNode.id); }}
                            className="w-3 h-3 rounded-full bg-red-500 text-white flex items-center justify-center opacity-0 group-hover/reftxt:opacity-100 transition flex-shrink-0"
                            title="移除引用"
                          >
                            <X className="w-2 h-2" />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <textarea
                  ref={promptTextareaRef}
                  value={node.content}
                  onChange={handlePromptChange}
                  onKeyDown={handlePromptKeyDown}
                  onMouseDown={(e) => e.stopPropagation()}
                  onBlur={() => setTimeout(() => setMentionState(null), 200)}
                  placeholder="描述想要生成的图片... 输入 @ 引用素材&#10;例如：把@项链换成粉色背景"
                  className="flex-1 w-full px-2.5 py-2 text-[11px] bg-white border border-slate-200 rounded-lg resize-none outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400/20 text-slate-700 placeholder:text-slate-400 leading-relaxed shadow-sm"
                  style={{ minHeight: hasRefs ? 36 : 50 }}
                />

                <button
                  onClick={(e) => { e.stopPropagation(); void executeGenerator(node.id); }}
                  disabled={node.generating}
                  className="w-full py-2 rounded-lg bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 disabled:opacity-50 disabled:cursor-not-allowed text-white text-[11px] font-semibold flex items-center justify-center gap-1.5 transition shadow-md shadow-blue-500/20"
                >
                  {node.generating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                  {node.generating ? "生成中..." : "开始生成"}
                </button>
              </div>
            </div>
          )}
        </div>
      </>
    );
  };

  const renderNode = (node: CanvasNode) => {
    const isSelected = node.id === selectedNodeId;
    const isHoveredInput = hoveredInputNodeId === node.id;
    const Icon = NODE_ICON[node.type];
    const colors = getNodeColors(node.type);
    const isTextLike = node.type === "text" || node.type === "sticky";
    const isImageLike = node.type === "image" || node.type === "generated";
    const isGenerator = node.type === "generator";

    const borderClass = isSelected
      ? "border-blue-500 shadow-lg shadow-blue-500/25 ring-1 ring-blue-500/20"
      : isHoveredInput
        ? "border-cyan-500 shadow-lg shadow-cyan-500/30 ring-2 ring-cyan-400/40"
        : colors.border;

    return (
      <div
        key={node.id}
        className={`absolute group select-none rounded-xl border-2 shadow-md shadow-slate-300/40 ${borderClass} ${isHoveredInput ? "bg-cyan-50/40" : ""}`}
        style={{
          left: node.x,
          top: node.y,
          width: node.width,
          height: node.height,
          willChange: isDraggingNode && isSelected ? "left, top" : undefined,
          transition: isDraggingNode && isSelected ? "none" : "border-color 0.15s, box-shadow 0.15s, background-color 0.15s",
        }}
        onMouseDown={(e) => handleNodeMouseDown(e, node)}
        onClick={(e) => { e.stopPropagation(); setSelectedNodeId(node.id); }}
        onDoubleClick={(e) => { e.stopPropagation(); if (isTextLike) setEditingNodeId(node.id); }}
      >
        <div className={`flex items-center justify-between px-2.5 ${colors.titleBg} rounded-t-[10px]`} style={{ height: TITLE_HEIGHT }}>
          <div className="flex items-center gap-1.5 min-w-0">
            <Icon className={`w-3.5 h-3.5 flex-shrink-0 ${isGenerator ? "text-white" : colors.accent}`} />
            <span className={`text-[11px] font-medium truncate ${isGenerator ? "text-white" : colors.text}`}>
              {node.title}
            </span>
          </div>
          {node.type === "generated" && (
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-violet-100 text-violet-700 border border-violet-200 flex-shrink-0">AI</span>
          )}
        </div>

        <div className="relative overflow-hidden rounded-b-[10px]" style={{ height: node.height - TITLE_HEIGHT, width: "100%" }}>
          {isGenerator ? renderGeneratorNode(node, colors) : isImageLike && node.imageUrl ? (
            <img src={node.imageUrl} alt="" className="w-full h-full object-cover pointer-events-none" draggable={false} />
          ) : isTextLike ? (
            <div className={`w-full h-full p-2.5 ${colors.bodyBg}`}>
              {editingNodeId === node.id ? (
                <textarea
                  autoFocus
                  value={node.content}
                  onChange={(e) => updateNodeText(node.id, e.target.value)}
                  onBlur={() => setEditingNodeId(null)}
                  onKeyDown={(e) => { if (e.key === "Escape") setEditingNodeId(null); }}
                  placeholder={node.type === "sticky" ? "写点备注..." : "输入文字..."}
                  onMouseDown={(e) => e.stopPropagation()}
                  className={`w-full h-full bg-transparent text-sm outline-none resize-none ${colors.text} ${colors.placeholder}`}
                />
              ) : (
                <div className={`w-full h-full text-sm whitespace-pre-wrap overflow-auto ${colors.text}`}>
                  {node.content || <span className="opacity-30 italic">双击编辑</span>}
                </div>
              )}
            </div>
          ) : isImageLike && !node.imageUrl ? (
            <div className={`w-full h-full flex items-center justify-center ${colors.bodyBg}`}>
              <ImageIcon className="w-8 h-8 text-slate-600" />
            </div>
          ) : null}
        </div>

        {/* 右侧输出连接点 - 带+图标 */}
        <div
          className={`absolute rounded-full bg-gradient-to-br from-blue-500 to-cyan-500 hover:from-blue-400 hover:to-cyan-400 border-2 border-white shadow-lg shadow-blue-500/30 cursor-crosshair transition-all z-30 flex items-center justify-center ${
            draggingConnection ? "opacity-20 pointer-events-none" : "hover:scale-125"
          }`}
          style={{ right: -9, top: "50%", width: 18, height: 18, transform: "translateY(-50%)" }}
          title="拖拽连线到目标节点左侧"
          onMouseDown={(e) => startConnection(e, node)}
        >
          <Plus className="w-2.5 h-2.5 text-white pointer-events-none" strokeWidth={3} />
        </div>
        {/* 左侧输入连接点（视觉指示器，任意区域都可连线） */}
        <div
          className={`absolute rounded-full border-2 border-white shadow-sm transition-all z-30 pointer-events-none ${
            isHoveredInput
              ? "bg-cyan-500 scale-150 ring-4 ring-cyan-400/40"
              : draggingConnection
                ? "bg-blue-400 scale-125"
                : "bg-slate-300"
          }`}
          style={{ left: -9, top: "50%", width: 18, height: 18, transform: "translateY(-50%)" }}
        />

        {isSelected && RESIZE_HANDLES.map(h => (
          <div
            key={h.id}
            className="absolute w-3 h-3 bg-white border-2 border-blue-500 rounded-sm z-20 no-drag shadow-sm"
            style={{ ...h.style, cursor: h.cursor }}
            onMouseDown={(e) => startResize(e, node.id, h.id)}
          />
        ))}

        <button
          onClick={(e) => { e.stopPropagation(); deleteNode(node.id); }}
          className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-red-500/90 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition shadow-lg z-20 hover:bg-red-500 hover:scale-110"
          title="删除节点"
        >
          <X className="w-3 h-3" />
        </button>
      </div>
    );
  };

  return (
    <div className="flex-1 relative overflow-hidden bg-slate-100">
      <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleFileUpload} />

      <div className="absolute top-4 left-1/2 -translate-x-1/2 text-[11px] text-slate-600 bg-white/80 backdrop-blur border border-slate-200 rounded-full px-3.5 py-1.5 z-10 pointer-events-none shadow-md">
        右键创建节点 · 拖右侧 <span className="text-blue-500">+</span> 连线引用 · 滚轮缩放
      </div>

      <div
        ref={canvasRef}
        className="w-full h-full relative overflow-hidden cursor-grab active:cursor-grabbing canvas-bg"
        style={{
          backgroundImage: "radial-gradient(circle, rgba(100, 116, 139, 0.18) 1px, transparent 1px)",
          backgroundSize: `${24 * scale}px ${24 * scale}px`,
          backgroundPosition: `${offset.x}px ${offset.y}px`,
          backgroundColor: "#f1f5f9",
        }}
        onMouseDown={handleCanvasMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
        onContextMenu={handleContextMenu}
      >
        <div style={{ transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`, transformOrigin: "0 0", position: "absolute", top: 0, left: 0 }}>
          <svg className="absolute top-0 left-0" style={{ width: 1, height: 1, overflow: "visible", pointerEvents: "none" }}>
            <defs>
              <linearGradient id="conn-grad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#06b6d4" />
                <stop offset="100%" stopColor="#3b82f6" />
              </linearGradient>
              <filter id="conn-glow">
                <feGaussianBlur stdDeviation="2" result="coloredBlur" />
                <feMerge>
                  <feMergeNode in="coloredBlur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>
            {connections.map((conn) => {
              const fromNode = nodes.find(n => n.id === conn.from);
              const toNode = nodes.find(n => n.id === conn.to);
              if (!fromNode || !toNode) return null;
              const d = buildBezierPath(getOutputPoint(fromNode), getInputPoint(toNode));
              return (
                <g key={conn.id} className="cursor-pointer">
                  <path d={d} stroke="transparent" strokeWidth={16} fill="none" style={{ pointerEvents: "stroke" }} onClick={(e) => { e.stopPropagation(); deleteConnection(conn.id); }}>
                    <title>点击删除连线</title>
                  </path>
                  <path d={d} stroke="url(#conn-grad)" strokeWidth={2.5} fill="none" filter="url(#conn-glow)" style={{ pointerEvents: "none" }} />
                </g>
              );
            })}
            {draggingConnection && (
              <path d={buildBezierPath(draggingConnection.fromPos, draggingConnection.currentPos)} stroke="#06b6d4" strokeWidth={2.5} strokeDasharray="6 4" fill="none" style={{ pointerEvents: "none" }} />
            )}
          </svg>
          {nodes.map(renderNode)}
        </div>
      </div>

      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 flex items-center gap-1 bg-white/95 backdrop-blur border border-slate-200 rounded-2xl px-2 py-1.5 shadow-xl shadow-slate-400/20">
        <button onClick={() => createNode("generator", viewportCenterCanvas())} className="flex items-center gap-1.5 px-3.5 h-9 rounded-xl bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white text-xs font-semibold transition shadow-md shadow-blue-500/25">
          <Wand2 className="w-3.5 h-3.5" /> 新建生成器
        </button>
        <div className="w-px h-6 bg-slate-200 mx-0.5" />
        <button onClick={() => createNode("text", viewportCenterCanvas())} className="w-9 h-9 rounded-xl hover:bg-slate-100 flex items-center justify-center text-slate-500 hover:text-blue-600 transition" title="添加文本"><Type className="w-4 h-4" /></button>
        <button onClick={() => createNode("sticky", viewportCenterCanvas())} className="w-9 h-9 rounded-xl hover:bg-slate-100 flex items-center justify-center text-slate-500 hover:text-amber-600 transition" title="添加便签"><StickyNote className="w-4 h-4" /></button>
        <button onClick={() => createNode("image", viewportCenterCanvas())} className="w-9 h-9 rounded-xl hover:bg-slate-100 flex items-center justify-center text-slate-500 hover:text-emerald-600 transition" title="上传图片"><Upload className="w-4 h-4" /></button>
        <div className="w-px h-6 bg-slate-200 mx-0.5" />
        <button onClick={() => setScale(s => Math.min(MAX_SCALE, s * 1.2))} className="w-9 h-9 rounded-xl hover:bg-slate-100 flex items-center justify-center text-slate-500 hover:text-blue-600 transition" title="放大"><ZoomIn className="w-4 h-4" /></button>
        <span className="text-xs text-slate-600 w-12 text-center font-mono tabular-nums">{Math.round(scale * 100)}%</span>
        <button onClick={() => setScale(s => Math.max(MIN_SCALE, s / 1.2))} className="w-9 h-9 rounded-xl hover:bg-slate-100 flex items-center justify-center text-slate-500 hover:text-blue-600 transition" title="缩小"><ZoomOut className="w-4 h-4" /></button>
        <button onClick={resetView} className="w-9 h-9 rounded-xl hover:bg-slate-100 flex items-center justify-center text-slate-500 hover:text-blue-600 transition" title="重置视图"><RotateCcw className="w-4 h-4" /></button>
      </div>

      {typeof document !== "undefined" && createPortal(
        <>
          <AnimatePresence>
            {modelDropdownOpen && (
              <motion.div
                initial={{ opacity: 0, y: -4, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -4, scale: 0.98 }}
                transition={{ duration: 0.12 }}
                className="fixed z-50 bg-white border border-slate-200 rounded-xl shadow-xl shadow-slate-400/20 overflow-hidden no-drag"
                style={{ left: modelDropdownPos.x, top: modelDropdownPos.y, minWidth: 200 }}
                onClick={(e) => e.stopPropagation()}
              >
                {MODELS.map(m => (
                  <button
                    key={m.id}
                    onClick={() => { const node = nodes.find(n => n.id === modelDropdownOpen); if (node) updateNode(node.id, { model: m.id }); setModelDropdownOpen(null); }}
                    className={`w-full text-left px-3 py-2.5 text-[12px] hover:bg-blue-50 flex items-center justify-between gap-2 transition ${m.id === (nodes.find(n => n.id === modelDropdownOpen)?.model) ? "bg-blue-50 text-blue-600" : "text-slate-700"}`}
                  >
                    <div className="flex flex-col">
                      <span className="font-medium">{m.name}</span>
                      <span className="text-[10px] text-slate-400">{m.desc}</span>
                    </div>
                    {m.id === (nodes.find(n => n.id === modelDropdownOpen)?.model) && <Check className="w-4 h-4 text-blue-600 flex-shrink-0" />}
                  </button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>

          <AnimatePresence>
            {sizeDropdownOpen && (
              <motion.div
                initial={{ opacity: 0, y: -4, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -4, scale: 0.98 }}
                transition={{ duration: 0.12 }}
                className="fixed z-50 bg-white border border-slate-200 rounded-xl shadow-xl shadow-slate-400/20 overflow-hidden no-drag"
                style={{ left: sizeDropdownPos.x, top: sizeDropdownPos.y, minWidth: 160 }}
                onClick={(e) => e.stopPropagation()}
              >
                {SIZES.map(s => (
                  <button
                    key={s.id}
                    onClick={() => { const node = nodes.find(n => n.id === sizeDropdownOpen); if (node) updateNode(node.id, { size: s.id }); setSizeDropdownOpen(null); }}
                    className={`w-full text-left px-3 py-2.5 text-[12px] hover:bg-blue-50 flex items-center justify-between gap-2 transition ${s.id === (nodes.find(n => n.id === sizeDropdownOpen)?.size) ? "bg-blue-50 text-blue-600" : "text-slate-700"}`}
                  >
                    <span className="font-medium">{s.name}</span>
                    {s.id === (nodes.find(n => n.id === sizeDropdownOpen)?.size) && <Check className="w-4 h-4 text-blue-600 flex-shrink-0" />}
                  </button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>

          <AnimatePresence>
            {presetDropdownOpen && (
              <motion.div
                initial={{ opacity: 0, y: -4, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -4, scale: 0.98 }}
                transition={{ duration: 0.12 }}
                className="fixed z-50 bg-white border border-slate-200 rounded-xl shadow-xl shadow-slate-400/20 overflow-hidden no-drag"
                style={{ left: presetDropdownPos.x, top: presetDropdownPos.y, minWidth: 180 }}
                onClick={(e) => e.stopPropagation()}
              >
                {PRESETS.map(p => (
                  <button
                    key={p.id}
                    onClick={() => { const node = nodes.find(n => n.id === presetDropdownOpen); if (node) updateNode(node.id, { preset: p.id }); setPresetDropdownOpen(null); }}
                    className={`w-full text-left px-3 py-2.5 text-[12px] hover:bg-blue-50 flex items-center justify-between gap-2 transition ${p.id === (nodes.find(n => n.id === presetDropdownOpen)?.preset) ? "bg-blue-50 text-blue-600" : "text-slate-700"}`}
                  >
                    <span className="font-medium">{p.name}</span>
                    {p.id === (nodes.find(n => n.id === presetDropdownOpen)?.preset) && <Check className="w-4 h-4 text-blue-600 flex-shrink-0" />}
                  </button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>

          <AnimatePresence>
            {mentionState && (
              <motion.div
                initial={{ opacity: 0, y: -4, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -4, scale: 0.97 }}
                transition={{ duration: 0.1 }}
                className="fixed z-50 w-[220px] bg-white border border-slate-200 rounded-xl shadow-xl shadow-slate-400/20 overflow-hidden py-1"
                style={{ left: Math.min(mentionState.pos.x, window.innerWidth - 240), top: Math.min(mentionState.pos.y, window.innerHeight - 200) }}
                onMouseDown={(e) => e.preventDefault()}
              >
                <div className="px-3 py-1 text-[10px] text-slate-400 border-b border-slate-200 uppercase tracking-wider flex items-center gap-1">
                  <span>选择引用素材</span>
                  {mentionState.query && <span className="text-blue-600 normal-case tracking-normal truncate">"{mentionState.query}"</span>}
                </div>
                <div className="max-h-[180px] overflow-y-auto">
                  {mentionState.query && mentionCandidates.length === 0 ? (
                    <div className="px-3 py-3 text-[11px] text-slate-400 text-center">无匹配素材</div>
                  ) : mentionCandidates.length === 0 ? (
                    <div className="px-3 py-3 text-[11px] text-slate-400 text-center">画布上无可用素材</div>
                  ) : mentionCandidates.map((n, idx) => {
                    const isImg = n.type === "image" || n.type === "generated";
                    const icon = n.type === "text" ? <Type className="w-3.5 h-3.5 text-blue-500" />
                      : n.type === "sticky" ? <StickyNote className="w-3.5 h-3.5 text-amber-500" />
                      : n.type === "generated" ? <Sparkles className="w-3.5 h-3.5 text-violet-500" />
                      : <ImageIcon className="w-3.5 h-3.5 text-emerald-500" />;
                    return (
                      <button
                        key={n.id}
                        onMouseDown={(e) => { e.preventDefault(); e.stopPropagation(); handleSelectMention(n); }}
                        className={`w-full flex items-center gap-2 px-3 py-1.5 text-[11px] text-left transition ${idx === mentionIndex ? "bg-blue-50 text-blue-700" : "text-slate-700 hover:bg-slate-50"}`}
                        onMouseEnter={() => setMentionIndex(idx)}
                      >
                        {isImg && n.imageUrl ? (
                          <img src={n.imageUrl} alt="" className="w-7 h-7 rounded object-cover border border-slate-200 flex-shrink-0" />
                        ) : (
                          <div className="w-7 h-7 rounded bg-slate-100 border border-slate-200 flex items-center justify-center flex-shrink-0">{icon}</div>
                        )}
                        <div className="flex flex-col min-w-0 flex-1">
                          <span className="font-medium truncate">{n.title}</span>
                          {n.content && <span className="text-[9px] text-slate-400 truncate">{n.content.slice(0, 20)}</span>}
                        </div>
                        {idx === mentionIndex && <span className="text-[9px] text-blue-500 flex-shrink-0">↵</span>}
                      </button>
                    );
                  })}
                </div>
                <div className="px-3 py-1 border-t border-slate-200 flex items-center gap-2 text-[9px] text-slate-400">
                  <span>↑↓ 选择</span><span>Enter 确认</span><span>Esc 取消</span>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <AnimatePresence>
            {contextMenu.visible && (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} transition={{ duration: 0.12 }}
                className="fixed z-50 min-w-[180px] bg-white border border-slate-200 rounded-xl shadow-xl shadow-slate-400/20 overflow-hidden py-1"
                style={{ left: Math.min(contextMenu.screenX, window.innerWidth - 200), top: Math.min(contextMenu.screenY, window.innerHeight - 260) }}
                onClick={(e) => e.stopPropagation()} onContextMenu={(e) => e.preventDefault()}
              >
                <div className="px-3 py-1.5 text-[10px] text-slate-400 uppercase tracking-wider border-b border-slate-200">创建节点</div>
                <button onClick={() => { createNode("generator", { x: contextMenu.canvasX, y: contextMenu.canvasY }); closeContextMenu(); }} className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-blue-50 transition">
                  <Wand2 className="w-4 h-4 text-blue-500" /> 图片生成器
                </button>
                <button onClick={() => { createNode("text", { x: contextMenu.canvasX, y: contextMenu.canvasY }); closeContextMenu(); }} className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-blue-50 transition">
                  <Type className="w-4 h-4 text-slate-500" /> 文本节点
                </button>
                <button onClick={() => { createNode("sticky", { x: contextMenu.canvasX, y: contextMenu.canvasY }); closeContextMenu(); }} className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-blue-50 transition">
                  <StickyNote className="w-4 h-4 text-amber-500" /> 便签节点
                </button>
                <button onClick={() => { createNode("image", { x: contextMenu.canvasX, y: contextMenu.canvasY }); closeContextMenu(); }} className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-blue-50 transition">
                  <Upload className="w-4 h-4 text-emerald-500" /> 上传图片
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </>,
        document.body
      )}
    </div>
  );
}
