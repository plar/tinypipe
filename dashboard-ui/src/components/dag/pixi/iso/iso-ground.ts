/**
 * Isometric ground grid and node shadows.
 */

import { Graphics } from 'pixi.js'
import { isoProject } from './iso-projection'

const GRID_SPACING = 60
const GRID_COLOR = 0x888888
const GRID_ALPHA = 0.06
const GRID_PADDING = 200

/**
 * Draw an isometric grid on the ground plane.
 * Grid lines follow the iso axes (diagonal on screen).
 */
export function drawGroundGrid(
  g: Graphics,
  layoutWidth: number,
  layoutHeight: number,
): void {
  g.clear()

  const minX = -GRID_PADDING
  const maxX = layoutWidth + GRID_PADDING
  const minY = -GRID_PADDING
  const maxY = layoutHeight + GRID_PADDING

  // Lines along the X-axis direction
  for (let y = minY; y <= maxY; y += GRID_SPACING) {
    const start = isoProject(minX, y)
    const end = isoProject(maxX, y)
    g.moveTo(start.x, start.y)
    g.lineTo(end.x, end.y)
    g.stroke({ color: GRID_COLOR, width: 0.5, alpha: GRID_ALPHA })
  }

  // Lines along the Y-axis direction
  for (let x = minX; x <= maxX; x += GRID_SPACING) {
    const start = isoProject(x, minY)
    const end = isoProject(x, maxY)
    g.moveTo(start.x, start.y)
    g.lineTo(end.x, end.y)
    g.stroke({ color: GRID_COLOR, width: 0.5, alpha: GRID_ALPHA })
  }
}

/**
 * Draw a shadow for a single node on the ground plane.
 * Shadow is a darkened parallelogram offset from the node's iso position.
 */
export function drawNodeShadow(
  g: Graphics,
  elkX: number,
  elkY: number,
  w: number,
  h: number,
  _kindColor: number,
): void {
  const shadowOffset = 8

  // Project the four corners of the node rect, shifted down on z-axis
  const tl = isoProject(elkX, elkY, -shadowOffset)
  const tr = isoProject(elkX + w, elkY, -shadowOffset)
  const bl = isoProject(elkX, elkY + h, -shadowOffset)
  const br = isoProject(elkX + w, elkY + h, -shadowOffset)

  g.moveTo(tl.x, tl.y)
  g.lineTo(tr.x, tr.y)
  g.lineTo(br.x, br.y)
  g.lineTo(bl.x, bl.y)
  g.closePath()
  g.fill({ color: 0x000000, alpha: 0.12 })
}
