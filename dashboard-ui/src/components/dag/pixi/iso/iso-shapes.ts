/**
 * Isometric 3D shape drawing for each step kind.
 *
 * Shapes are drawn in isometric projection. The top face is an iso
 * parallelogram (projected from the node's ELK-space rectangle); extrusion
 * faces extend straight down in screen Y to create depth.
 *
 * Three visible faces: top (brightest), right (darken 25%), front (darken 45%).
 * Edge strokes use darken 55% at alpha 0.4.
 */

import { Graphics } from 'pixi.js'
import { darken } from './iso-projection'

// Isometric projection constants (same as iso-projection.ts)
const ISO_COS = Math.cos(Math.PI / 6) // ~0.866
const ISO_SIN = Math.sin(Math.PI / 6) // 0.5

/**
 * Project a local ELK-space (u, v) offset to isometric screen-space offset.
 * u = local X (right in ELK), v = local Y (down in ELK).
 * Mirrored (v-u) for left-to-right flow — matches isoProject in iso-projection.ts.
 * Returns [screenDx, screenDy] relative to the container origin.
 */
function iso(u: number, v: number): [number, number] {
  return [(v - u) * ISO_COS, (u + v) * ISO_SIN]
}

/** Per-kind extrusion depths (screen pixels downward from top face) */
const DEPTHS: Record<string, number> = {
  step: 18,
  map: 14,
  switch: 14,
  sub: 24,
  barrier: 16,
  streaming: 20,
  pseudo: 6,
}

export function getIsoHeight(kind: string): number {
  return DEPTHS[kind] ?? DEPTHS.step!
}

/**
 * Get the screen-space center of the iso top face for label positioning.
 */
export function getIsoTopCenter(w: number, h: number): { x: number; y: number } {
  const [cx, cy] = iso(w / 2, h / 2)
  return { x: cx, y: cy }
}

/**
 * Get a point near the top edge of the iso top face (upper ~30% region).
 * Used for surface/floating label modes that place text near the top.
 */
export function getIsoTopEdge(w: number, h: number): { x: number; y: number } {
  const [cx, cy] = iso(w * 0.3, h * 0.3)
  return { x: cx, y: cy }
}

interface FaceColors {
  top: number
  right: number
  left: number
  stroke: number
}

function faceColors(base: number): FaceColors {
  return {
    top: base,
    right: darken(base, 0.25),
    left: darken(base, 0.45),
    stroke: darken(base, 0.55),
  }
}

const STROKE_ALPHA = 0.4
const STROKE_WIDTH = 1

// ── Shared isometric cuboid ─────────────────────────────────────

/**
 * Draw a standard isometric cuboid. The top face is an iso parallelogram;
 * right and front extrusion faces extend straight down by `depth` pixels.
 */
function drawCuboidFaces(
  g: Graphics,
  w: number,
  h: number,
  depth: number,
  colors: FaceColors,
): void {
  const [tlx, tly] = iso(0, 0)
  const [trx, try_] = iso(w, 0)
  const [brx, bry] = iso(w, h)
  const [blx, bly] = iso(0, h)

  // Top face (iso parallelogram)
  g.moveTo(tlx, tly)
  g.lineTo(trx, try_)
  g.lineTo(brx, bry)
  g.lineTo(blx, bly)
  g.closePath()
  g.fill({ color: colors.top })
  g.stroke({ color: colors.stroke, width: STROKE_WIDTH, alpha: STROKE_ALPHA })

  // Right face (TR → BR edge, extruded straight down)
  g.moveTo(trx, try_)
  g.lineTo(trx, try_ + depth)
  g.lineTo(brx, bry + depth)
  g.lineTo(brx, bry)
  g.closePath()
  g.fill({ color: colors.right })
  g.stroke({ color: colors.stroke, width: STROKE_WIDTH, alpha: STROKE_ALPHA })

  // Front face (BR → BL edge, extruded straight down)
  g.moveTo(brx, bry)
  g.lineTo(brx, bry + depth)
  g.lineTo(blx, bly + depth)
  g.lineTo(blx, bly)
  g.closePath()
  g.fill({ color: colors.left })
  g.stroke({ color: colors.stroke, width: STROKE_WIDTH, alpha: STROKE_ALPHA })
}

// ── Per-kind draw functions ─────────────────────────────────────

/**
 * Step — Isometric server block with rack lines and LED dots.
 */
export function drawStepIso(g: Graphics, w: number, h: number, color: number): void {
  const depth = getIsoHeight('step')
  const c = faceColors(color)
  drawCuboidFaces(g, w, h, depth, c)

  // Rack lines across the top face (parallel to the u-axis at constant v)
  const lineCount = 3
  for (let i = 1; i <= lineCount; i++) {
    const t = i / (lineCount + 1)
    const [x1, y1] = iso(4, h * t)
    const [x2, y2] = iso(w - 4, h * t)
    g.moveTo(x1, y1)
    g.lineTo(x2, y2)
    g.stroke({ color: c.stroke, width: 0.5, alpha: 0.25 })
  }

  // LED dots on right extrusion face
  const [trx, try_] = iso(w, 0)
  const [brx, bry] = iso(w, h)
  const midX = (trx + brx) / 2 + 2
  for (let i = 0; i < 3; i++) {
    const t = 0.2 + i * 0.25
    const ledY = try_ + (bry - try_) * 0.5 + depth * t
    g.circle(midX, ledY, 1.5)
    g.fill({ color: i === 0 ? 0x22c55e : c.stroke, alpha: i === 0 ? 0.8 : 0.3 })
  }
}

/**
 * Map — 3 stacked thin isometric slabs (parallel rack).
 */
export function drawMapIso(g: Graphics, w: number, h: number, color: number): void {
  const totalDepth = getIsoHeight('map')
  const c = faceColors(color)
  const slabCount = 3
  const slabDepth = totalDepth / slabCount
  const slabFrac = 0.22 // each slab covers 22% of h
  const gap = (1 - slabCount * slabFrac) / (slabCount + 1)

  for (let i = 0; i < slabCount; i++) {
    const v0 = (gap + i * (slabFrac + gap)) * h
    const v1 = v0 + slabFrac * h

    const [tlx, tly] = iso(0, v0)
    const [trx, try_] = iso(w, v0)
    const [brx, bry] = iso(w, v1)
    const [blx, bly] = iso(0, v1)

    // Top face
    g.moveTo(tlx, tly)
    g.lineTo(trx, try_)
    g.lineTo(brx, bry)
    g.lineTo(blx, bly)
    g.closePath()
    g.fill({ color: c.top })
    g.stroke({ color: c.stroke, width: STROKE_WIDTH, alpha: STROKE_ALPHA })

    // Right face
    g.moveTo(trx, try_)
    g.lineTo(trx, try_ + slabDepth)
    g.lineTo(brx, bry + slabDepth)
    g.lineTo(brx, bry)
    g.closePath()
    g.fill({ color: c.right })
    g.stroke({ color: c.stroke, width: STROKE_WIDTH, alpha: STROKE_ALPHA })

    // Front face
    g.moveTo(brx, bry)
    g.lineTo(brx, bry + slabDepth)
    g.lineTo(blx, bly + slabDepth)
    g.lineTo(blx, bly)
    g.closePath()
    g.fill({ color: c.left })
    g.stroke({ color: c.stroke, width: STROKE_WIDTH, alpha: STROKE_ALPHA })
  }
}

/**
 * Switch — Iso-projected diamond prism with routing chevrons.
 */
export function drawSwitchIso(g: Graphics, w: number, h: number, color: number): void {
  const depth = getIsoHeight('switch')
  const c = faceColors(color)
  const cx = w / 2
  const cy = h / 2

  // Diamond vertices in ELK space → iso screen space
  const [tx, ty] = iso(cx, 0)   // top
  const [rx, ry] = iso(w, cy)   // right
  const [bx, by] = iso(cx, h)   // bottom
  const [lx, ly] = iso(0, cy)   // left

  // Top face (iso diamond)
  g.moveTo(tx, ty)
  g.lineTo(rx, ry)
  g.lineTo(bx, by)
  g.lineTo(lx, ly)
  g.closePath()
  g.fill({ color: c.top })
  g.stroke({ color: c.stroke, width: STROKE_WIDTH, alpha: STROKE_ALPHA })

  // Right face (R → B edge, extruded down)
  g.moveTo(rx, ry)
  g.lineTo(rx, ry + depth)
  g.lineTo(bx, by + depth)
  g.lineTo(bx, by)
  g.closePath()
  g.fill({ color: c.right })
  g.stroke({ color: c.stroke, width: STROKE_WIDTH, alpha: STROKE_ALPHA })

  // Front face (B → L edge, extruded down)
  g.moveTo(bx, by)
  g.lineTo(bx, by + depth)
  g.lineTo(lx, ly + depth)
  g.lineTo(lx, ly)
  g.closePath()
  g.fill({ color: c.left })
  g.stroke({ color: c.stroke, width: STROKE_WIDTH, alpha: STROKE_ALPHA })

  // Routing chevrons at center of top face
  const [ccx, ccy] = iso(cx, cy)
  const cs = 4
  g.moveTo(ccx - cs, ccy - cs)
  g.lineTo(ccx, ccy)
  g.lineTo(ccx - cs, ccy + cs)
  g.stroke({ color: c.stroke, width: 1, alpha: 0.35 })
  g.moveTo(ccx + cs, ccy - cs)
  g.lineTo(ccx, ccy)
  g.lineTo(ccx + cs, ccy + cs)
  g.stroke({ color: c.stroke, width: 1, alpha: 0.35 })
}

/**
 * Sub — Tall iso cabinet with dashed edges and a window on the right face.
 */
export function drawSubIso(g: Graphics, w: number, h: number, color: number): void {
  const depth = getIsoHeight('sub')
  const c = faceColors(color)
  drawCuboidFaces(g, w, h, depth, c)

  // Dashed edges along the top face parallelogram
  const [tlx, tly] = iso(0, 0)
  const [trx, try_] = iso(w, 0)
  const [brx, bry] = iso(w, h)
  const [blx, bly] = iso(0, h)
  const dashLen = 5
  const gapLen = 3
  drawDashedLine(g, tlx, tly, trx, try_, c.stroke, dashLen, gapLen)
  drawDashedLine(g, trx, try_, brx, bry, c.stroke, dashLen, gapLen)
  drawDashedLine(g, brx, bry, blx, bly, c.stroke, dashLen, gapLen)
  drawDashedLine(g, blx, bly, tlx, tly, c.stroke, dashLen, gapLen)

  // Window on right extrusion face
  const winX = (trx + brx) / 2 - 2
  const winY1 = (try_ + bry) / 2 + depth * 0.15
  const winY2 = winY1 + depth * 0.5
  g.rect(winX, winY1, 6, winY2 - winY1)
  g.fill({ color: c.top, alpha: 0.15 })
  g.stroke({ color: c.stroke, width: 0.5, alpha: 0.3 })
}

/**
 * Barrier — Iso-projected hexagonal prism with gate-post lines.
 */
export function drawBarrierIso(g: Graphics, w: number, h: number, color: number): void {
  const depth = getIsoHeight('barrier')
  const c = faceColors(color)
  const indent = h * 0.3

  // Hexagon vertices in ELK space → iso
  const [p0x, p0y] = iso(indent, 0)       // top-left
  const [p1x, p1y] = iso(w - indent, 0)   // top-right
  const [p2x, p2y] = iso(w, h / 2)        // right
  const [p3x, p3y] = iso(w - indent, h)   // bottom-right
  const [p4x, p4y] = iso(indent, h)       // bottom-left
  const [p5x, p5y] = iso(0, h / 2)        // left

  // Top face (iso hexagon)
  g.moveTo(p0x, p0y)
  g.lineTo(p1x, p1y)
  g.lineTo(p2x, p2y)
  g.lineTo(p3x, p3y)
  g.lineTo(p4x, p4y)
  g.lineTo(p5x, p5y)
  g.closePath()
  g.fill({ color: c.top })
  g.stroke({ color: c.stroke, width: STROKE_WIDTH, alpha: STROKE_ALPHA })

  // Visible extrusion faces (edges facing camera: p1→p2, p2→p3, p3→p4, p4→p5)

  // Right upper: p1 → p2
  g.moveTo(p1x, p1y)
  g.lineTo(p1x, p1y + depth)
  g.lineTo(p2x, p2y + depth)
  g.lineTo(p2x, p2y)
  g.closePath()
  g.fill({ color: c.right })
  g.stroke({ color: c.stroke, width: STROKE_WIDTH, alpha: STROKE_ALPHA })

  // Right lower: p2 → p3
  g.moveTo(p2x, p2y)
  g.lineTo(p2x, p2y + depth)
  g.lineTo(p3x, p3y + depth)
  g.lineTo(p3x, p3y)
  g.closePath()
  g.fill({ color: c.right })
  g.stroke({ color: c.stroke, width: STROKE_WIDTH, alpha: STROKE_ALPHA })

  // Front: p3 → p4
  g.moveTo(p3x, p3y)
  g.lineTo(p3x, p3y + depth)
  g.lineTo(p4x, p4y + depth)
  g.lineTo(p4x, p4y)
  g.closePath()
  g.fill({ color: c.left })
  g.stroke({ color: c.stroke, width: STROKE_WIDTH, alpha: STROKE_ALPHA })

  // Left-front: p4 → p5
  g.moveTo(p4x, p4y)
  g.lineTo(p4x, p4y + depth)
  g.lineTo(p5x, p5y + depth)
  g.lineTo(p5x, p5y)
  g.closePath()
  g.fill({ color: c.left })
  g.stroke({ color: c.stroke, width: STROKE_WIDTH, alpha: STROKE_ALPHA })

  // Gate-post lines on right face (p2 → p3 region)
  const postCount = 3
  for (let i = 1; i <= postCount; i++) {
    const t = i / (postCount + 1)
    const px = p2x + (p3x - p2x) * t
    const py = p2y + (p3y - p2y) * t
    g.moveTo(px, py)
    g.lineTo(px, py + depth * 0.7)
    g.stroke({ color: c.stroke, width: 0.5, alpha: 0.3 })
  }
}

/**
 * Streaming — Isometric cuboid with flow arrows on the top face.
 * Uses cuboid base (true iso cylinder is complex; cuboid is visually clear).
 */
export function drawStreamingIso(g: Graphics, w: number, h: number, color: number): void {
  const depth = getIsoHeight('streaming')
  const c = faceColors(color)
  drawCuboidFaces(g, w, h, depth, c)

  // Flow arrows on top face (along the u-axis direction)
  const [cx, cy] = iso(w / 2, h / 2)
  const arrowSize = 4
  const offsets = [-12, 0, 12]
  for (const dx of offsets) {
    const ax = cx + dx
    const ay = cy
    g.moveTo(ax - arrowSize, ay - arrowSize * 0.6)
    g.lineTo(ax, ay)
    g.lineTo(ax - arrowSize, ay + arrowSize * 0.6)
    g.stroke({ color: c.stroke, width: 1, alpha: 0.35 })
  }
}

/**
 * Pseudo — Flat isometric disc (Start/End marker).
 */
export function drawPseudoIso(g: Graphics, w: number, h: number, color: number): void {
  const depth = getIsoHeight('pseudo')
  const c = faceColors(color)
  drawCuboidFaces(g, w, h, depth, c)

  // Filled top face overlay for the indicator look
  const [tlx, tly] = iso(0, 0)
  const [trx, try_] = iso(w, 0)
  const [brx, bry] = iso(w, h)
  const [blx, bly] = iso(0, h)
  g.moveTo(tlx, tly)
  g.lineTo(trx, try_)
  g.lineTo(brx, bry)
  g.lineTo(blx, bly)
  g.closePath()
  g.fill({ color, alpha: 0.15 })
}

/**
 * Draw the appropriate iso shape for a node kind.
 */
export function drawIsoShape(g: Graphics, kind: string, w: number, h: number, color: number): void {
  switch (kind) {
    case 'map':
      drawMapIso(g, w, h, color)
      break
    case 'switch':
      drawSwitchIso(g, w, h, color)
      break
    case 'sub':
      drawSubIso(g, w, h, color)
      break
    case 'barrier':
      drawBarrierIso(g, w, h, color)
      break
    case 'streaming':
      drawStreamingIso(g, w, h, color)
      break
    case 'pseudo':
      drawPseudoIso(g, w, h, color)
      break
    default:
      drawStepIso(g, w, h, color)
      break
  }
}

/**
 * Draw an isometric glow around a shape (for selection/status).
 * Traces the visible 3D silhouette of each kind's iso shape,
 * expanded outward so the glow border is fully visible around
 * the opaque shape underneath.
 */
export function drawIsoGlow(
  g: Graphics,
  kind: string,
  w: number,
  h: number,
  color: number,
  alpha = 0.15,
): void {
  const depth = getIsoHeight(kind)
  const silhouette = expandPolygon(isoSilhouette(kind, w, h, depth), 3)

  // Draw the glow as an overlay ON TOP of the iso shape.
  // Fill adds a visible color wash; stroke provides a bright border.
  g.moveTo(silhouette[0]![0], silhouette[0]![1])
  for (let i = 1; i < silhouette.length; i++) {
    g.lineTo(silhouette[i]![0], silhouette[i]![1])
  }
  g.closePath()
  g.fill({ color, alpha: alpha * 0.6 })
  g.stroke({ color: 0xffffff, width: 2, alpha: Math.min(alpha * 2.5, 0.9) })
}

/**
 * Push each vertex of a polygon outward from its centroid by `px` pixels.
 */
function expandPolygon(
  pts: Array<[number, number]>,
  px: number,
): Array<[number, number]> {
  const cx = pts.reduce((s, p) => s + p[0], 0) / pts.length
  const cy = pts.reduce((s, p) => s + p[1], 0) / pts.length
  return pts.map(([x, y]) => {
    const dx = x - cx
    const dy = y - cy
    const len = Math.sqrt(dx * dx + dy * dy)
    if (len === 0) return [x, y] as [number, number]
    return [x + (dx / len) * px, y + (dy / len) * px] as [number, number]
  })
}

/**
 * Compute the visible 3D silhouette polygon for a given kind.
 * The silhouette traces the outer edge of the top face + extruded sides,
 * forming the painter's-algorithm outline of the shape as seen from camera.
 *
 * For a cuboid: TL → TR → TR+d → BR+d → BL+d → BL
 * For a diamond: T → R → R+d → B+d → L+d → L
 * For a hexagon: p0 → p1 → p1+d → p2+d → p3+d → p4+d → p5+d → p5
 */
function isoSilhouette(
  kind: string,
  w: number,
  h: number,
  depth: number,
): Array<[number, number]> {
  switch (kind) {
    case 'switch': {
      const cx = w / 2
      const cy = h / 2
      const [tx, ty] = iso(cx, 0)
      const [rx, ry] = iso(w, cy)
      const [bx, by] = iso(cx, h)
      const [lx, ly] = iso(0, cy)
      return [
        [tx, ty],
        [rx, ry],
        [rx, ry + depth],
        [bx, by + depth],
        [lx, ly + depth],
        [lx, ly],
      ]
    }
    case 'barrier': {
      const indent = h * 0.3
      const [p0x, p0y] = iso(indent, 0)
      const [p1x, p1y] = iso(w - indent, 0)
      const [p2x, p2y] = iso(w, h / 2)
      const [p3x, p3y] = iso(w - indent, h)
      const [p4x, p4y] = iso(indent, h)
      const [p5x, p5y] = iso(0, h / 2)
      return [
        [p0x, p0y],
        [p1x, p1y],
        [p1x, p1y + depth],
        [p2x, p2y + depth],
        [p3x, p3y + depth],
        [p4x, p4y + depth],
        [p5x, p5y + depth],
        [p5x, p5y],
      ]
    }
    default: {
      // Cuboid silhouette (step, map, sub, streaming)
      const [tlx, tly] = iso(0, 0)
      const [trx, try_] = iso(w, 0)
      const [brx, bry] = iso(w, h)
      const [blx, bly] = iso(0, h)
      return [
        [tlx, tly],
        [trx, try_],
        [trx, try_ + depth],
        [brx, bry + depth],
        [blx, bly + depth],
        [blx, bly],
      ]
    }
  }
}

// ── Helpers ─────────────────────────────────────────────────────

function drawDashedLine(
  g: Graphics,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  color: number,
  dashLen: number,
  gapLen: number,
): void {
  const dx = x2 - x1
  const dy = y2 - y1
  const len = Math.sqrt(dx * dx + dy * dy)
  if (len === 0) return
  const ux = dx / len
  const uy = dy / len
  let pos = 0
  let drawing = true

  while (pos < len) {
    const segLen = drawing ? dashLen : gapLen
    const end = Math.min(pos + segLen, len)
    if (drawing) {
      g.moveTo(x1 + ux * pos, y1 + uy * pos)
      g.lineTo(x1 + ux * end, y1 + uy * end)
      g.stroke({ color, width: 0.8, alpha: 0.5 })
    }
    pos = end
    drawing = !drawing
  }
}

