import type { Container } from 'pixi.js'

const DRAG_THRESHOLD = 4
const MIN_SCALE = 0.2
const MAX_SCALE = 3

/**
 * Manages pan/zoom interactions for the PixiJS DAG canvas.
 * Focal-point zoom: zooms toward the mouse cursor position.
 */
export class InteractionManager {
  private isPanning = false
  private didDrag = false
  private pointerOrigin = { x: 0, y: 0 }
  private panStart = { x: 0, y: 0 }

  scale = 1
  panX = 0
  panY = 0

  /** Fired after every zoom/pan change so the UI can read scale */
  onScaleChange: ((scale: number) => void) | null = null

  private world: Container
  private canvas: HTMLCanvasElement
  constructor(world: Container, canvas: HTMLCanvasElement) {
    this.world = world
    this.canvas = canvas

    canvas.addEventListener('pointerdown', this.handlePointerDown)
    canvas.addEventListener('pointermove', this.handlePointerMove)
    canvas.addEventListener('pointerup', this.handlePointerUp)
    canvas.addEventListener('pointerleave', this.handlePointerUp)
    canvas.addEventListener('wheel', this.handleWheel, { passive: false })
  }

  /** Apply current pan/zoom to the world container */
  applyTransform(): void {
    this.world.position.set(this.panX, this.panY)
    this.world.scale.set(this.scale)
  }

  /** Fit the layout to the canvas, with optional origin offset */
  fitToView(layoutWidth: number, layoutHeight: number, offsetX = 0, offsetY = 0): void {
    const cw = this.canvas.clientWidth
    const ch = this.canvas.clientHeight
    if (cw === 0 || ch === 0) return

    const padding = 40
    const scaleX = (cw - padding) / layoutWidth
    const scaleY = (ch - padding) / layoutHeight
    this.scale = Math.min(1, scaleX, scaleY)
    // Center the content in the canvas
    this.panX = (cw - layoutWidth * this.scale) / 2 - offsetX * this.scale
    this.panY = (ch - layoutHeight * this.scale) / 2 - offsetY * this.scale
    this.applyTransform()
    this.onScaleChange?.(this.scale)
  }

  /** Set zoom to a specific scale (0-1 range maps to MIN_SCALE-MAX_SCALE) */
  setScale(newScale: number): void {
    const clamped = Math.min(MAX_SCALE, Math.max(MIN_SCALE, newScale))

    // Zoom toward center of canvas
    const cw = this.canvas.clientWidth
    const ch = this.canvas.clientHeight
    const cx = cw / 2
    const cy = ch / 2

    const ratio = clamped / this.scale
    this.panX = cx - (cx - this.panX) * ratio
    this.panY = cy - (cy - this.panY) * ratio
    this.scale = clamped

    this.applyTransform()
    this.onScaleChange?.(this.scale)
  }

  /** Check if the last pointer interaction was a drag (not a click) */
  wasDrag(): boolean {
    return this.didDrag
  }

  destroy(): void {
    this.canvas.removeEventListener('pointerdown', this.handlePointerDown)
    this.canvas.removeEventListener('pointermove', this.handlePointerMove)
    this.canvas.removeEventListener('pointerup', this.handlePointerUp)
    this.canvas.removeEventListener('pointerleave', this.handlePointerUp)
    this.canvas.removeEventListener('wheel', this.handleWheel)
  }

  private handlePointerDown = (e: PointerEvent): void => {
    if (e.button !== 0) return
    this.isPanning = true
    this.didDrag = false
    this.pointerOrigin = { x: e.clientX, y: e.clientY }
    this.panStart = { x: e.clientX - this.panX, y: e.clientY - this.panY }
    this.canvas.style.cursor = 'grabbing'
  }

  private handlePointerMove = (e: PointerEvent): void => {
    if (!this.isPanning) return
    const dx = e.clientX - this.pointerOrigin.x
    const dy = e.clientY - this.pointerOrigin.y
    if (!this.didDrag && Math.abs(dx) + Math.abs(dy) > DRAG_THRESHOLD) {
      this.didDrag = true
    }
    if (this.didDrag) {
      this.panX = e.clientX - this.panStart.x
      this.panY = e.clientY - this.panStart.y
      this.applyTransform()
    }
  }

  private handlePointerUp = (): void => {
    this.isPanning = false
    this.canvas.style.cursor = 'grab'
  }

  private handleWheel = (e: WheelEvent): void => {
    e.preventDefault()
    const factor = e.deltaY > 0 ? 0.9 : 1.1
    const newScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, this.scale * factor))

    // Focal-point zoom: keep the point under the cursor fixed
    const rect = this.canvas.getBoundingClientRect()
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top

    const ratio = newScale / this.scale
    this.panX = mx - (mx - this.panX) * ratio
    this.panY = my - (my - this.panY) * ratio
    this.scale = newScale

    this.applyTransform()
    this.onScaleChange?.(this.scale)
  }
}
