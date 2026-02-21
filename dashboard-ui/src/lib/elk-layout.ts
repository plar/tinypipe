import ELK from 'elkjs/lib/elk.bundled.js'
import type { PipelineTopology, VisualASTData } from '@/types'
import type {
  ElkGraph,
  ElkNode,
  ElkLayoutGraph,
  ElkLayoutNode,
  ElkPoint,
  DagLayout,
  RenderedNode,
  RenderedEdge,
  RenderedGroup,
} from '@/types/dag'

const NODE_WIDTH = 160
const NODE_HEIGHT = 48

const LAYOUT_OPTIONS: Record<string, string> = {
  'elk.algorithm': 'layered',
  'elk.direction': 'RIGHT',
  'elk.spacing.nodeNode': '40',
  'elk.layered.spacing.nodeNodeBetweenLayers': '60',
  'elk.edgeRouting': 'ORTHOGONAL',
  'elk.layered.nodePlacement.strategy': 'NETWORK_SIMPLEX',
  'elk.hierarchyHandling': 'INCLUDE_CHILDREN',
}

/* ── AST layout options (vertical, top-to-bottom) ─────────── */

const AST_LAYOUT_OPTIONS: Record<string, string> = {
  'elk.algorithm': 'layered',
  'elk.direction': 'DOWN',
  'elk.spacing.nodeNode': '40',
  'elk.layered.spacing.nodeNodeBetweenLayers': '50',
  'elk.edgeRouting': 'ORTHOGONAL',
  'elk.layered.nodePlacement.strategy': 'LINEAR_SEGMENTS',
  'elk.hierarchyHandling': 'INCLUDE_CHILDREN',
  'elk.layered.crossingMinimization.strategy': 'LAYER_SWEEP',
  'elk.layered.crossingMinimization.greedySwitch.type': 'TWO_SIDED',
  'elk.portAlignment.default': 'CENTER',
  'elk.spacing.portPort': '10',
}

/* ── Variable node sizes per kind ─────────────────────────── */

const NODE_SIZES: Record<string, { w: number; h: number }> = {
  step: { w: 160, h: 48 },
  streaming: { w: 160, h: 48 },
  switch: { w: 140, h: 56 },
  map: { w: 180, h: 56 },
  sub: { w: 200, h: 56 },
  barrier: { w: 160, h: 48 },
  pseudo: { w: 80, h: 36 },
}

function getNodeSize(kind: string): { w: number; h: number } {
  return NODE_SIZES[kind] ?? NODE_SIZES.step!
}

/* ── ELK instance (singleton, runs on main thread) ────────── */

const elk = new ELK()

/* ── Human-readable label formatting ─────────────────────── */

function toHumanLabel(snakeCase: string): string {
  return snakeCase
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

/* ── Topology → ELK graph conversion (legacy) ────────────── */

function toElkGraph(topology: PipelineTopology): ElkGraph {
  const children = Object.entries(topology.nodes).map(([name]) => ({
    id: name,
    width: NODE_WIDTH,
    height: NODE_HEIGHT,
    labels: [{ text: name }],
    layoutOptions: { 'elk.portConstraints': 'FIXED_ORDER' },
  }))

  const edges: ElkGraph['edges'] = []
  for (const [source, node] of Object.entries(topology.nodes)) {
    for (const target of node.targets) {
      edges.push({
        id: `${source}->${target}`,
        sources: [source],
        targets: [target],
      })
    }
  }

  return {
    id: 'root',
    children,
    edges,
    layoutOptions: LAYOUT_OPTIONS,
  }
}

/* ── VisualAST → ELK graph conversion ────────────────────── */

function astToElkGraph(ast: VisualASTData): ElkGraph {
  const children: ElkNode[] = []
  const edges: ElkGraph['edges'] = []

  // Pseudo start/end node IDs
  const START_ID = '__start__'
  const END_ID = '__end__'

  // Add pseudo start node (only SOUTH output port)
  const pseudoSize = getNodeSize('pseudo')
  children.push({
    id: START_ID,
    width: pseudoSize.w,
    height: pseudoSize.h,
    labels: [{ text: '\u25B6 Start' }],
    ports: [{ id: `${START_ID}__out`, layoutOptions: { 'elk.port.side': 'SOUTH' } }],
    layoutOptions: {
      'elk.portConstraints': 'FIXED_SIDE',
      'elk.portAlignment.south': 'CENTER',
    },
  })

  // Collect entry and terminal nodes
  const entryNodes: string[] = []
  const terminalNodes: string[] = []

  // Build parallel group membership: node → group ID
  const nodeToGroup = new Map<string, string>()
  for (const group of ast.parallel_groups) {
    for (const nodeId of group.node_ids) {
      nodeToGroup.set(nodeId, group.id)
    }
  }

  // Group children by parallel group
  const groupChildren = new Map<string, ElkNode[]>()
  for (const group of ast.parallel_groups) {
    groupChildren.set(group.id, [])
  }

  // Add regular nodes
  for (const [name, node] of Object.entries(ast.nodes)) {
    if (node.is_isolated) continue

    const size = getNodeSize(node.kind)
    let label = toHumanLabel(name)
    if (node.barrier_type === 'any') {
      label += ' (Any)'
    }

    const elkNode: ElkNode = {
      id: name,
      width: size.w,
      height: size.h,
      labels: [{ text: label }],
    }

    // All nodes: centered NORTH input + SOUTH output
    elkNode.ports = [
      { id: `${name}__in`, layoutOptions: { 'elk.port.side': 'NORTH' } },
      { id: `${name}__out`, layoutOptions: { 'elk.port.side': 'SOUTH' } },
    ]
    elkNode.layoutOptions = {
      'elk.portConstraints': 'FIXED_SIDE',
      'elk.portAlignment.north': 'CENTER',
      'elk.portAlignment.south': 'CENTER',
    }

    if (node.is_entry) entryNodes.push(name)
    if (node.is_terminal) terminalNodes.push(name)

    // Add to parallel group or root
    const groupId = nodeToGroup.get(name)
    if (groupId) {
      groupChildren.get(groupId)!.push(elkNode)
    } else {
      children.push(elkNode)
    }
  }

  // Add parallel groups as compound nodes
  for (const group of ast.parallel_groups) {
    const groupNodes = groupChildren.get(group.id) ?? []
    if (groupNodes.length === 0) continue

    children.push({
      id: group.id,
      width: 0,
      height: 0,
      labels: [{ text: 'Parallel' }],
      children: groupNodes,
      ports: [
        { id: `${group.id}__in`, layoutOptions: { 'elk.port.side': 'NORTH' } },
        { id: `${group.id}__out`, layoutOptions: { 'elk.port.side': 'SOUTH' } },
      ],
      layoutOptions: {
        'elk.algorithm': 'layered',
        'elk.direction': 'RIGHT',
        'elk.spacing.nodeNode': '30',
        'elk.layered.spacing.nodeNodeBetweenLayers': '40',
        'elk.padding': '[top=30,left=16,bottom=16,right=16]',
        'elk.portConstraints': 'FIXED_SIDE',
        'elk.portAlignment.north': 'CENTER',
        'elk.portAlignment.south': 'CENTER',
      },
    })
  }

  // Add pseudo end node (only NORTH input port)
  children.push({
    id: END_ID,
    width: pseudoSize.w,
    height: pseudoSize.h,
    labels: [{ text: '\u25A0 End' }],
    ports: [{ id: `${END_ID}__in`, layoutOptions: { 'elk.port.side': 'NORTH' } }],
    layoutOptions: {
      'elk.portConstraints': 'FIXED_SIDE',
      'elk.portAlignment.north': 'CENTER',
    },
  })

  // Connect Start → entry nodes
  for (const entry of entryNodes) {
    const targetId = nodeToGroup.get(entry) ?? entry
    edges.push({
      id: `${START_ID}->${entry}`,
      sources: [START_ID],
      targets: [targetId],
      sourcePort: `${START_ID}__out`,
      targetPort: `${targetId}__in`,
    })
  }

  // Connect terminal nodes → End
  for (const terminal of terminalNodes) {
    const sourceId = nodeToGroup.get(terminal) ?? terminal
    edges.push({
      id: `${terminal}->${END_ID}`,
      sources: [sourceId],
      targets: [END_ID],
      sourcePort: `${sourceId}__out`,
      targetPort: `${END_ID}__in`,
    })
  }

  // Add edges from AST (deduplicate resolved group edges)
  const seenEdgeKeys = new Set<string>()
  for (const edge of ast.edges) {
    // Skip edges to/from isolated nodes
    const sourceNode = ast.nodes[edge.source]
    const targetNode = ast.nodes[edge.target]
    if (sourceNode?.is_isolated || targetNode?.is_isolated) continue

    // Resolve group membership for edge routing
    const sourceId = nodeToGroup.get(edge.source) ?? edge.source
    const targetId = nodeToGroup.get(edge.target) ?? edge.target

    // Skip edges within the same group (ELK handles internal layout)
    if (sourceId === targetId && nodeToGroup.has(edge.source)) continue

    // Deduplicate: when multiple group members connect to the same external
    // node, only create one edge between the group and that node
    const edgeKey = `${sourceId}->${targetId}`
    if (seenEdgeKeys.has(edgeKey)) continue
    seenEdgeKeys.add(edgeKey)

    const elkEdge: ElkGraph['edges'][0] = {
      id: edgeKey,
      sources: [sourceId],
      targets: [targetId],
      sourcePort: `${sourceId}__out`,
      targetPort: `${targetId}__in`,
    }
    if (edge.label) {
      elkEdge.labels = [{ text: edge.label }]
    }
    edges.push(elkEdge)
  }

  return {
    id: 'root',
    children,
    edges,
    layoutOptions: AST_LAYOUT_OPTIONS,
  }
}

/* ── Post-processing ──────────────────────────────────────── */

function flattenEdgePoints(sections: ElkLayoutGraph['edges'][0]['sections']): ElkPoint[] {
  if (!sections || sections.length === 0) return []
  const points: ElkPoint[] = []
  for (const section of sections) {
    points.push(section.startPoint)
    if (section.bendPoints) {
      points.push(...section.bendPoints)
    }
    points.push(section.endPoint)
  }
  return points
}

/** Flatten compound node children to world-space coordinates */
function flattenCompoundNodes(
  layoutChildren: ElkLayoutNode[],
  offsetX = 0,
  offsetY = 0,
): { flatNodes: ElkLayoutNode[]; groups: RenderedGroup[] } {
  const flatNodes: ElkLayoutNode[] = []
  const groups: RenderedGroup[] = []

  for (const child of layoutChildren) {
    const worldX = (child.x ?? 0) + offsetX
    const worldY = (child.y ?? 0) + offsetY

    if (child.children && child.children.length > 0) {
      // This is a compound (group) node
      groups.push({
        id: child.id,
        label: child.labels?.[0]?.text ?? 'Parallel',
        x: worldX,
        y: worldY,
        width: child.width ?? 200,
        height: child.height ?? 100,
        kind: 'parallel',
      })

      // Recurse into children
      const inner = flattenCompoundNodes(
        child.children as ElkLayoutNode[],
        worldX,
        worldY,
      )
      flatNodes.push(...inner.flatNodes)
      groups.push(...inner.groups)
    } else {
      flatNodes.push({ ...child, x: worldX, y: worldY })
    }
  }

  return { flatNodes, groups }
}

/* ── Public API ───────────────────────────────────────────── */

export async function computeLayout(topology: PipelineTopology): Promise<DagLayout> {
  const elkGraph = toElkGraph(topology)
  const result = (await elk.layout(elkGraph)) as unknown as ElkLayoutGraph

  const nodeKindMap: Record<string, string> = {}
  for (const [name, node] of Object.entries(topology.nodes)) {
    nodeKindMap[name] = node.kind
  }

  const nodes: RenderedNode[] = (result.children ?? []).map((n) => ({
    id: n.id,
    label: n.id,
    kind: nodeKindMap[n.id] ?? 'step',
    x: n.x ?? 0,
    y: n.y ?? 0,
    width: n.width ?? NODE_WIDTH,
    height: n.height ?? NODE_HEIGHT,
  }))

  const edges: RenderedEdge[] = (result.edges ?? [])
    .filter((e) => e.sources[0] && e.targets[0])
    .map((e) => ({
      id: e.id,
      source: e.sources[0]!,
      target: e.targets[0]!,
      points: flattenEdgePoints(e.sections),
    }))

  let maxX = 0
  let maxY = 0
  for (const n of nodes) {
    maxX = Math.max(maxX, n.x + n.width)
    maxY = Math.max(maxY, n.y + n.height)
  }

  return {
    nodes,
    edges,
    groups: [],
    width: maxX + 40,
    height: maxY + 40,
  }
}

export async function computeLayoutFromAST(
  ast: VisualASTData,
): Promise<DagLayout> {
  const elkGraph = astToElkGraph(ast)
  const result = (await elk.layout(elkGraph)) as unknown as ElkLayoutGraph

  // Build kind map from AST
  const astKindMap: Record<string, string> = {}
  for (const [name, node] of Object.entries(ast.nodes)) {
    astKindMap[name] = node.kind
  }

  // Flatten compound nodes to world coordinates
  const { flatNodes, groups } = flattenCompoundNodes(result.children ?? [])

  // Build AST node lookup for metadata
  const astNodeMap = ast.nodes

  const nodes: RenderedNode[] = flatNodes.map((n) => {
    const astNode = astNodeMap[n.id]
    const isPseudo = n.id === '__start__' || n.id === '__end__'
    const pseudoKind = n.id === '__start__' ? 'start' as const : n.id === '__end__' ? 'end' as const : undefined

    return {
      id: n.id,
      label: n.labels?.[0]?.text ?? n.id,
      kind: isPseudo ? 'pseudo' : (astKindMap[n.id] ?? 'step'),
      x: n.x ?? 0,
      y: n.y ?? 0,
      width: n.width ?? NODE_WIDTH,
      height: n.height ?? NODE_HEIGHT,
      isEntry: astNode?.is_entry,
      isTerminal: astNode?.is_terminal,
      barrierType: astNode?.barrier_type,
      isPseudo,
      pseudoKind,
    }
  })

  // Build edge lookup from AST for metadata
  const astEdgeMap = new Map<string, typeof ast.edges[0]>()
  for (const edge of ast.edges) {
    astEdgeMap.set(`${edge.source}->${edge.target}`, edge)
  }

  const edges: RenderedEdge[] = (result.edges ?? [])
    .filter((e) => e.sources[0] && e.targets[0])
    .map((e) => {
      const astEdge = astEdgeMap.get(e.id)
      return {
        id: e.id,
        source: e.sources[0]!,
        target: e.targets[0]!,
        points: flattenEdgePoints(e.sections),
        label: astEdge?.label ?? e.labels?.[0]?.text,
        isMapEdge: astEdge?.is_map_edge,
      }
    })

  let maxX = 0
  let maxY = 0
  for (const n of nodes) {
    maxX = Math.max(maxX, n.x + n.width)
    maxY = Math.max(maxY, n.y + n.height)
  }
  for (const g of groups) {
    maxX = Math.max(maxX, g.x + g.width)
    maxY = Math.max(maxY, g.y + g.height)
  }

  return {
    nodes,
    edges,
    groups,
    width: maxX + 40,
    height: maxY + 40,
  }
}
