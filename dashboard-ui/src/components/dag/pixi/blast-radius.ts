import type { DagLayout } from '@/types/dag'
import type { PixiNode, PixiEdge } from './types'

interface BlastResult {
  affectedNodes: Set<string>
  affectedEdges: Set<string>
}

/**
 * Compute blast radius via BFS from a failed node.
 * Traverses both upstream (backward) and downstream (forward).
 */
export function computeBlastRadius(
  layout: DagLayout,
  failedNodeId: string,
): BlastResult {
  // Build adjacency maps
  const forward = new Map<string, string[]>() // source → targets
  const backward = new Map<string, string[]>() // target → sources
  const edgeIds = new Map<string, string>() // "source->target" → edge id

  for (const edge of layout.edges) {
    const fwd = forward.get(edge.source) ?? []
    fwd.push(edge.target)
    forward.set(edge.source, fwd)

    const bwd = backward.get(edge.target) ?? []
    bwd.push(edge.source)
    backward.set(edge.target, bwd)

    edgeIds.set(`${edge.source}->${edge.target}`, edge.id)
  }

  const affectedNodes = new Set<string>()
  const affectedEdges = new Set<string>()

  // BFS forward (downstream from failed)
  const fwdQueue = [failedNodeId]
  while (fwdQueue.length > 0) {
    const node = fwdQueue.shift()!
    if (affectedNodes.has(node)) continue
    affectedNodes.add(node)

    const targets = forward.get(node) ?? []
    for (const target of targets) {
      const eid = edgeIds.get(`${node}->${target}`)
      if (eid) affectedEdges.add(eid)
      if (!affectedNodes.has(target)) fwdQueue.push(target)
    }
  }

  // BFS backward (upstream from failed)
  const bwdQueue = [failedNodeId]
  const visited = new Set<string>()
  while (bwdQueue.length > 0) {
    const node = bwdQueue.shift()!
    if (visited.has(node)) continue
    visited.add(node)
    affectedNodes.add(node)

    const sources = backward.get(node) ?? []
    for (const source of sources) {
      const eid = edgeIds.get(`${source}->${node}`)
      if (eid) affectedEdges.add(eid)
      if (!visited.has(source)) bwdQueue.push(source)
    }
  }

  return { affectedNodes, affectedEdges }
}

/**
 * Apply blast radius visualization: dim non-affected, highlight affected.
 */
export function applyBlastRadius(
  result: BlastResult,
  nodes: Map<string, PixiNode>,
  edges: Map<string, PixiEdge>,
  _failedNodeId: string,
): void {
  const DIM_ALPHA = 0.15

  for (const [id, node] of nodes) {
    if (result.affectedNodes.has(id)) {
      node.container.alpha = 1
    } else {
      node.container.alpha = DIM_ALPHA
    }
  }

  for (const [id, edge] of edges) {
    if (result.affectedEdges.has(id)) {
      edge.main.alpha = 1
      edge.dash.alpha = 1
      edge.arrow.alpha = 1
    } else {
      edge.main.alpha = DIM_ALPHA
      edge.dash.alpha = DIM_ALPHA
      edge.arrow.alpha = DIM_ALPHA
    }
  }
}

/**
 * Remove blast radius visualization, restoring normal alphas.
 */
export function clearBlastRadius(
  nodes: Map<string, PixiNode>,
  edges: Map<string, PixiEdge>,
): void {
  for (const [, node] of nodes) {
    node.container.alpha = 1
  }
  for (const [, edge] of edges) {
    edge.main.alpha = 0.6
    edge.dash.alpha = 1
    edge.arrow.alpha = 1
  }
}
