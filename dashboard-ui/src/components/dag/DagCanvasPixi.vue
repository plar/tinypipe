<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import type { PipelineTopology, VisualASTData } from '@/types'
import type { DagLayout } from '@/types/dag'
import { computeLayout, computeLayoutFromAST } from '@/lib/elk-layout'
import { useUiStore } from '@/stores/ui'
import { createPixiApp } from './pixi/create-app'
import { SceneManager } from './pixi/scene-manager'
import type { Application } from 'pixi.js'
import { Sparkles, Box, RotateCcw, ZoomIn, ZoomOut, Type } from 'lucide-vue-next'

const props = defineProps<{
  topology: PipelineTopology
  stepStatuses?: Record<string, string>
  /** Optional pre-computed layout (for replay mode) */
  layout?: DagLayout
  /** Override node statuses from replay */
  replayStatuses?: Record<string, string>
  /** Rich VisualAST from backend (enables enhanced layout) */
  visualAst?: VisualASTData | null
  /** Current replay time in ms (drives progressive edge fill) */
  replayTimeMs?: number
  /** Pre-computed step timings for replay edge progress */
  replayStepTimings?: Record<string, { startMs: number; endMs: number }>
}>()

const emit = defineEmits<{
  'navigate-sub': [hash: string]
}>()

const ui = useUiStore()

const canvasRef = ref<HTMLCanvasElement>()
const containerRef = ref<HTMLDivElement>()
const wrapperRef = ref<HTMLDivElement>()

let app: Application | null = null
let scene: SceneManager | null = null
let resizeObserver: ResizeObserver | null = null
const loading = ref(true)
const scale = ref(100)

/** Expose scene for replay integration */
defineExpose({
  getScene: () => scene,
})

async function init() {
  if (!canvasRef.value) return

  app = await createPixiApp(canvasRef.value)
  scene = new SceneManager(app, canvasRef.value)

  // Listen for scale changes from wheel zoom, fit-to-view, etc.
  scene.onScaleChange((s) => {
    scale.value = Math.round(s * 100)
  })

  scene.setCallbacks({
    onSelect: (id) => ui.selectNode(id),
    onHover: (id) => ui.hoverNode(id),
    onDoubleClick: (id) => {
      const node = props.topology.nodes[id]
      if (node?.kind === 'sub') {
        const subHash = (node as unknown as Record<string, unknown>).sub_pipeline_hash as string | undefined
        if (subHash) emit('navigate-sub', subHash)
      }
    },
  })

  // Watch for wrapper resize (user drags the CSS resize handle on the outer div)
  if (wrapperRef.value) {
    resizeObserver = new ResizeObserver(() => {
      if (app && containerRef.value) {
        app.renderer.resize(containerRef.value.clientWidth, containerRef.value.clientHeight)
        scene?.resetView()
      }
    })
    resizeObserver.observe(wrapperRef.value)
  }

  await computeAndSetLayout()
}

async function computeAndSetLayout() {
  if (!scene) return
  loading.value = true

  try {
    let layout: DagLayout
    if (props.layout) {
      layout = props.layout
    } else if (props.visualAst) {
      layout = await computeLayoutFromAST(props.visualAst)
    } else {
      layout = await computeLayout(props.topology)
    }
    scene.setLayout(layout)

    if (props.stepStatuses) {
      scene.updateStepStatuses(props.stepStatuses)
    }

    // Apply current UI state
    scene.setParticlesEnabled(ui.particlesEnabled)
    scene.setIsoLabelMode(ui.isoLabelMode)
    scene.setIsometric(ui.dagMode === '2.5d')

    scale.value = Math.round(scene.getScale() * 100)
  } finally {
    loading.value = false
  }
}

function resetView() {
  scene?.resetView()
  if (scene) scale.value = Math.round(scene.getScale() * 100)
}

function zoomIn() {
  if (!scene) return
  scene.setScale(scene.getScale() * 1.25)
}

function zoomOut() {
  if (!scene) return
  scene.setScale(scene.getScale() / 1.25)
}

function toggleParticles() {
  ui.toggleParticles()
  scene?.setParticlesEnabled(ui.particlesEnabled)
}

function toggleIsometric() {
  ui.toggleDagMode()
  scene?.setIsometric(ui.dagMode === '2.5d')
}

const labelModeLabels: Record<string, string> = {
  surface: 'Surface',
  rotated: 'Rotated',
  floating: 'Floating',
}

function cycleIsoLabelMode() {
  ui.cycleIsoLabelMode()
  scene?.setIsoLabelMode(ui.isoLabelMode)
}

// Watch for topology changes
watch(() => props.topology, async () => {
  await computeAndSetLayout()
})

// Watch for step status changes
watch(() => props.stepStatuses, (statuses) => {
  if (statuses && scene) scene.updateStepStatuses(statuses)
}, { deep: true })

// Watch for replay status changes
watch(() => props.replayStatuses, (statuses) => {
  if (statuses && scene) scene.updateStepStatuses(statuses)
}, { deep: true })

// Watch for replay time changes (drives progressive edge fill at ~60fps)
watch(() => props.replayTimeMs, (timeMs) => {
  if (timeMs !== undefined && props.replayStepTimings && scene) {
    scene.updateReplayEdges(timeMs, props.replayStepTimings)
  }
})

// Watch for selection changes from UI store
watch(() => ui.selectedNode, (nodeId) => {
  scene?.updateSelection(nodeId)
})

// Watch for hover changes from UI store
watch(() => ui.hoveredNode, (nodeId) => {
  scene?.updateHover(nodeId)
})

// Watch for blast radius changes
watch(() => ui.blastRadiusNode, (nodeId) => {
  scene?.setBlastRadius(nodeId)
})

onMounted(async () => {
  await nextTick()
  await init()
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  scene?.destroy()
  app?.destroy(true)
  scene = null
  app = null
})
</script>

<template>
  <div class="relative flex w-full flex-col">
    <!-- Controls -->
    <div class="mb-3 flex items-center justify-between">
      <slot name="legend" />
      <div class="flex items-center gap-2">
        <slot name="toolbar" />
        <!-- Particles toggle -->
        <button
          class="rounded-md border px-2 py-1 text-xs transition-colors"
          :class="ui.particlesEnabled
            ? 'border-info/50 bg-info/10 text-info'
            : 'border-border bg-card text-muted-foreground hover:text-foreground'"
          title="Toggle particles"
          @click="toggleParticles"
        >
          <Sparkles class="h-3.5 w-3.5" />
        </button>
        <!-- 2.5D toggle -->
        <button
          class="rounded-md border px-2 py-1 text-xs transition-colors"
          :class="ui.dagMode === '2.5d'
            ? 'border-info/50 bg-info/10 text-info'
            : 'border-border bg-card text-muted-foreground hover:text-foreground'"
          title="Toggle 2.5D isometric view"
          @click="toggleIsometric"
        >
          <Box class="h-3.5 w-3.5" />
        </button>
        <!-- Label mode cycle (only visible in iso mode) -->
        <button
          v-if="ui.dagMode === '2.5d'"
          class="rounded-md border px-2 py-1 text-xs transition-colors border-border bg-card text-muted-foreground hover:text-foreground"
          :title="`Label: ${labelModeLabels[ui.isoLabelMode]}`"
          @click="cycleIsoLabelMode"
        >
          <Type class="h-3.5 w-3.5" />
        </button>
        <!-- Zoom controls -->
        <button
          class="rounded-md border border-border bg-card px-1.5 py-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          title="Zoom out"
          @click="zoomOut"
        >
          <ZoomOut class="h-3.5 w-3.5" />
        </button>
        <span
          class="text-xs text-muted-foreground tabular-nums w-10 text-center cursor-default"
          title="Scroll to zoom"
        >
          {{ scale }}%
        </span>
        <button
          class="rounded-md border border-border bg-card px-1.5 py-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          title="Zoom in"
          @click="zoomIn"
        >
          <ZoomIn class="h-3.5 w-3.5" />
        </button>
        <!-- Reset View -->
        <button
          class="rounded-md border border-border bg-card px-2 py-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          title="Reset view"
          @click="resetView"
        >
          <RotateCcw class="h-3.5 w-3.5" />
        </button>
      </div>
    </div>

    <!-- Resizable wrapper — overflow:auto is needed for CSS resize to work in Firefox -->
    <div
      ref="wrapperRef"
      class="min-h-[300px] rounded-lg border border-border"
      style="height: 500px; resize: vertical; overflow: auto"
    >
      <!-- Canvas container — clips the WebGL canvas -->
      <div
        ref="containerRef"
        class="relative h-full w-full overflow-hidden bg-card scanline"
        style="cursor: grab"
      >
        <!-- Loading overlay -->
        <div
          v-if="loading"
          class="absolute inset-0 z-10 flex items-center justify-center"
        >
          <span class="text-sm text-muted-foreground">Computing layout...</span>
        </div>

        <!-- PixiJS canvas (always in DOM so init works) -->
        <canvas
          ref="canvasRef"
          :style="{ visibility: loading ? 'hidden' : 'visible', width: '100%', height: '100%' }"
        />
      </div>
    </div>
  </div>
</template>
