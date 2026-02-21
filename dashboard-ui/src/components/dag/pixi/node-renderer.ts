import { Graphics } from 'pixi.js'

/**
 * Draw a node shape into a Graphics object.
 * Translates the SVG path generators from NodeShapes.ts into PixiJS Graphics API.
 */

/** Standard rounded rectangle (step) */
export function drawRect(g: Graphics, w: number, h: number, color: number, r = 6): void {
  g.roundRect(0, 0, w, h, r)
  g.fill({ color: 0x000000, alpha: 0 })
  g.stroke({ color, width: 1.5 })
}

/** Diamond (switch) */
export function drawDiamond(g: Graphics, w: number, h: number, color: number): void {
  const cx = w / 2
  const cy = h / 2
  g.moveTo(cx, 0)
  g.lineTo(w, cy)
  g.lineTo(cx, h)
  g.lineTo(0, cy)
  g.closePath()
  g.fill({ color: 0x000000, alpha: 0 })
  g.stroke({ color, width: 1.5 })
}

/** Double-border rectangle (map) — outer + inner */
export function drawMap(g: Graphics, w: number, h: number, color: number, r = 6): void {
  // Outer
  g.roundRect(0, 0, w, h, r)
  g.fill({ color: 0x000000, alpha: 0 })
  g.stroke({ color, width: 1.5 })
  // Inner (inset 4px)
  const inset = 4
  g.roundRect(inset, inset, w - inset * 2, h - inset * 2, r - 2)
  g.stroke({ color, width: 1, alpha: 0.4 })
}

/** Dashed rectangle (sub) — uses manual dash segments */
export function drawSub(g: Graphics, w: number, h: number, color: number, r = 6): void {
  // Fill with transparent (for hit area)
  g.roundRect(0, 0, w, h, r)
  g.fill({ color: 0x000000, alpha: 0 })

  // Draw dashed border manually along the rectangle perimeter
  const dashLen = 6
  const gapLen = 3
  const points: Array<{ x: number; y: number }> = []

  // Build perimeter points (clockwise from top-left + radius)
  // Top edge
  for (let x = r; x <= w - r; x += 1) points.push({ x, y: 0 })
  // Top-right corner arc approximation
  points.push({ x: w, y: r })
  // Right edge
  for (let y = r; y <= h - r; y += 1) points.push({ x: w, y })
  // Bottom-right corner
  points.push({ x: w - r, y: h })
  // Bottom edge
  for (let x = w - r; x >= r; x -= 1) points.push({ x, y: h })
  // Bottom-left corner
  points.push({ x: 0, y: h - r })
  // Left edge
  for (let y = h - r; y >= r; y -= 1) points.push({ x: 0, y })
  // Top-left corner
  points.push({ x: r, y: 0 })

  // Draw dashed segments
  let dist = 0
  let drawing = true
  let segStart: { x: number; y: number } | null = null

  for (let i = 0; i < points.length; i++) {
    const p = points[i]!
    if (i > 0) {
      const prev = points[i - 1]!
      const dx = p.x - prev.x
      const dy = p.y - prev.y
      dist += Math.sqrt(dx * dx + dy * dy)
    }

    const threshold = drawing ? dashLen : gapLen
    if (dist >= threshold) {
      dist = 0
      if (drawing && segStart) {
        g.moveTo(segStart.x, segStart.y)
        g.lineTo(p.x, p.y)
        g.stroke({ color, width: 1.5 })
      }
      drawing = !drawing
      segStart = drawing ? p : null
    } else if (drawing && !segStart) {
      segStart = p
    }
  }
  // Finish last segment
  if (drawing && segStart && points.length > 0) {
    const last = points[points.length - 1]!
    g.moveTo(segStart.x, segStart.y)
    g.lineTo(last.x, last.y)
    g.stroke({ color, width: 1.5 })
  }
}

/** Hexagon (barrier) */
export function drawHexagon(g: Graphics, w: number, h: number, color: number): void {
  const indent = h * 0.3
  g.moveTo(indent, 0)
  g.lineTo(w - indent, 0)
  g.lineTo(w, h / 2)
  g.lineTo(w - indent, h)
  g.lineTo(indent, h)
  g.lineTo(0, h / 2)
  g.closePath()
  g.fill({ color: 0x000000, alpha: 0 })
  g.stroke({ color, width: 1.5 })
}

/** Stadium / pill shape (streaming) — very rounded corners */
export function drawStadium(g: Graphics, w: number, h: number, color: number): void {
  const r = h / 2
  g.roundRect(0, 0, w, h, r)
  g.fill({ color: 0x000000, alpha: 0 })
  g.stroke({ color, width: 1.5 })
}

/** Pseudo-node (Start/End) — pill with filled background */
export function drawPseudoNode(g: Graphics, w: number, h: number, color: number): void {
  const r = h / 2
  g.roundRect(0, 0, w, h, r)
  g.fill({ color, alpha: 0.15 })
  g.stroke({ color, width: 1.5 })
}

/** Draw the appropriate shape for a node kind */
export function drawNodeShape(g: Graphics, kind: string, w: number, h: number, color: number): void {
  switch (kind) {
    case 'switch':
      drawDiamond(g, w, h, color)
      break
    case 'map':
      drawMap(g, w, h, color)
      break
    case 'sub':
      drawSub(g, w, h, color)
      break
    case 'barrier':
      drawHexagon(g, w, h, color)
      break
    case 'streaming':
      drawStadium(g, w, h, color)
      break
    case 'pseudo':
      drawPseudoNode(g, w, h, color)
      break
    default:
      drawRect(g, w, h, color)
      break
  }
}

/** Draw a glow effect behind a node (for selection or status).
 *  Draws at the same bounds as the shape — no gap — using a thicker
 *  semi-transparent stroke to create an outer glow. */
export function drawNodeGlow(
  g: Graphics,
  kind: string,
  w: number,
  h: number,
  color: number,
  alpha = 0.15,
): void {
  switch (kind) {
    case 'switch': {
      const cx = w / 2
      const cy = h / 2
      g.moveTo(cx, 0)
      g.lineTo(w, cy)
      g.lineTo(cx, h)
      g.lineTo(0, cy)
      g.closePath()
      break
    }
    case 'barrier': {
      const indent = h * 0.3
      g.moveTo(indent, 0)
      g.lineTo(w - indent, 0)
      g.lineTo(w, h / 2)
      g.lineTo(w - indent, h)
      g.lineTo(indent, h)
      g.lineTo(0, h / 2)
      g.closePath()
      break
    }
    case 'streaming':
    case 'pseudo':
      g.roundRect(0, 0, w, h, h / 2)
      break
    default:
      g.roundRect(0, 0, w, h, 6)
      break
  }
  g.fill({ color, alpha: alpha * 0.5 })
  g.stroke({ color, width: 4, alpha: alpha * 2.5 })
}

/** Get the node color key for a kind */
export function kindColorKey(kind: string): string {
  switch (kind) {
    case 'step': return 'nodeStep'
    case 'switch': return 'nodeSwitch'
    case 'map': return 'nodeMap'
    case 'sub': return 'nodeSub'
    case 'barrier': return 'nodeBarrier'
    case 'streaming': return 'nodeStreaming'
    case 'pseudo': return 'nodePseudo'
    default: return 'nodeStep'
  }
}
