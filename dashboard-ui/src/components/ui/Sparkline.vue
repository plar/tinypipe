<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
  /** Data points: array of [label, value] pairs (rendered left to right) */
  data: Array<[string, number]>
  /** Height of the SVG in pixels */
  height?: number
  /** Color for the line/fill */
  color?: string
  /** Show bar chart instead of line */
  bars?: boolean
}>()

const svgHeight = computed(() => props.height ?? 40)
const strokeColor = computed(() => props.color ?? 'var(--color-info)')

const containerRef = ref<HTMLDivElement | null>(null)
const hoverIndex = ref<number | null>(null)
const hoverX = ref(0)
const hoverY = ref(0)

const maxVal = computed(() => {
  const max = Math.max(...props.data.map(([, v]) => v))
  return max > 0 ? max : 1
})

// Line/area chart points
const linePoints = computed(() => {
  if (props.data.length === 0) return ''
  const n = props.data.length
  const h = svgHeight.value
  const padding = 2
  const usable = h - padding * 2
  return props.data
    .map(([, v], i) => {
      const x = (i / Math.max(n - 1, 1)) * 100
      const y = padding + usable - (v / maxVal.value) * usable
      return `${x},${y}`
    })
    .join(' ')
})

const areaPath = computed(() => {
  if (props.data.length === 0) return ''
  const n = props.data.length
  const h = svgHeight.value
  const padding = 2
  const usable = h - padding * 2
  let d = `M0,${h} `
  for (let i = 0; i < n; i++) {
    const x = (i / Math.max(n - 1, 1)) * 100
    const y = padding + usable - (props.data[i]![1] / maxVal.value) * usable
    d += `L${x},${y} `
  }
  d += `L100,${h} Z`
  return d
})

// Bar chart rects
const barRects = computed(() => {
  if (props.data.length === 0) return []
  const n = props.data.length
  const h = svgHeight.value
  const barWidth = 100 / n
  const gap = barWidth * 0.15
  return props.data.map(([label, v], i) => ({
    label,
    x: i * barWidth + gap / 2,
    width: barWidth - gap,
    height: (v / maxVal.value) * (h - 4),
    y: h - (v / maxVal.value) * (h - 4),
    value: v,
  }))
})

// Hover indicator line position (SVG viewBox x-coordinate)
const hoverLineX = computed(() => {
  if (hoverIndex.value === null || props.data.length === 0) return 0
  const n = props.data.length
  if (props.bars) {
    const barWidth = 100 / n
    return hoverIndex.value * barWidth + barWidth / 2
  }
  return (hoverIndex.value / Math.max(n - 1, 1)) * 100
})

function onMouseMove(event: MouseEvent) {
  const el = containerRef.value
  if (!el || props.data.length === 0) return
  const rect = el.getBoundingClientRect()
  const relX = event.clientX - rect.left
  const ratio = relX / rect.width
  const n = props.data.length
  const idx = Math.max(0, Math.min(n - 1, Math.round(ratio * (n - 1))))
  hoverIndex.value = idx
  hoverX.value = event.clientX - rect.left
  hoverY.value = event.clientY - rect.top
}

function onMouseLeave() {
  hoverIndex.value = null
}

const hoveredItem = computed(() => {
  if (hoverIndex.value === null) return null
  const item = props.data[hoverIndex.value]
  if (!item) return null
  return { label: item[0], value: item[1] }
})
</script>

<template>
  <div
    v-if="data.length > 0"
    ref="containerRef"
    class="relative"
    @mousemove="onMouseMove"
    @mouseleave="onMouseLeave"
  >
    <svg
      :viewBox="`0 0 100 ${svgHeight}`"
      preserveAspectRatio="none"
      class="w-full"
      :style="{ height: svgHeight + 'px' }"
    >
      <template v-if="bars">
        <rect
          v-for="(bar, i) in barRects"
          :key="bar.label"
          :x="bar.x"
          :y="bar.y"
          :width="bar.width"
          :height="bar.height"
          :fill="strokeColor"
          :fill-opacity="hoverIndex === i ? 0.9 : 0.6"
          rx="0.5"
          class="transition-[fill-opacity] duration-100"
        />
      </template>
      <template v-else>
        <path :d="areaPath" :fill="strokeColor" fill-opacity="0.1" />
        <polyline
          :points="linePoints"
          fill="none"
          :stroke="strokeColor"
          stroke-width="0.5"
          vector-effect="non-scaling-stroke"
        />
      </template>
      <!-- Hover indicator line -->
      <line
        v-if="hoverIndex !== null"
        :x1="hoverLineX"
        :y1="0"
        :x2="hoverLineX"
        :y2="svgHeight"
        stroke="var(--color-foreground)"
        stroke-opacity="0.3"
        stroke-width="0.3"
        vector-effect="non-scaling-stroke"
      />
    </svg>
    <!-- Hover tooltip -->
    <div
      v-if="hoveredItem"
      class="pointer-events-none absolute z-10 rounded border border-border bg-card px-2 py-1 text-xs shadow-md"
      :style="{
        left: hoverX + 'px',
        top: '-4px',
        transform: 'translate(-50%, -100%)',
      }"
    >
      <span class="text-muted-foreground">{{ hoveredItem.label }}:</span>
      <span class="ml-1 font-medium tabular-nums text-foreground">{{ hoveredItem.value }}</span>
    </div>
  </div>
</template>
