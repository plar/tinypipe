/**
 * Edge projection for isometric mode.
 *
 * Transforms ELK polyline points into iso screen coordinates
 * with a slight z elevation so edges float above the ground grid.
 */

import { isoProject } from './iso-projection'
import type { IsoPoint } from './iso-projection'

const EDGE_ELEVATION = 2

/**
 * Project an array of ELK edge points into isometric screen space.
 */
export function projectEdgePoints(
  points: Array<{ x: number; y: number }>,
): IsoPoint[] {
  return points.map((p) => isoProject(p.x, p.y, EDGE_ELEVATION))
}

/**
 * Project all edge paths for the particle system.
 * Returns arrays of screen-space points matching the particle system's expected format.
 */
export function projectAllEdgePaths(
  edgePaths: Array<Array<{ x: number; y: number }>>,
): Array<Array<{ x: number; y: number }>> {
  return edgePaths.map(projectEdgePoints)
}
