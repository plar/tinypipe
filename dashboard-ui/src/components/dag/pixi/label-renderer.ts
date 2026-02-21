import { Container, Graphics, Text, TextStyle } from 'pixi.js'

const FONT_SANS = 'Outfit, system-ui, sans-serif'
const FONT_MONO = '"JetBrains Mono", monospace'

/** Create the main node label (node name) */
export function createLabel(
  text: string,
  maxWidth: number,
  color: number,
): Text {
  const style = new TextStyle({
    fontFamily: FONT_SANS,
    fontSize: 12,
    fontWeight: '500',
    fill: color,
    align: 'center',
  })

  const label = new Text({ text: truncateText(text, 18), style })
  label.anchor.set(0.5, 0.5)

  // Constrain to max width
  if (label.width > maxWidth - 16) {
    label.scale.set((maxWidth - 16) / label.width)
  }

  return label
}

/** Create the kind badge as a pill container (background + text) */
export function createKindBadge(
  kind: string,
  color: number,
  cardColor: number,
): Container {
  const badge = new Container()

  const style = new TextStyle({
    fontFamily: FONT_MONO,
    fontSize: 8,
    fontWeight: '500',
    fill: color,
    align: 'center',
  })

  const label = new Text({ text: kind, style })
  label.anchor.set(0, 0)

  // Pill background
  const padX = 5
  const padY = 2
  const bg = new Graphics()
  bg.roundRect(0, 0, label.width + padX * 2, label.height + padY * 2, 4)
  bg.fill({ color: cardColor, alpha: 0.9 })
  bg.stroke({ color, width: 1, alpha: 0.5 })

  label.position.set(padX, padY)

  badge.addChild(bg)
  badge.addChild(label)

  return badge
}

function truncateText(text: string, maxLen: number): string {
  return text.length > maxLen ? text.slice(0, maxLen - 1) + '\u2026' : text
}
