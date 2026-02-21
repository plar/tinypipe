/**
 * Animated 500ms transition between 2D and isometric modes.
 *
 * Lerps node positions, crossfades shape alpha, and fades ground/shadows.
 */

import type { Container, Graphics } from 'pixi.js'
import type { PixiNode, PixiEdge } from '../types'
import { isoProject } from './iso-projection'
import { projectEdgePoints } from './iso-edges'
import { drawEdgeLine, drawArrow } from '../edge-renderer'

const DURATION = 500 // ms

interface NodeSnapshot {
  x: number
  y: number
}

interface TransitionState {
  startTime: number
  toIso: boolean
  nodeSnapshots: Map<string, NodeSnapshot>
  edgeSnapshots: Map<string, Array<{ x: number; y: number }>>
  onComplete: () => void
}

/** Ease-out cubic: decelerating to zero velocity */
function easeOutCubic(t: number): number {
  const t1 = 1 - t
  return 1 - t1 * t1 * t1
}

/**
 * Manages animated transitions between 2D and isometric modes.
 */
export class IsoTransition {
  private active: TransitionState | null = null

  get isActive(): boolean {
    return this.active !== null
  }

  /**
   * Start a transition. Snapshots current positions.
   * When transitioning FROM iso (toIso=false), edge snapshots must be the
   * iso-projected positions since edge.points always stores original 2D coords.
   */
  start(
    toIso: boolean,
    nodes: Map<string, PixiNode>,
    edges: Map<string, PixiEdge>,
    onComplete: () => void,
  ): void {
    const nodeSnapshots = new Map<string, NodeSnapshot>()
    for (const [id, node] of nodes) {
      nodeSnapshots.set(id, {
        x: node.container.x,
        y: node.container.y,
      })
    }

    const edgeSnapshots = new Map<string, Array<{ x: number; y: number }>>()
    for (const [id, edge] of edges) {
      if (toIso) {
        // Currently in 2D — snapshot the 2D points
        edgeSnapshots.set(id, edge.points.map((p) => ({ x: p.x, y: p.y })))
      } else {
        // Currently in iso — snapshot the iso-projected points
        edgeSnapshots.set(id, projectEdgePoints(edge.points))
      }
    }

    this.active = {
      startTime: performance.now(),
      toIso,
      nodeSnapshots,
      edgeSnapshots,
      onComplete,
    }
  }

  /**
   * Update the transition. Called per frame from ticker.
   * Returns true if the transition is still active.
   */
  update(
    now: number,
    nodes: Map<string, PixiNode>,
    edges: Map<string, PixiEdge>,
    groundLayer: Graphics,
    shadowLayer: Graphics,
    _isoShapes: Map<string, Container>,
    borderColor: number,
  ): boolean {
    if (!this.active) return false

    const elapsed = now - this.active.startTime
    const rawT = Math.min(elapsed / DURATION, 1)
    const t = easeOutCubic(rawT)

    const { toIso, nodeSnapshots } = this.active

    // Lerp node positions
    for (const [id, node] of nodes) {
      const snap = nodeSnapshots.get(id)
      if (!snap) continue

      const elkX = node.data.x
      const elkY = node.data.y

      // Target position
      let targetX: number, targetY: number
      if (toIso) {
        const iso = isoProject(elkX, elkY)
        targetX = iso.x
        targetY = iso.y
      } else {
        targetX = elkX
        targetY = elkY
      }

      node.container.x = snap.x + (targetX - snap.x) * t
      node.container.y = snap.y + (targetY - snap.y) * t
    }

    // Lerp edge positions
    for (const [id, edge] of edges) {
      const origPoints = edge.points
      let targetPoints: Array<{ x: number; y: number }>
      if (toIso) {
        targetPoints = projectEdgePoints(origPoints)
      } else {
        targetPoints = origPoints
      }

      // Get snapshot (source positions)
      const snapPoints = this.active.edgeSnapshots.get(id)
      if (!snapPoints || snapPoints.length !== targetPoints.length) continue

      const lerpedPoints = snapPoints.map((sp, i) => ({
        x: sp.x + (targetPoints[i]!.x - sp.x) * t,
        y: sp.y + (targetPoints[i]!.y - sp.y) * t,
      }))

      // Redraw edge at lerped positions
      edge.main.clear()
      drawEdgeLine(edge.main, lerpedPoints, borderColor, 1.5, 0.6)
      edge.arrow.clear()
      if (lerpedPoints.length > 0) {
        const last = lerpedPoints[lerpedPoints.length - 1]!
        drawArrow(edge.arrow, last.x, last.y, borderColor)
      }
    }

    // Crossfade 2D ↔ iso shapes
    const isoAlpha = toIso ? t : 1 - t
    const flatAlpha = toIso ? 1 - t : t

    for (const [, node] of nodes) {
      // Crossfade iso elements ↔ 2D elements.
      // Label (Text) must be excluded — it stays visible in both modes.
      for (const child of node.container.children) {
        if (child.label === 'iso-shape' || child.label === 'iso-glow') {
          child.alpha = isoAlpha
        } else if (child.label === 'iso-pill') {
          child.alpha = isoAlpha
        } else if (child === node.label) {
          // Label stays fully visible during transition
          child.alpha = 1
        } else if (
          child !== node.glow &&
          child.label !== 'depth-faces' &&
          child.label !== 'iso-shadow'
        ) {
          // 2D elements (bg, shape, kindLabel, hitArea)
          if (child.label === 'hit-area' || child.eventMode === 'static') continue
          child.alpha = flatAlpha
        }
      }
    }

    // Fade ground + shadows
    groundLayer.alpha = isoAlpha
    shadowLayer.alpha = isoAlpha

    // Check completion
    if (rawT >= 1) {
      const onComplete = this.active.onComplete
      this.active = null
      onComplete()
      return false
    }

    return true
  }

  /** Cancel any active transition */
  cancel(): void {
    this.active = null
  }
}
