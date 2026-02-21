<script setup lang="ts">
import { computed } from 'vue'

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
</script>

<template>
  <div v-if="data.length > 0">
    <svg
      :viewBox="`0 0 100 ${svgHeight}`"
      preserveAspectRatio="none"
      class="w-full"
      :style="{ height: svgHeight + 'px' }"
    >
      <template v-if="bars">
        <rect
          v-for="bar in barRects"
          :key="bar.label"
          :x="bar.x"
          :y="bar.y"
          :width="bar.width"
          :height="bar.height"
          :fill="strokeColor"
          fill-opacity="0.6"
          rx="0.5"
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
    </svg>
  </div>
</template>
