/**
 * Isometric projection utilities — pure math, no PixiJS dependency.
 *
 * Uses manual projection (no world-container rotation) so labels stay
 * horizontal and hit areas match visuals.
 *
 * Core projection (mirrored for left-to-right flow with DOWN ELK layout):
 *   screenX = (y - x) * cos(30°)
 *   screenY = (x + y) * sin(30°) - z
 */

const COS30 = Math.cos(Math.PI / 6) // ~0.866
const SIN30 = Math.sin(Math.PI / 6) // 0.5

export interface IsoPoint {
  x: number
  y: number
}

/**
 * Project a 2D ELK position (with optional z height) into isometric screen space.
 */
export function isoProject(x: number, y: number, z = 0): IsoPoint {
  return {
    x: (y - x) * COS30,
    y: (x + y) * SIN30 - z,
  }
}

/**
 * Unproject screen coords back to 2D ELK space (z=0 plane).
 */
export function isoUnproject(screenX: number, screenY: number): IsoPoint {
  // Inverse of: sx = (y-x)*cos30, sy = (x+y)*sin30
  // y-x = sx/cos30, x+y = sy/sin30
  const diff = screenX / COS30
  const sum = screenY / SIN30
  return {
    x: (sum - diff) / 2,
    y: (sum + diff) / 2,
  }
}

/**
 * Compute the screen-space bounding box of an isometric-projected rectangle.
 */
export function isoBounds(
  layoutWidth: number,
  layoutHeight: number,
): { width: number; height: number; offsetX: number; offsetY: number } {
  // Project the four corners of the layout rect
  const tl = isoProject(0, 0)
  const tr = isoProject(layoutWidth, 0)
  const bl = isoProject(0, layoutHeight)
  const br = isoProject(layoutWidth, layoutHeight)

  const minX = Math.min(tl.x, tr.x, bl.x, br.x)
  const maxX = Math.max(tl.x, tr.x, bl.x, br.x)
  const minY = Math.min(tl.y, tr.y, bl.y, br.y)
  const maxY = Math.max(tl.y, tr.y, bl.y, br.y)

  return {
    width: maxX - minX,
    height: maxY - minY,
    offsetX: minX,
    offsetY: minY,
  }
}

/**
 * Darken a hex color by a factor (0 = no change, 1 = black).
 */
export function darken(color: number, factor: number): number {
  const r = (color >> 16) & 0xff
  const g = (color >> 8) & 0xff
  const b = color & 0xff
  const f = 1 - factor
  return (Math.round(r * f) << 16) | (Math.round(g * f) << 8) | Math.round(b * f)
}

/**
 * Lighten a hex color by a factor (0 = no change, 1 = white).
 */
export function lighten(color: number, factor: number): number {
  const r = (color >> 16) & 0xff
  const g = (color >> 8) & 0xff
  const b = color & 0xff
  return (
    (Math.round(r + (255 - r) * factor) << 16) |
    (Math.round(g + (255 - g) * factor) << 8) |
    Math.round(b + (255 - b) * factor)
  )
}

/**
 * Depth-sort key: nodes with higher (elkX + elkY) are closer to camera
 * and should render later (on top in painter's algorithm for back-to-front).
 */
export function isoSortKey(elkX: number, elkY: number): number {
  return elkX + elkY
}
