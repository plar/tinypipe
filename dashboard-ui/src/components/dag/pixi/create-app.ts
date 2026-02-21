import { Application } from 'pixi.js'

/**
 * Create and initialize a PixiJS v8 Application.
 * Must be called after the canvas element is in the DOM.
 */
export async function createPixiApp(canvas: HTMLCanvasElement): Promise<Application> {
  // Wait for fonts before creating the app (labels need correct metrics)
  await document.fonts.ready

  const app = new Application()
  await app.init({
    canvas,
    antialias: true,
    backgroundAlpha: 0,
    autoDensity: true,
    resolution: window.devicePixelRatio || 1,
    resizeTo: canvas.parentElement ?? undefined,
  })

  return app
}
