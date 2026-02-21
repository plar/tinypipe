/**
 * Resolves CSS custom properties (including OKLCH) to hex colors
 * for use in PixiJS Graphics API.
 *
 * Modern browsers return OKLCH from getComputedStyle when CSS uses oklch().
 * Canvas 2D fillStyle also preserves oklch strings. We use pixel read-back:
 * 1. Probe element resolves CSS variables to computed color values
 * 2. Canvas fillRect + getImageData forces sRGB pixel conversion
 */

const cache = new Map<string, number>()
let probe: HTMLElement | null = null
let canvas: HTMLCanvasElement | null = null
let canvasCtx: CanvasRenderingContext2D | null = null

function getProbe(): HTMLElement {
  if (probe) return probe
  probe = document.createElement('div')
  probe.style.position = 'absolute'
  probe.style.width = '0'
  probe.style.height = '0'
  probe.style.overflow = 'hidden'
  probe.style.pointerEvents = 'none'
  document.body.appendChild(probe)
  return probe
}

function getCanvasCtx(): CanvasRenderingContext2D {
  if (canvasCtx) return canvasCtx
  canvas = document.createElement('canvas')
  canvas.width = 1
  canvas.height = 1
  canvasCtx = canvas.getContext('2d', { willReadFrequently: true })!
  return canvasCtx
}

/**
 * Convert any CSS color string to 0xRRGGBB via canvas pixel read-back.
 * This works for oklch, lab, lch, rgb, hsl, hex — any format the browser supports.
 */
function cssColorToHex(cssColor: string): number {
  const ctx = getCanvasCtx()
  ctx.clearRect(0, 0, 1, 1)
  ctx.fillStyle = cssColor
  ctx.fillRect(0, 0, 1, 1)
  const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data
  return (r! << 16) | (g! << 8) | b!
}

/** Resolve a CSS color value (variable reference or literal) to a 0xRRGGBB number */
export function resolveColor(cssValue: string): number {
  const cached = cache.get(cssValue)
  if (cached !== undefined) return cached

  // Step 1: resolve CSS variables via probe element
  const el = getProbe()
  el.style.color = cssValue
  const computed = getComputedStyle(el).color

  // Step 2: convert to hex via pixel read-back (handles oklch, lab, etc.)
  const hex = cssColorToHex(computed)
  cache.set(cssValue, hex)
  return hex
}

/** Resolve a CSS custom property name like '--color-success' */
export function resolveVar(varName: string): number {
  return resolveColor(`var(${varName})`)
}

/** Clear the color cache (call when theme changes) */
export function clearColorCache(): void {
  cache.clear()
}

/** Pre-resolve all common colors used in the DAG */
export function resolveAllColors(): Record<string, number> {
  return {
    card: resolveVar('--color-card'),
    border: resolveVar('--color-border'),
    foreground: resolveVar('--color-foreground'),
    mutedForeground: resolveVar('--color-muted-foreground'),
    primary: resolveVar('--color-primary'),
    success: resolveVar('--color-success'),
    destructive: resolveVar('--color-destructive'),
    warning: resolveVar('--color-warning'),
    info: resolveVar('--color-info'),
    nodeStep: resolveVar('--color-node-step'),
    nodeSwitch: resolveVar('--color-node-switch'),
    nodeMap: resolveVar('--color-node-map'),
    nodeSub: resolveVar('--color-node-sub'),
    nodeBarrier: resolveVar('--color-node-barrier'),
    nodeStreaming: resolveVar('--color-node-streaming'),
    nodePseudo: resolveVar('--color-node-pseudo'),
  }
}
