import { Graphics } from 'pixi.js'
import type { Ticker } from 'pixi.js'

type Point = { x: number; y: number }

/** Draw a solid polyline edge */
export function drawEdgeLine(
  g: Graphics,
  points: Point[],
  color: number,
  width = 1.5,
  alpha = 1,
): void {
  if (points.length < 2) return
  g.moveTo(points[0]!.x, points[0]!.y)
  for (let i = 1; i < points.length; i++) {
    g.lineTo(points[i]!.x, points[i]!.y)
  }
  g.stroke({ color, width, alpha, cap: 'round', join: 'round' })
}

/**
 * Draw a manually-dashed polyline for the conveyor animation.
 * PixiJS v8 doesn't support stroke dash natively, so we compute
 * dash segments ourselves along the polyline path.
 */
export function drawEdgeDash(
  g: Graphics,
  points: Point[],
  color: number,
  dashOffset: number,
  dashLen = 8,
  gapLen = 4,
): void {
  if (points.length < 2) return

  // Compute cumulative distances along the polyline
  const segments: Array<{ start: Point; end: Point; startDist: number; len: number }> = []
  let totalDist = 0
  for (let i = 1; i < points.length; i++) {
    const dx = points[i]!.x - points[i - 1]!.x
    const dy = points[i]!.y - points[i - 1]!.y
    const len = Math.sqrt(dx * dx + dy * dy)
    segments.push({ start: points[i - 1]!, end: points[i]!, startDist: totalDist, len })
    totalDist += len
  }

  if (totalDist === 0) return

  const period = dashLen + gapLen
  // Normalize offset to [0, period)
  const offset = ((dashOffset % period) + period) % period

  // Walk along the path and draw dash segments
  let pos = -offset
  while (pos < totalDist) {
    const dashStart = Math.max(0, pos)
    const dashEnd = Math.min(totalDist, pos + dashLen)

    if (dashEnd > dashStart) {
      const p1 = pointAtDistance(segments, dashStart)
      const p2 = pointAtDistance(segments, dashEnd)
      if (p1 && p2) {
        g.moveTo(p1.x, p1.y)
        // Draw through intermediate segment boundaries
        for (const seg of segments) {
          const segEnd = seg.startDist + seg.len
          if (segEnd > dashStart && seg.startDist < dashEnd) {
            const clampedEnd = Math.min(dashEnd, segEnd)
            const pt = pointAtDistance(segments, clampedEnd)
            if (pt) g.lineTo(pt.x, pt.y)
          }
        }
      }
    }

    pos += period
  }

  g.stroke({ color, width: 1.5, alpha: 0.6, cap: 'round', join: 'round' })
}

function pointAtDistance(
  segments: Array<{ start: Point; end: Point; startDist: number; len: number }>,
  dist: number,
): Point | null {
  for (const seg of segments) {
    const segEnd = seg.startDist + seg.len
    if (dist >= seg.startDist && dist <= segEnd) {
      const t = seg.len > 0 ? (dist - seg.startDist) / seg.len : 0
      return {
        x: seg.start.x + (seg.end.x - seg.start.x) * t,
        y: seg.start.y + (seg.end.y - seg.start.y) * t,
      }
    }
  }
  return null
}

/** Draw an edge split at a progress point: wide colored portion + narrow gray remainder */
export function drawEdgeWithProgress(
  g: Graphics,
  points: Point[],
  filledColor: number,
  defaultColor: number,
  progress: number,
  filledWidth = 8,
  defaultWidth = 2,
): void {
  if (points.length < 2) return

  if (progress <= 0) {
    drawEdgeLine(g, points, defaultColor, defaultWidth, 0.6)
    return
  }
  if (progress >= 1) {
    drawEdgeLine(g, points, filledColor, filledWidth, 0.9)
    return
  }

  // Compute segment distances
  const segments: Array<{ start: Point; end: Point; startDist: number; len: number }> = []
  let totalDist = 0
  for (let i = 1; i < points.length; i++) {
    const dx = points[i]!.x - points[i - 1]!.x
    const dy = points[i]!.y - points[i - 1]!.y
    const len = Math.sqrt(dx * dx + dy * dy)
    segments.push({ start: points[i - 1]!, end: points[i]!, startDist: totalDist, len })
    totalDist += len
  }
  if (totalDist === 0) return

  const splitDist = progress * totalDist

  // Find the split point
  let splitPoint: Point | null = null
  for (const seg of segments) {
    const segEnd = seg.startDist + seg.len
    if (splitDist >= seg.startDist && splitDist <= segEnd) {
      const t = seg.len > 0 ? (splitDist - seg.startDist) / seg.len : 0
      splitPoint = {
        x: seg.start.x + (seg.end.x - seg.start.x) * t,
        y: seg.start.y + (seg.end.y - seg.start.y) * t,
      }
      break
    }
  }
  if (!splitPoint) return

  // Draw filled portion (wide, colored)
  g.moveTo(points[0]!.x, points[0]!.y)
  for (const seg of segments) {
    if (seg.startDist + seg.len <= splitDist) {
      g.lineTo(seg.end.x, seg.end.y)
    } else if (seg.startDist < splitDist) {
      g.lineTo(splitPoint.x, splitPoint.y)
      break
    } else {
      break
    }
  }
  g.stroke({ color: filledColor, width: filledWidth, alpha: 0.9, cap: 'round', join: 'round' })

  // Draw unfilled portion (narrow, muted)
  g.moveTo(splitPoint.x, splitPoint.y)
  for (const seg of segments) {
    if (seg.startDist + seg.len > splitDist) {
      g.lineTo(seg.end.x, seg.end.y)
    }
  }
  g.stroke({ color: defaultColor, width: defaultWidth, alpha: 0.6, cap: 'round', join: 'round' })
}

/** Draw an arrow dot at the end of an edge */
export function drawArrow(g: Graphics, x: number, y: number, color: number): void {
  g.circle(x, y, 3)
  g.fill({ color })
}

/**
 * Manages dash animation for all edges via the PixiJS ticker.
 */
export class EdgeAnimator {
  private offset = 0
  private speed = 20 // pixels per second
  private edges: Array<{
    dash: Graphics
    points: Point[]
    color: number
  }> = []

  register(dash: Graphics, points: Point[], color: number): void {
    this.edges.push({ dash, points, color })
  }

  /** Update the points for a registered dash (e.g. when switching to iso-projected paths) */
  updatePoints(dash: Graphics, points: Point[]): void {
    const entry = this.edges.find((e) => e.dash === dash)
    if (entry) entry.points = points
  }

  clear(): void {
    this.edges = []
    this.offset = 0
  }

  update(ticker: Ticker): void {
    this.offset += ticker.deltaMS * this.speed / 1000

    for (const edge of this.edges) {
      edge.dash.clear()
      drawEdgeDash(edge.dash, edge.points, edge.color, this.offset)
    }
  }
}
