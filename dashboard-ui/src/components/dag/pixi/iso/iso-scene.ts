/**
 * Isometric scene orchestrator.
 *
 * Manages iso layers, draws shapes, projects edges, depth-sorts nodes.
 * Delegates to iso-projection, iso-shapes, iso-ground, iso-edges, iso-labels,
 * and iso-transition for specific concerns.
 *
 * Integration strategy: additive, not destructive. 2D elements get hidden
 * (not removed) when iso mode activates; iso elements are added to existing
 * PixiNode containers.
 */

import { Container, Graphics, Text } from 'pixi.js'
import type { PixiNode, DagSceneState } from '../types'
import type { DagLayout } from '@/types/dag'
import { kindColorKey } from '../node-renderer'
import { drawEdgeLine, drawArrow } from '../edge-renderer'
import { isoProject, isoBounds, isoSortKey } from './iso-projection'
import { drawIsoShape, drawIsoGlow } from './iso-shapes'
import { drawGroundGrid, drawNodeShadow } from './iso-ground'
import { projectEdgePoints, projectAllEdgePaths } from './iso-edges'
import type { IsoLabelMode } from './iso-labels'
import { createIsoPill, updateIsoPill, getIsoLabelConfig } from './iso-labels'
import { IsoTransition } from './iso-transition'

/**
 * Layer structure for isometric mode, inserted into the world container.
 */
interface IsoLayers {
  ground: Graphics
  shadows: Graphics
  edges: Container // re-uses the existing edgeLayer
  particles: Container // re-uses existing
  nodes: Container // re-uses the existing nodeLayer
  labels: Container
}

/**
 * Per-node iso state stored on the PixiNode via a side-map.
 */
interface IsoNodeState {
  isoShape: Graphics
  isoGlow: Graphics
  isoPill: Graphics
}

export class IsometricScene {
  private layers: IsoLayers | null = null
  private isoNodes = new Map<string, IsoNodeState>()
  private transition = new IsoTransition()
  private enabled = false
  private labelMode: IsoLabelMode = 'surface' // fallback; overridden by store via setLabelMode()
  private groupLayer: Container | null = null
  private isoGroupContainer: Container | null = null

  /** Whether iso mode is currently active (or transitioning to active) */
  get isEnabled(): boolean {
    return this.enabled
  }

  /**
   * Activate isometric mode. Creates iso layers and shapes.
   */
  activate(
    world: Container,
    edgeLayer: Container,
    nodeLayer: Container,
    particleContainer: Container,
    groupLayer: Container,
    state: DagSceneState,
    colors: Record<string, number>,
    animate: boolean,
  ): { width: number; height: number; offsetX: number; offsetY: number } | null {
    this.enabled = true
    this.groupLayer = groupLayer

    if (!state.layout) return null

    // Create iso layers if not already present
    if (!this.layers) {
      const ground = new Graphics()
      ground.label = 'iso-ground'
      const shadows = new Graphics()
      shadows.label = 'iso-shadows'
      const labels = new Container()
      labels.label = 'iso-labels'

      // Insert ground and shadows at the beginning of world (behind everything)
      world.addChildAt(ground, 0)
      world.addChildAt(shadows, 1)
      // Labels go on top (after nodeLayer)
      world.addChild(labels)

      this.layers = {
        ground,
        shadows,
        edges: edgeLayer,
        particles: particleContainer,
        nodes: nodeLayer,
        labels,
      }
    }

    // Draw ground grid
    drawGroundGrid(this.layers.ground, state.layout.width, state.layout.height)

    // Create iso shapes for all nodes, draw shadows, position labels
    this.layers.shadows.clear()
    for (const [, node] of state.nodes) {
      this.createIsoNode(node, colors)
    }

    if (animate) {
      // Start animated transition
      this.transition.start(
        true,
        state.nodes,
        state.edges,
        () => this.finalizeActivation(state, colors),
      )
    } else {
      // Immediate activation
      this.finalizeActivation(state, colors)
    }

    // Return iso bounds for fitToView
    return isoBounds(state.layout.width, state.layout.height)
  }

  /**
   * Deactivate isometric mode. Restores 2D positions and hides iso elements.
   */
  deactivate(
    world: Container,
    state: DagSceneState,
    colors: Record<string, number>,
    animate: boolean,
  ): void {
    this.enabled = false

    if (animate && state.layout) {
      this.transition.start(
        false,
        state.nodes,
        state.edges,
        () => this.finalizeDeactivation(world, state, colors),
      )
    } else {
      this.finalizeDeactivation(world, state, colors)
    }
  }

  /**
   * Per-frame update. Drives transition animations.
   */
  update(
    state: DagSceneState,
    colors: Record<string, number>,
  ): void {
    if (!this.transition.isActive) return
    if (!this.layers) return

    this.transition.update(
      performance.now(),
      state.nodes,
      state.edges,
      this.layers.ground,
      this.layers.shadows,
      new Map(), // isoShapes not needed for transition crossfade (handled via labels)
      colors.mutedForeground ?? 0x888888,
    )
  }

  /**
   * Refresh a single node's iso glow (for selection/status changes).
   */
  refreshIsoNode(
    node: PixiNode,
    isSelected: boolean,
    isHovered: boolean,
    _status: string | undefined,
    colors: Record<string, number>,
  ): void {
    const isoState = this.isoNodes.get(node.id)
    if (!isoState) return

    const colorKey = kindColorKey(node.kind)
    const kindColor = colors[colorKey] ?? 0x888888

    isoState.isoGlow.clear()
    if (isSelected) {
      drawIsoGlow(isoState.isoGlow, node.kind, node.data.width, node.data.height, kindColor, 0.35)
      isoState.isoGlow.visible = true
    } else if (isHovered) {
      drawIsoGlow(isoState.isoGlow, node.kind, node.data.width, node.data.height, kindColor, 0.25)
      isoState.isoGlow.visible = true
    } else {
      isoState.isoGlow.visible = false
    }
  }

  /**
   * Project a single edge's points to iso screen coords.
   */
  projectEdge(points: Array<{ x: number; y: number }>): Array<{ x: number; y: number }> {
    return projectEdgePoints(points)
  }

  /**
   * Get iso bounds for fitToView. Callable any time iso is enabled.
   */
  getIsoBounds(layout: DagLayout): { width: number; height: number; offsetX: number; offsetY: number } {
    return isoBounds(layout.width, layout.height)
  }

  /**
   * Get projected edge paths for the particle system.
   */
  getProjectedEdgePaths(layout: DagLayout): Array<Array<{ x: number; y: number }>> {
    const paths = layout.edges.map((e) => e.points)
    return projectAllEdgePaths(paths)
  }

  /**
   * Depth-sort nodes in the nodeLayer (painter's algorithm).
   * Nodes further from camera (lower elkX+elkY) draw first.
   */
  depthSortNodes(state: DagSceneState): void {
    if (!this.layers) return

    const sorted = [...state.nodes.values()].sort(
      (a, b) => isoSortKey(a.data.x, a.data.y) - isoSortKey(b.data.x, b.data.y),
    )

    for (let i = 0; i < sorted.length; i++) {
      this.layers.nodes.setChildIndex(sorted[i]!.container, i)
    }
  }

  /**
   * Change the iso label display mode. Re-applies transforms if iso is active.
   */
  setLabelMode(mode: IsoLabelMode, state: DagSceneState, colors: Record<string, number>): void {
    this.labelMode = mode
    if (!this.enabled) return
    this.applyLabelTransforms(state, colors)
  }

  /**
   * Clean up all iso resources.
   */
  destroy(world: Container): void {
    this.transition.cancel()

    if (this.isoGroupContainer) {
      this.isoGroupContainer.parent?.removeChild(this.isoGroupContainer)
      this.isoGroupContainer.destroy()
      this.isoGroupContainer = null
    }

    if (this.layers) {
      world.removeChild(this.layers.ground)
      world.removeChild(this.layers.shadows)
      world.removeChild(this.layers.labels)
      this.layers.ground.destroy()
      this.layers.shadows.destroy()
      this.layers.labels.destroy()
      this.layers = null
    }

    // Remove iso children from node containers
    for (const [, isoState] of this.isoNodes) {
      isoState.isoShape.destroy()
      isoState.isoGlow.destroy()
      isoState.isoPill.destroy()
    }
    this.isoNodes.clear()
    this.enabled = false
  }

  /** Clear iso node state without destroying layers (used when layout is rebuilt). */
  clearNodes(): void {
    this.isoNodes.clear()
    this.transition.cancel()
  }

  // ── Private methods ─────────────────────────────────────────

  private createIsoNode(node: PixiNode, colors: Record<string, number>): void {
    // Skip if already has iso state
    if (this.isoNodes.has(node.id)) return

    const colorKey = kindColorKey(node.kind)
    const kindColor = colors[colorKey] ?? 0x888888
    const cardColor = colors.card ?? 0x1a1a2e
    const w = node.data.width
    const h = node.data.height

    // Iso shape
    const isoShape = new Graphics()
    isoShape.label = 'iso-shape'
    drawIsoShape(isoShape, node.kind, w, h, kindColor)
    isoShape.visible = false // hidden until transition completes or immediate activate
    node.container.addChildAt(isoShape, 0)

    // Iso glow (on top of iso shape, below labels)
    const isoGlow = new Graphics()
    isoGlow.label = 'iso-glow'
    isoGlow.visible = false
    // Insert after isoShape so it renders on top of it
    const shapeIdx = node.container.getChildIndex(isoShape)
    node.container.addChildAt(isoGlow, shapeIdx + 1)

    // Iso label pill (insert BEFORE label so label renders on top)
    const isoPill = createIsoPill(cardColor)
    const labelIdx = node.container.getChildIndex(node.label)
    node.container.addChildAt(isoPill, labelIdx)

    this.isoNodes.set(node.id, { isoShape, isoGlow, isoPill })
  }

  private finalizeActivation(state: DagSceneState, colors: Record<string, number>): void {
    const borderColor = colors.mutedForeground ?? 0x888888
    const cardColor = colors.card ?? 0x1a1a2e

    // Position all nodes at iso-projected positions
    for (const [id, node] of state.nodes) {
      const iso = isoProject(node.data.x, node.data.y)
      node.container.x = iso.x
      node.container.y = iso.y

      // Show iso shapes, hide 2D shapes
      const isoState = this.isoNodes.get(id)
      if (isoState) {
        isoState.isoShape.visible = true
        isoState.isoShape.alpha = 1
      }

      // Hide 2D children
      this.set2DChildrenVisible(node, false)

      // Apply label position + transform based on current label mode
      const cfg = getIsoLabelConfig(node.data.width, node.data.height, node.kind, this.labelMode)
      node.label.visible = true
      node.label.alpha = 1
      node.label.anchor.set(cfg.anchorX, cfg.anchorY)
      node.label.position.set(cfg.x, cfg.y)
      node.label.rotation = cfg.rotation
      node.label.skew.set(cfg.skewX, cfg.skewY)

      // Show and update pill (same transform as label)
      if (isoState) {
        isoState.isoPill.visible = true
        isoState.isoPill.position.set(cfg.x, cfg.y)
        isoState.isoPill.rotation = cfg.rotation
        isoState.isoPill.skew.set(cfg.skewX, cfg.skewY)
        updateIsoPill(isoState.isoPill, node.label, cardColor, node.data.width)
      }

      // Ensure label is the topmost child (above pill and iso shape)
      node.container.setChildIndex(node.label, node.container.children.length - 1)
    }

    // Hide 2D groups and draw iso-projected groups
    if (this.groupLayer) {
      this.groupLayer.visible = false
    }
    this.drawIsoGroups(state, colors)

    // Draw shadows
    if (this.layers) {
      this.layers.shadows.clear()
      for (const [, node] of state.nodes) {
        const colorKey = kindColorKey(node.kind)
        const kindColor = colors[colorKey] ?? 0x888888
        drawNodeShadow(
          this.layers.shadows,
          node.data.x, node.data.y,
          node.data.width, node.data.height,
          kindColor,
        )
      }
      this.layers.ground.alpha = 1
      this.layers.shadows.alpha = 1
    }

    // Project edges to iso positions
    for (const [, edge] of state.edges) {
      const projected = projectEdgePoints(edge.points)
      edge.main.clear()
      drawEdgeLine(edge.main, projected, borderColor, 1.5, 0.6)
      edge.arrow.clear()
      if (projected.length > 0) {
        const last = projected[projected.length - 1]!
        drawArrow(edge.arrow, last.x, last.y, borderColor)
      }
      // Reproject edge label
      if (edge.label && projected.length >= 2) {
        const midIdx = Math.floor(projected.length / 2)
        const midPt = projected[midIdx]!
        edge.label.position.set(midPt.x, midPt.y - 4)
      }
    }

    // Depth sort
    this.depthSortNodes(state)
  }

  private finalizeDeactivation(world: Container, state: DagSceneState, colors: Record<string, number>): void {
    // Restore 2D positions
    for (const [id, node] of state.nodes) {
      node.container.x = node.data.x
      node.container.y = node.data.y

      // Hide iso shapes, show 2D shapes
      const isoState = this.isoNodes.get(id)
      if (isoState) {
        isoState.isoShape.visible = false
        isoState.isoGlow.visible = false
        isoState.isoPill.visible = false
      }

      // Show 2D children
      this.set2DChildrenVisible(node, true)

      // Restore label position, anchor, transform, and alpha
      node.label.alpha = 1
      node.label.anchor.set(0.5, 0.5) // Center-aligned in 2D mode
      node.label.position.set(node.data.width / 2, node.data.height / 2)
      node.label.rotation = 0
      node.label.skew.set(0, 0)
    }

    // Restore edges to 2D positions
    const borderColor = colors.mutedForeground ?? 0x888888
    for (const [, edge] of state.edges) {
      edge.main.clear()
      drawEdgeLine(edge.main, edge.points, borderColor, 1.5, 0.6)
      edge.arrow.clear()
      if (edge.points.length > 0) {
        const last = edge.points[edge.points.length - 1]!
        drawArrow(edge.arrow, last.x, last.y, borderColor)
      }
      // Restore edge label to original 2D midpoint
      if (edge.label && edge.points.length >= 2) {
        const midIdx = Math.floor(edge.points.length / 2)
        const midPt = edge.points[midIdx]!
        edge.label.position.set(midPt.x, midPt.y - 4)
      }
    }

    // Restore 2D groups
    if (this.groupLayer) {
      this.groupLayer.visible = true
    }
    // Remove iso group graphics
    if (this.isoGroupContainer) {
      this.isoGroupContainer.parent?.removeChild(this.isoGroupContainer)
      this.isoGroupContainer.destroy()
      this.isoGroupContainer = null
    }

    // Hide ground and shadows
    if (this.layers) {
      this.layers.ground.alpha = 0
      this.layers.shadows.alpha = 0
    }

    // Remove iso children from node containers and clean up
    for (const [, isoState] of this.isoNodes) {
      isoState.isoShape.parent?.removeChild(isoState.isoShape)
      isoState.isoGlow.parent?.removeChild(isoState.isoGlow)
      isoState.isoPill.parent?.removeChild(isoState.isoPill)
      isoState.isoShape.destroy()
      isoState.isoGlow.destroy()
      isoState.isoPill.destroy()
    }
    this.isoNodes.clear()

    // Remove layers from world
    if (this.layers) {
      world.removeChild(this.layers.ground)
      world.removeChild(this.layers.shadows)
      world.removeChild(this.layers.labels)
      this.layers.ground.destroy()
      this.layers.shadows.destroy()
      this.layers.labels.destroy()
      this.layers = null
    }
  }

  /**
   * Draw iso-projected group containers (parallelograms on the ground plane).
   */
  private drawIsoGroups(state: DagSceneState, _colors: Record<string, number>): void {
    // Clean up previous iso groups
    if (this.isoGroupContainer) {
      this.isoGroupContainer.parent?.removeChild(this.isoGroupContainer)
      this.isoGroupContainer.destroy()
      this.isoGroupContainer = null
    }

    const groups = state.layout?.groups
    if (!groups || groups.length === 0) return
    if (!this.layers) return

    const container = new Container()
    container.label = 'iso-groups'
    const groupFill = 0x3a7abf // bright blue fill distinct from dark background
    const groupBorder = 0x5a9adf // prominent blue border
    const ISO_ANGLE = Math.PI / 6 // 30° — matches node label rotation

    for (const group of groups) {
      // Project the four corners of the group rectangle
      const tl = isoProject(group.x, group.y)
      const tr = isoProject(group.x + group.width + 20, group.y)
      const br = isoProject(group.x + group.width + 20, group.y + group.height + 20)
      const bl = isoProject(group.x, group.y + group.height + 20)

      // Draw iso-projected parallelogram with clearly visible background
      const g = new Graphics()
      const pts = [tl.x, tl.y, tr.x, tr.y, br.x, br.y, bl.x, bl.y]
      g.poly(pts, true)
      g.fill({ color: groupFill, alpha: 0.3 })
      g.stroke({ color: groupBorder, width: 2, alpha: 0.7 })
      container.addChild(g)

      // Group label at top of parallelogram, rotated to match iso node labels
      const labelText = new Text({
        text: group.label,
        style: {
          fontFamily: '"JetBrains Mono", monospace',
          fontSize: 11,
          fontWeight: '600',
          fill: 0x6abaef,
        },
      })
      // In iso screen space: tl=top, tr=LEFT, bl=RIGHT, br=bottom
      const lx = tl.x + (tr.x - tl.x) * 0.98 + (bl.x - tl.x) * 0.08
      const ly = tl.y + (tr.y - tl.y) * 0.97 + (bl.y - tl.y) * 0.08
      labelText.rotation = -ISO_ANGLE
      labelText.anchor.set(0, 0)
      labelText.position.set(lx, ly)

      const cfg = getIsoLabelConfig(labelText.width, labelText.height, "step", this.labelMode)
      labelText.skew.set(cfg.skewX, cfg.skewY)


      container.addChild(labelText)
    }

    // Add to world, just above the shadows layer
    if (this.layers.ground.parent) {
      const shadowIdx = this.layers.ground.parent.getChildIndex(this.layers.shadows)
      this.layers.ground.parent.addChildAt(container, shadowIdx + 1)
    }
    this.isoGroupContainer = container
  }

  /**
   * Re-apply label position + transform for all nodes (used when label mode changes).
   */
  private applyLabelTransforms(state: DagSceneState, colors: Record<string, number>): void {
    const cardColor = colors.card ?? 0x1a1a2e

    for (const [id, node] of state.nodes) {
      const cfg = getIsoLabelConfig(node.data.width, node.data.height, node.kind, this.labelMode)
      node.label.anchor.set(cfg.anchorX, cfg.anchorY)
      node.label.position.set(cfg.x, cfg.y)
      node.label.rotation = cfg.rotation
      node.label.skew.set(cfg.skewX, cfg.skewY)

      const isoState = this.isoNodes.get(id)
      if (isoState) {
        isoState.isoPill.position.set(cfg.x, cfg.y)
        isoState.isoPill.rotation = cfg.rotation
        isoState.isoPill.skew.set(cfg.skewX, cfg.skewY)
        updateIsoPill(isoState.isoPill, node.label, cardColor, node.data.width)
      }
    }
  }

  /**
   * Toggle visibility of 2D children on a node (bg, shape, kindLabel).
   * Preserves glow, hitArea, label, and iso elements.
   */
  private set2DChildrenVisible(node: PixiNode, visible: boolean): void {
    for (const child of node.container.children) {
      const label = child.label ?? ''
      // Skip iso elements and special elements
      if (
        label === 'iso-shape' ||
        label === 'iso-glow' ||
        label === 'iso-pill' ||
        label === 'iso-shadow'
      ) continue

      // Skip glow (managed separately) and label (always visible)
      if (child === node.glow) {
        child.visible = visible ? node.glow.visible : false
        continue
      }
      if (child === node.label) continue

      // Everything else (bg, shape, kindLabel, hitArea) follows visibility
      // But keep hitArea always functional
      if (child.eventMode === 'static') continue

      child.visible = visible
    }
  }
}
