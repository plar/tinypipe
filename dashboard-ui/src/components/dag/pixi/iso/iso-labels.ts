/**
 * Label positioning and transforms for isometric mode.
 *
 * Three configurable modes:
 *   - surface  (default): full isometric projection — text appears "painted" on the top face
 *   - rotated:  simple -30° tilt aligning with the top-left edge
 *   - floating: horizontal text floating above the shape
 */

import { Graphics, Text } from 'pixi.js'
import { getIsoTopCenter, getIsoTopEdge, getIsoHeight } from './iso-shapes'

export type IsoLabelMode = 'surface' | 'rotated' | 'floating'

const PILL_PAD_X = 6
const PILL_PAD_Y = 2
const PILL_RADIUS = 3
const PILL_ALPHA = 0.8

const ISO_ANGLE = Math.PI / 6 // 30°

/** All parameters needed to position + transform a label in iso mode. */
export interface IsoLabelConfig {
  x: number
  y: number
  rotation: number
  skewX: number
  skewY: number
  anchorX: number
  anchorY: number
}

/**
 * Compute full label config (position + transform) for a given mode.
 *
 * Surface: rotation = -30°, skew.x = -30° — maps text onto the isometric
 *          top face (baseline follows reversed width edge, height follows
 *          depth edge). Produces a parallelogram look.
 *
 * Rotated: rotation = -30° only — text tilts to follow the top-left edge
 *          of the top face without perspective distortion.
 *
 * Floating: no transform — horizontal text hovering above the shape apex.
 */
export function getIsoLabelConfig(
  w: number,
  h: number,
  kind: string,
  mode: IsoLabelMode,
): IsoLabelConfig {
  switch (mode) {
    case 'surface': {
      const top = getIsoTopEdge(w, h)
      return {
        x: top.x,
        y: top.y,
        rotation: -ISO_ANGLE,
        skewX: -ISO_ANGLE,
        skewY: 0,
        anchorX: 0.5,
        anchorY: 0.5,
      }
    }
    case 'rotated': {
      const center = getIsoTopCenter(w, h)
      return {
        x: center.x,
        y: center.y,
        rotation: -ISO_ANGLE,
        skewX: ISO_ANGLE,
        skewY: 0,
        anchorX: 0.5,
        anchorY: 0.5,
      }
    }
    case 'floating': {
      const top = getIsoTopEdge(w, h)
      const isoH = getIsoHeight(kind)
      return {
        x: top.x,
        y: -isoH - 4,
        rotation: 0,
        skewX: 0,
        skewY: 0,
        anchorX: 0.5,
        anchorY: 0.5,
      }
    }
  }
}

/**
 * Create a background pill behind a label for iso mode readability.
 */
export function createIsoPill(_cardColor: number): Graphics {
  const pill = new Graphics()
  pill.label = 'iso-pill'
  pill.visible = false
  return pill
}

/**
 * Update pill to match the label. Accepts explicit width so we
 * don't depend on getBounds() which can return zero before first render.
 */
export function updateIsoPill(
  pill: Graphics,
  label: Text,
  cardColor: number,
  _nodeWidth: number,
): void {
  pill.clear()

  // Use actual measured width if available, otherwise estimate
  const measuredWidth = label.width > 0 ? label.width : (label.text?.length ?? 10) * 7 + 4
  const w = measuredWidth + PILL_PAD_X * 2
  const h = (label.height > 0 ? label.height : 16) + PILL_PAD_Y * 2

  // Pill is centered on the label position (anchor 0.5, 0.5).
  pill.roundRect(-w / 2, -h / 2, w, h, PILL_RADIUS)
  pill.fill({ color: cardColor, alpha: PILL_ALPHA })
}
