import type { NodeKind } from './index'

/* ── ELK input types ───────────────────────────────────────── */

export interface ElkNode {
  id: string
  width: number
  height: number
  labels?: Array<{ text: string }>
  layoutOptions?: Record<string, string>
  children?: ElkNode[]
  ports?: Array<{ id: string; x?: number; y?: number; layoutOptions?: Record<string, string> }>
}

export interface ElkEdge {
  id: string
  sources: string[]
  targets: string[]
  labels?: Array<{ text: string }>
  sourcePort?: string
  targetPort?: string
}

export interface ElkGraph {
  id: string
  children: ElkNode[]
  edges: ElkEdge[]
  layoutOptions: Record<string, string>
}

/* ── ELK output (after layout) ─────────────────────────────── */

export interface ElkPoint {
  x: number
  y: number
}

export interface ElkSection {
  startPoint: ElkPoint
  endPoint: ElkPoint
  bendPoints?: ElkPoint[]
}

export interface ElkLayoutNode extends ElkNode {
  x: number
  y: number
  children?: ElkLayoutNode[]
}

export interface ElkLayoutEdge extends ElkEdge {
  sections: ElkSection[]
}

export interface ElkLayoutGraph extends ElkGraph {
  children: ElkLayoutNode[]
  edges: ElkLayoutEdge[]
}

/* ── Rendering model (consumed by Vue components) ──────────── */

export interface RenderedNode {
  id: string
  label: string
  kind: NodeKind | string
  x: number
  y: number
  width: number
  height: number
  isEntry?: boolean
  isTerminal?: boolean
  barrierType?: string
  isPseudo?: boolean
  pseudoKind?: 'start' | 'end'
}

export interface RenderedEdge {
  id: string
  source: string
  target: string
  points: ElkPoint[]
  label?: string
  isMapEdge?: boolean
}

export interface RenderedGroup {
  id: string
  label: string
  x: number
  y: number
  width: number
  height: number
  kind: 'parallel'
}

export interface DagLayout {
  nodes: RenderedNode[]
  edges: RenderedEdge[]
  groups: RenderedGroup[]
  width: number
  height: number
}
