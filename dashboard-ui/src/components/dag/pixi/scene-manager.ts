import { Application, Container, Graphics, Text, TextStyle } from 'pixi.js'
import type { DagLayout, RenderedGroup } from '@/types/dag'
import type { PixiNode, PixiEdge, DagSceneState } from './types'
import { resolveAllColors } from './color-bridge'
import { drawNodeShape, drawNodeGlow, kindColorKey } from './node-renderer'
import { createLabel, createKindBadge } from './label-renderer'
import { drawEdgeLine, drawEdgeDash, drawEdgeWithProgress, drawArrow, EdgeAnimator } from './edge-renderer'
import { InteractionManager } from './interaction-manager'
import { ParticleSystem } from './particle-system'
import { IsometricScene } from './iso/iso-scene'
import { computeBlastRadius, applyBlastRadius, clearBlastRadius } from './blast-radius'

/**
 * Central orchestrator for the PixiJS DAG scene.
 * Bridges Vue reactivity → imperative PixiJS API.
 */
export class SceneManager {
  app: Application
  private world: Container
  private edgeLayer: Container
  private groupLayer: Container
  private nodeLayer: Container
  private interaction: InteractionManager
  private edgeAnimator: EdgeAnimator
  private particles: ParticleSystem
  private colors: Record<string, number> = {}
  private edgeSourceMap = new Map<string, number[]>()
  private edgeIdToIndex = new Map<string, number>()
  private replayEdgesActive = false
  private activeReplayEdges = new Set<string>()
  private replayParticleTimer = 0
  private replayTimeMs = 0
  private replayTimings: Record<string, { startMs: number; endMs: number }> | null = null
  private isoScene: IsometricScene

  private state: DagSceneState = {
    layout: null,
    nodes: new Map(),
    edges: new Map(),
    selectedNode: null,
    hoveredNode: null,
    stepStatuses: {},
    particlesEnabled: false,
    isometric: false,
    blastRadiusNode: null,
  }

  // External callbacks
  private onNodeSelect: ((id: string | null) => void) | null = null
  private onNodeHover: ((id: string | null) => void) | null = null
  private onNodeDoubleClick: ((id: string) => void) | null = null

  constructor(app: Application, canvas: HTMLCanvasElement) {
    this.app = app

    // Scene graph: app.stage → viewport (pan/zoom) → world (isometric) → [edgeLayer, groupLayer, particleLayer, nodeLayer]
    const viewport = new Container()
    this.world = new Container()
    this.edgeLayer = new Container()
    this.groupLayer = new Container()
    this.nodeLayer = new Container()
    this.world.addChild(this.edgeLayer)
    this.world.addChild(this.groupLayer)

    // Resolve theme colors
    this.colors = resolveAllColors()

    // Particles (between edges and nodes)
    this.particles = new ParticleSystem(this.colors.info ?? 0x3b82f6)
    this.world.addChild(this.particles.container)

    this.world.addChild(this.nodeLayer)
    viewport.addChild(this.world)
    app.stage.addChild(viewport)

    // Interaction — operates on viewport so it doesn't conflict with isometric transforms on world
    this.interaction = new InteractionManager(viewport, canvas)

    // Isometric scene
    this.isoScene = new IsometricScene()

    // Edge animation + iso updates
    this.edgeAnimator = new EdgeAnimator()
    app.ticker.add((ticker) => {
      this.edgeAnimator.update(ticker)
      this.particles.update(ticker)
      this.isoScene.update(this.state, this.colors)
      this.renderReplayEdges()
      this.tickReplayParticles(ticker.deltaMS)
    })
  }

  /** Set callbacks for node interactions */
  setCallbacks(opts: {
    onSelect?: (id: string | null) => void
    onHover?: (id: string | null) => void
    onDoubleClick?: (id: string) => void
  }): void {
    this.onNodeSelect = opts.onSelect ?? null
    this.onNodeHover = opts.onHover ?? null
    this.onNodeDoubleClick = opts.onDoubleClick ?? null
  }

  /** Load a new layout into the scene */
  setLayout(layout: DagLayout): void {
    this.clear()
    this.state.layout = layout

    // Re-resolve colors (in case theme changed)
    this.colors = resolveAllColors()

    // Create edges and build source map for particles
    const edgePaths: Array<Array<{ x: number; y: number }>> = []
    this.edgeSourceMap.clear()
    for (let i = 0; i < layout.edges.length; i++) {
      const edge = layout.edges[i]!
      this.createEdge(edge.id, edge.source, edge.target, edge.points, edge.label, edge.isMapEdge)
      edgePaths.push(edge.points)
      // Map source node → edge indices
      const existing = this.edgeSourceMap.get(edge.source) ?? []
      existing.push(i)
      this.edgeSourceMap.set(edge.source, existing)
      this.edgeIdToIndex.set(edge.id, i)
    }

    // Create group containers
    for (const group of layout.groups ?? []) {
      this.createGroup(group)
    }

    // Set up particles
    this.particles.setEdges(edgePaths)

    // Create nodes
    for (const node of layout.nodes) {
      this.createNode(node.id, node.label, node.kind, node.x, node.y, node.width, node.height)
    }

    // Fit to 2D bounds initially; iso re-activation is handled by
    // the caller via setIsometric() to avoid duplicate activation.
    this.interaction.fitToView(layout.width, layout.height)

    // Apply initial statuses
    this.updateAllStatuses()
  }

  /** Update which node is selected */
  updateSelection(nodeId: string | null): void {
    const prev = this.state.selectedNode
    this.state.selectedNode = nodeId

    if (prev) this.refreshNode(prev)
    if (nodeId) this.refreshNode(nodeId)
  }

  /** Update which node is hovered */
  updateHover(nodeId: string | null): void {
    const prev = this.state.hoveredNode
    this.state.hoveredNode = nodeId

    // Update edge highlighting
    for (const [, edge] of this.state.edges) {
      const sel = nodeId ?? this.state.selectedNode
      const highlighted = sel ? (edge.source === sel || edge.target === sel) : false
      edge.main.alpha = highlighted ? 1 : 0.6
    }

    // Update node dimming
    const connected = new Set<string>()
    if (nodeId && this.state.layout) {
      connected.add(nodeId)
      for (const edge of this.state.layout.edges) {
        if (edge.source === nodeId) connected.add(edge.target)
        if (edge.target === nodeId) connected.add(edge.source)
      }
    }

    for (const [id, pixiNode] of this.state.nodes) {
      if (!nodeId) {
        pixiNode.container.alpha = 1
      } else {
        pixiNode.container.alpha = connected.has(id) ? 1 : 0.5
      }
    }

    if (prev) this.refreshNode(prev)
    if (nodeId) this.refreshNode(nodeId)
  }

  /** Update step statuses (from latest run) */
  updateStepStatuses(statuses: Record<string, string>): void {
    this.state.stepStatuses = statuses
    this.updateAllStatuses()
  }

  /** Toggle particle system */
  setParticlesEnabled(enabled: boolean): void {
    this.state.particlesEnabled = enabled
    this.particles.setEnabled(enabled)
  }

  /** Toggle 2.5D isometric view (instant swap, no animation) */
  setIsometric(enabled: boolean): void {
    this.state.isometric = enabled

    // Brief fade-out → swap → fade-in to hide the jarring repositioning
    this.world.alpha = 0

    if (enabled) {
      const bounds = this.isoScene.activate(
        this.world, this.edgeLayer, this.nodeLayer, this.particles.container,
        this.groupLayer, this.state, this.colors, false,
      )
      if (bounds) {
        this.interaction.fitToView(bounds.width, bounds.height, bounds.offsetX, bounds.offsetY)
      }
      if (this.state.layout) {
        const projectedPaths = this.isoScene.getProjectedEdgePaths(this.state.layout)
        this.particles.setEdges(projectedPaths)
        for (const [, edge] of this.state.edges) {
          const projected = this.isoScene.projectEdge(edge.points)
          this.edgeAnimator.updatePoints(edge.dash, projected)
        }
      }
    } else {
      this.isoScene.deactivate(this.world, this.state, this.colors, false)
      if (this.state.layout) {
        this.interaction.fitToView(this.state.layout.width, this.state.layout.height)
        const edgePaths = this.state.layout.edges.map((e) => e.points)
        this.particles.setEdges(edgePaths)
        for (const [, edge] of this.state.edges) {
          this.edgeAnimator.updatePoints(edge.dash, edge.points)
        }
      }
    }

    // Fade back in over ~150ms
    requestAnimationFrame(() => {
      this.world.alpha = 1
    })
  }

  /** Change the iso label display mode (surface / rotated / floating) */
  setIsoLabelMode(mode: string): void {
    this.isoScene.setLabelMode(mode as 'surface' | 'rotated' | 'floating', this.state, this.colors)
  }

  /** Emit particles from a node (used by replay) */
  emitParticlesFromNode(nodeId: string): void {
    this.particles.emitFromNode(nodeId, this.edgeSourceMap)
  }

  /** Apply blast radius visualization */
  setBlastRadius(nodeId: string | null): void {
    this.state.blastRadiusNode = nodeId

    if (!nodeId || !this.state.layout) {
      clearBlastRadius(this.state.nodes, this.state.edges)
      return
    }

    const result = computeBlastRadius(this.state.layout, nodeId)
    applyBlastRadius(result, this.state.nodes, this.state.edges, nodeId)
  }

  /** Get current interaction scale (for UI display) */
  getScale(): number {
    return this.interaction.scale
  }

  /** Set zoom scale programmatically */
  setScale(scale: number): void {
    this.interaction.setScale(scale)
  }

  /** Register a callback for scale changes (wheel zoom, fit-to-view, etc.) */
  onScaleChange(cb: (scale: number) => void): void {
    this.interaction.onScaleChange = cb
  }

  /** Reset view to fit layout (accounts for iso mode) */
  resetView(): void {
    if (!this.state.layout) return

    if (this.isoScene.isEnabled) {
      const bounds = this.isoScene.getIsoBounds(this.state.layout)
      if (bounds) {
        this.interaction.fitToView(bounds.width, bounds.height, bounds.offsetX, bounds.offsetY)
      }
    } else {
      this.interaction.fitToView(this.state.layout.width, this.state.layout.height)
    }
  }

  /** Get state for external use */
  getState(): DagSceneState {
    return this.state
  }

  /** Clean up all resources */
  destroy(): void {
    this.isoScene.destroy(this.world)
    this.edgeAnimator.clear()
    this.particles.destroy()
    this.interaction.destroy()
    this.clear()
  }

  // ── Private methods ─────────────────────────────────────────

  private clear(): void {
    this.edgeAnimator.clear()
    this.isoScene.clearNodes()
    this.nodeLayer.removeChildren()
    this.edgeLayer.removeChildren()
    this.groupLayer.removeChildren()
    this.state.nodes.clear()
    this.state.edges.clear()
    this.state.layout = null
    this.edgeIdToIndex.clear()
    this.replayEdgesActive = false
    this.activeReplayEdges.clear()
    this.replayParticleTimer = 0
    this.replayTimeMs = 0
    this.replayTimings = null
  }

  private createNode(
    id: string,
    label: string,
    kind: string,
    x: number,
    y: number,
    w: number,
    h: number,
  ): void {
    const colorKey = kindColorKey(kind)
    const color = this.colors[colorKey] ?? 0x888888
    const fgColor = this.colors.foreground ?? 0xffffff

    const container = new Container()
    container.position.set(x, y)
    container.eventMode = 'static'
    container.cursor = 'pointer'

    // Glow layer (hidden by default)
    const glow = new Graphics()
    glow.visible = false
    container.addChild(glow)

    // Background fill (card color)
    const bg = new Graphics()
    bg.roundRect(0, 0, w, h, 6)
    bg.fill({ color: this.colors.card ?? 0x1a1a2e })
    container.addChild(bg)

    // Shape outline
    const shape = new Graphics()
    drawNodeShape(shape, kind, w, h, color)
    container.addChild(shape)

    // Labels
    const labelText = createLabel(label, w, fgColor)
    labelText.position.set(w / 2, h / 2)
    container.addChild(labelText)

    const kindBadge = createKindBadge(kind, color, this.colors.card ?? 0x1a1a2e)
    kindBadge.position.set(w - kindBadge.width - 4, 4)
    container.addChild(kindBadge)

    // Hit area for better click detection
    const hitArea = new Graphics()
    hitArea.roundRect(0, 0, w, h, 6)
    hitArea.fill({ color: 0xffffff, alpha: 0.001 })
    container.addChild(hitArea)

    // Events
    container.on('pointerdown', (e) => {
      e.stopPropagation()
    })

    container.on('pointerup', () => {
      if (!this.interaction.wasDrag()) {
        this.onNodeSelect?.(this.state.selectedNode === id ? null : id)
      }
    })

    container.on('pointerenter', () => {
      this.onNodeHover?.(id)
    })

    container.on('pointerleave', () => {
      this.onNodeHover?.(null)
    })

    container.on('dblclick', () => {
      this.onNodeDoubleClick?.(id)
    })

    this.nodeLayer.addChild(container)

    const pixiNode: PixiNode = {
      id,
      kind,
      container,
      shape,
      glow,
      label: labelText,
      kindLabel: kindBadge,
      data: { id, label, kind, x, y, width: w, height: h },
    }
    this.state.nodes.set(id, pixiNode)
  }

  private createEdge(
    id: string,
    source: string,
    target: string,
    points: Array<{ x: number; y: number }>,
    label?: string,
    isMapEdge?: boolean,
  ): void {
    const color = this.colors.mutedForeground ?? 0x888888

    const main = new Graphics()
    if (isMapEdge) {
      // Draw dotted line for map edges
      drawEdgeDash(main, points, color, 0, 6, 4)
    } else {
      drawEdgeLine(main, points, color, 1.5, 0.6)
    }
    this.edgeLayer.addChild(main)

    const dash = new Graphics()
    this.edgeLayer.addChild(dash)

    const arrow = new Graphics()
    if (points.length > 0) {
      const last = points[points.length - 1]!
      drawArrow(arrow, last.x, last.y, color)
    }
    this.edgeLayer.addChild(arrow)

    // Edge label
    let edgeLabel: Text | undefined
    if (label && points.length >= 2) {
      const midIdx = Math.floor(points.length / 2)
      const midPt = points[midIdx]!
      const labelStyle = new TextStyle({
        fontFamily: '"JetBrains Mono", monospace',
        fontSize: 9,
        fontWeight: '500',
        fill: this.colors.mutedForeground ?? 0x666666,
      })
      edgeLabel = new Text({ text: label, style: labelStyle })
      edgeLabel.anchor.set(0.5, 1)
      edgeLabel.position.set(midPt.x, midPt.y - 4)
      this.edgeLayer.addChild(edgeLabel)
    }

    // Register for animation (skip for map edges — they already have dashes)
    if (!isMapEdge) {
      const mutedColor = this.colors.mutedForeground ?? 0x666666
      this.edgeAnimator.register(dash, points, mutedColor)
    }

    const pixiEdge: PixiEdge = { id, source, target, main, dash, arrow, points, label: edgeLabel }
    this.state.edges.set(id, pixiEdge)
  }

  private createGroup(group: RenderedGroup): void {
    const g = new Graphics()
    const borderColor = this.colors.border ?? 0x444444
    const cardColor = this.colors.card ?? 0x1a1a2e

    // Group background
    g.roundRect(group.x, group.y, group.width, group.height, 8)
    g.fill({ color: cardColor, alpha: 0.3 })
    g.stroke({ color: borderColor, width: 1, alpha: 0.4 })
    this.groupLayer.addChild(g)

    // Group header label
    const labelStyle = new TextStyle({
      fontFamily: '"JetBrains Mono", monospace',
      fontSize: 9,
      fontWeight: '500',
      fill: this.colors.mutedForeground ?? 0x666666,
    })
    const labelText = new Text({ text: group.label, style: labelStyle })
    labelText.position.set(group.x + 10, group.y + 6)
    this.groupLayer.addChild(labelText)
  }

  private refreshNode(id: string): void {
    const node = this.state.nodes.get(id)
    if (!node) return

    const isSelected = this.state.selectedNode === id
    const isHovered = this.state.hoveredNode === id
    const status = this.state.stepStatuses[id]
    const colorKey = kindColorKey(node.kind)
    const kindColor = this.colors[colorKey] ?? 0x888888

    // Update iso glow if in iso mode
    if (this.isoScene.isEnabled) {
      this.isoScene.refreshIsoNode(node, isSelected, isHovered, status, this.colors)
    }

    // Update 2D glow
    node.glow.clear()
    if (isSelected) {
      drawNodeGlow(node.glow, node.kind, node.data.width, node.data.height, kindColor, 0.15)
      node.glow.visible = !this.isoScene.isEnabled
    } else if (status === 'running') {
      const runningColor = this.colors.info ?? 0x3b82f6
      drawNodeGlow(node.glow, node.kind, node.data.width, node.data.height, runningColor, 0.4)
      node.glow.visible = !this.isoScene.isEnabled
    } else if (status === 'success') {
      const successColor = this.colors.success ?? 0x22c55e
      drawNodeGlow(node.glow, node.kind, node.data.width, node.data.height, successColor, 0.25)
      node.glow.visible = !this.isoScene.isEnabled
    } else if (status === 'failed' || status === 'error') {
      const errColor = this.colors.destructive ?? 0xef4444
      drawNodeGlow(node.glow, node.kind, node.data.width, node.data.height, errColor, 0.25)
      node.glow.visible = !this.isoScene.isEnabled
    } else {
      node.glow.visible = false
    }

    // Update shape stroke width
    node.shape.clear()
    drawNodeShape(node.shape, node.kind, node.data.width, node.data.height, kindColor)
  }

  private updateAllStatuses(): void {
    for (const [id] of this.state.nodes) {
      this.refreshNode(id)
    }
    if (!this.replayEdgesActive) {
      this.updateEdgeStatuses()
    }
  }

  private updateEdgeStatuses(): void {
    const statuses = this.state.stepStatuses
    const defaultColor = this.colors.mutedForeground ?? 0x888888
    const successColor = this.colors.success ?? 0x22c55e
    const runningColor = this.colors.info ?? 0x3b82f6
    const errorColor = this.colors.destructive ?? 0xef4444

    for (const [, edge] of this.state.edges) {
      const srcStatus = statuses[edge.source]
      const tgtStatus = statuses[edge.target]

      let color = defaultColor
      let alpha = 0.6

      if (srcStatus === 'success' || srcStatus === 'error') {
        if (tgtStatus === 'running') {
          // Data flowing: source done, target executing
          color = runningColor
          alpha = 0.9
        } else if (tgtStatus === 'success') {
          // Both done: path completed
          color = successColor
          alpha = 0.8
        } else if (tgtStatus === 'error') {
          color = errorColor
          alpha = 0.8
        }
      }

      // Redraw main line
      edge.main.clear()
      drawEdgeLine(edge.main, edge.points, color, 1.5, alpha)

      // Redraw arrow
      if (edge.points.length > 0) {
        const last = edge.points[edge.points.length - 1]!
        edge.arrow.clear()
        drawArrow(edge.arrow, last.x, last.y, color)
      }
    }
  }

  /** Store replay state — actual rendering happens in ticker via renderReplayEdges() */
  updateReplayEdges(
    timeMs: number,
    timings: Record<string, { startMs: number; endMs: number }>,
  ): void {
    this.replayTimeMs = timeMs
    this.replayTimings = timings
    if (!this.replayEdgesActive) {
      this.replayEdgesActive = true
      this.particles.setReplayMode(true)
    }
  }

  /** Render replay edges at 60fps from stored state (called by ticker) */
  private renderReplayEdges(): void {
    if (!this.replayEdgesActive || !this.replayTimings) return

    const timeMs = this.replayTimeMs
    const timings = this.replayTimings
    const isIso = this.isoScene.isEnabled

    const defaultColor = this.colors.mutedForeground ?? 0x888888
    const successColor = this.colors.success ?? 0x22c55e
    const runningColor = this.colors.info ?? 0x3b82f6
    const errorColor = this.colors.destructive ?? 0xef4444
    const statuses = this.state.stepStatuses

    // Minimum visual fill duration so edges don't snap instantly
    const MIN_FILL_MS = 200

    this.activeReplayEdges.clear()

    for (const [edgeId, edge] of this.state.edges) {
      const arrowIdx = edgeId.indexOf('->')
      if (arrowIdx === -1) continue
      const srcStep = edgeId.substring(0, arrowIdx)
      const tgtStep = edgeId.substring(arrowIdx + 2)

      // Use iso-projected points when in isometric mode
      const points = isIso ? this.isoScene.projectEdge(edge.points) : edge.points

      const srcTiming = timings[srcStep]
      const tgtTiming = timings[tgtStep]
      const srcStatus = statuses[srcStep]

      // Use precomputed timings directly (no status gate)
      let srcEndMs: number | null = null
      let srcStartMs = 0
      if (srcStep === '__start__') {
        srcEndMs = 0
      } else if (srcTiming) {
        srcStartMs = srcTiming.startMs
        srcEndMs = srcTiming.endMs
      }

      let tgtStartMs: number | null = null
      if (tgtStep === '__end__') {
        tgtStartMs = srcEndMs
      } else if (tgtTiming) {
        tgtStartMs = tgtTiming.startMs
      }

      edge.main.clear()
      edge.dash.visible = false
      edge.arrow.clear()

      if (srcEndMs === null || tgtStartMs === null) {
        drawEdgeLine(edge.main, points, defaultColor, 1.5, 0.6)
        if (points.length > 0) {
          const last = points[points.length - 1]!
          drawArrow(edge.arrow, last.x, last.y, defaultColor)
        }
        continue
      }

      // Hybrid fill: two strategies based on whether this edge "triggered" the target
      let fillStartMs: number
      let fillEndMs: number

      if (srcEndMs <= tgtStartMs) {
        // Triggering edge: source completed before/when target started.
        // Fill DURING source execution, arriving at 100% exactly when target starts.
        // This syncs edge completion with the target node's "running" glow.
        fillStartMs = Math.max(srcStartMs, tgtStartMs - MIN_FILL_MS)
        fillEndMs = tgtStartMs
      } else {
        // Non-triggering parallel edge: source finishes AFTER target already started
        // (e.g., fetch_cdn finishes at 522ms but normalize_assets started at 121ms).
        // Fill forward from source completion.
        fillStartMs = srcEndMs
        fillEndMs = srcEndMs + MIN_FILL_MS
      }

      const fillDuration = fillEndMs - fillStartMs
      let progress: number
      if (fillDuration <= 0 || timeMs >= fillEndMs) {
        // Zero-duration or past end → snap to 1 only if we've reached fillEndMs
        progress = timeMs >= fillEndMs ? 1 : 0
      } else if (timeMs <= fillStartMs) {
        progress = 0
      } else {
        progress = (timeMs - fillStartMs) / fillDuration
      }

      const tgtStatus = statuses[tgtStep]
      let filledColor = runningColor
      if (progress >= 1) {
        if (tgtStep === '__end__') {
          filledColor = srcStatus === 'error' ? errorColor : successColor
        } else if (tgtStatus === 'success') {
          filledColor = successColor
        } else if (tgtStatus === 'error') {
          filledColor = errorColor
        }
      }

      drawEdgeWithProgress(edge.main, points, filledColor, defaultColor, progress)

      if (points.length > 0) {
        const last = points[points.length - 1]!
        const arrowColor = progress >= 1 ? filledColor : defaultColor
        drawArrow(edge.arrow, last.x, last.y, arrowColor)
      }

      if (progress > 0 && progress < 1) {
        this.activeReplayEdges.add(edgeId)
      }
    }
  }

  /** Spawn particles on actively-filling edges (called from ticker) */
  private tickReplayParticles(deltaMs: number): void {
    if (this.activeReplayEdges.size === 0) return
    this.replayParticleTimer += deltaMs
    if (this.replayParticleTimer >= 200) {
      this.replayParticleTimer = 0
      for (const edgeId of this.activeReplayEdges) {
        const idx = this.edgeIdToIndex.get(edgeId)
        if (idx !== undefined) {
          this.particles.spawnOnEdge(idx)
        }
      }
    }
  }
}
