import { Container, Graphics } from 'pixi.js'
import type { Ticker } from 'pixi.js'

interface Particle {
  graphic: Graphics
  edgeIndex: number
  progress: number // 0 → 1 along the edge
  active: boolean
}

interface EdgePath {
  points: Array<{ x: number; y: number }>
  totalLength: number
  segments: Array<{ start: { x: number; y: number }; end: { x: number; y: number }; startDist: number; len: number }>
}

const POOL_SIZE = 200
const PARTICLE_RADIUS = 2
const PARTICLE_SPEED = 0.4 // progress per second (0→1 in ~2.5s)
const SPAWN_INTERVAL = 300 // ms between spawns per edge

/**
 * Particle system: pool of small circles flowing along edge paths.
 * Owned by SceneManager, added as a child container.
 */
export class ParticleSystem {
  container: Container
  private pool: Particle[] = []
  private edges: EdgePath[] = []
  private spawnTimers: number[] = [] // ms since last spawn per edge
  private color: number
  private enabled = false
  private replayMode = false

  constructor(color: number) {
    this.container = new Container()
    this.color = color

    // Pre-allocate particle pool
    for (let i = 0; i < POOL_SIZE; i++) {
      const g = new Graphics()
      g.circle(0, 0, PARTICLE_RADIUS)
      g.fill({ color: this.color, alpha: 0.6 })
      g.visible = false
      this.container.addChild(g)
      this.pool.push({ graphic: g, edgeIndex: 0, progress: 0, active: false })
    }
  }

  /** Register edges for particles to flow along */
  setEdges(edgePaths: Array<Array<{ x: number; y: number }>>): void {
    this.edges = edgePaths.map((points) => {
      const segments: EdgePath['segments'] = []
      let totalLength = 0
      for (let i = 1; i < points.length; i++) {
        const dx = points[i]!.x - points[i - 1]!.x
        const dy = points[i]!.y - points[i - 1]!.y
        const len = Math.sqrt(dx * dx + dy * dy)
        segments.push({ start: points[i - 1]!, end: points[i]!, startDist: totalLength, len })
        totalLength += len
      }
      return { points, totalLength, segments }
    })
    this.spawnTimers = new Array(this.edges.length).fill(0)
    this.resetAll()
  }

  setEnabled(enabled: boolean): void {
    this.enabled = enabled
    if (!enabled && !this.replayMode) {
      this.resetAll()
    }
    this.container.visible = enabled || this.replayMode
  }

  /** Enable particle rendering without auto-spawning (for replay mode) */
  setReplayMode(enabled: boolean): void {
    this.replayMode = enabled
    if (enabled) {
      this.container.visible = true
    } else {
      this.container.visible = this.enabled
      if (!this.enabled) this.resetAll()
    }
  }

  /** Spawn a particle on a specific edge (for replay) */
  spawnOnEdge(edgeIndex: number): void {
    if (edgeIndex >= 0 && edgeIndex < this.edges.length) {
      this.spawnParticle(edgeIndex)
    }
  }

  /** Emit particles from a specific node's outgoing edges */
  emitFromNode(nodeId: string, edgeSourceMap: Map<string, number[]>): void {
    const edgeIndices = edgeSourceMap.get(nodeId)
    if (!edgeIndices) return
    for (const idx of edgeIndices) {
      this.spawnParticle(idx)
    }
  }

  update(ticker: Ticker): void {
    if ((!this.enabled && !this.replayMode) || this.edges.length === 0) return

    const dt = ticker.deltaMS

    // Auto-spawn only in normal (non-replay) mode
    if (this.enabled && !this.replayMode) {
      for (let i = 0; i < this.edges.length; i++) {
        this.spawnTimers[i] = (this.spawnTimers[i] ?? 0) + dt
        if (this.spawnTimers[i]! >= SPAWN_INTERVAL) {
          this.spawnTimers[i] = 0
          this.spawnParticle(i)
        }
      }
    }

    // Update active particles
    const progressDelta = (dt / 1000) * PARTICLE_SPEED
    for (const p of this.pool) {
      if (!p.active) continue
      p.progress += progressDelta
      if (p.progress >= 1) {
        p.active = false
        p.graphic.visible = false
        continue
      }

      const edge = this.edges[p.edgeIndex]
      if (!edge) {
        p.active = false
        p.graphic.visible = false
        continue
      }

      const pos = this.pointAtProgress(edge, p.progress)
      if (pos) {
        p.graphic.position.set(pos.x, pos.y)
      }
    }
  }

  destroy(): void {
    this.container.removeChildren()
    this.pool = []
    this.edges = []
  }

  private spawnParticle(edgeIndex: number): void {
    // Find an inactive particle
    const p = this.pool.find((p) => !p.active)
    if (!p) return

    p.active = true
    p.edgeIndex = edgeIndex
    p.progress = 0
    p.graphic.visible = true

    const edge = this.edges[edgeIndex]
    if (edge && edge.points.length > 0) {
      p.graphic.position.set(edge.points[0]!.x, edge.points[0]!.y)
    }
  }

  private resetAll(): void {
    for (const p of this.pool) {
      p.active = false
      p.graphic.visible = false
    }
  }

  private pointAtProgress(edge: EdgePath, progress: number): { x: number; y: number } | null {
    const dist = progress * edge.totalLength
    for (const seg of edge.segments) {
      const segEnd = seg.startDist + seg.len
      if (dist >= seg.startDist && dist <= segEnd) {
        const t = seg.len > 0 ? (dist - seg.startDist) / seg.len : 0
        return {
          x: seg.start.x + (seg.end.x - seg.start.x) * t,
          y: seg.start.y + (seg.end.y - seg.start.y) * t,
        }
      }
    }
    return null
  }
}
