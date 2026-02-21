import type { Container, Graphics, Text } from 'pixi.js'
import type { RenderedNode, DagLayout } from '@/types/dag'

/** PixiJS node container with child graphics + labels */
export interface PixiNode {
  id: string
  kind: string
  container: Container
  shape: Graphics
  glow: Graphics
  label: Text
  kindLabel: Container
  data: RenderedNode
}

/** PixiJS edge with polyline graphics */
export interface PixiEdge {
  id: string
  source: string
  target: string
  main: Graphics
  dash: Graphics
  arrow: Graphics
  points: Array<{ x: number; y: number }>
  label?: Text
}

/** Current state of the DAG scene */
export interface DagSceneState {
  layout: DagLayout | null
  nodes: Map<string, PixiNode>
  edges: Map<string, PixiEdge>
  selectedNode: string | null
  hoveredNode: string | null
  stepStatuses: Record<string, string>
  particlesEnabled: boolean
  isometric: boolean
  blastRadiusNode: string | null
}
