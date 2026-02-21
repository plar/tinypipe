<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useReplayStore } from '@/stores/replay'
import { formatDuration } from '@/lib/utils'
import { Play, Pause, RotateCcw } from 'lucide-vue-next'

const replay = useReplayStore()

const speeds = [0.1, 0.25, 0.5, 1, 2, 5, 10]
const scrubberRef = ref<HTMLDivElement>()
let rafId: number | null = null
let lastTime = 0

function startLoop() {
  lastTime = performance.now()
  const loop = (now: number) => {
    const delta = now - lastTime
    lastTime = now
    replay.advance(delta)
    rafId = requestAnimationFrame(loop)
  }
  rafId = requestAnimationFrame(loop)
}

function stopLoop() {
  if (rafId !== null) {
    cancelAnimationFrame(rafId)
    rafId = null
  }
}

function restart() {
  replay.seek(0)
  replay.play()
}

function onScrubberClick(e: MouseEvent) {
  const el = scrubberRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  const p = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  replay.seekProgress(p)
}

watch(() => replay.playing, (isPlaying) => {
  if (isPlaying) {
    startLoop()
  } else {
    stopLoop()
  }
})

onMounted(() => {
  if (replay.playing) startLoop()
})

onBeforeUnmount(() => {
  stopLoop()
})
</script>

<template>
  <div class="mt-4 rounded-lg border border-border bg-card p-4">
    <div class="flex items-center gap-4">
      <!-- Play/Pause -->
      <button
        class="flex h-8 w-8 items-center justify-center rounded-md border border-border bg-muted/50 text-foreground transition-colors hover:bg-muted"
        @click="replay.togglePlay()"
      >
        <Pause v-if="replay.playing" class="h-4 w-4" />
        <Play v-else class="h-4 w-4" />
      </button>

      <!-- Restart -->
      <button
        class="flex h-8 w-8 items-center justify-center rounded-md border border-border bg-muted/50 text-muted-foreground transition-colors hover:text-foreground hover:bg-muted"
        title="Restart"
        @click="restart"
      >
        <RotateCcw class="h-3.5 w-3.5" />
      </button>

      <!-- Scrubber -->
      <div
        ref="scrubberRef"
        class="relative h-2 flex-1 cursor-pointer rounded-full bg-muted"
        @click="onScrubberClick"
      >
        <div
          class="absolute top-0 left-0 h-full rounded-full bg-primary transition-[width]"
          :style="{ width: (replay.progress * 100) + '%' }"
        />
        <div
          class="absolute top-1/2 h-4 w-4 -translate-y-1/2 rounded-full border-2 border-primary bg-card shadow-sm"
          :style="{ left: (replay.progress * 100) + '%', marginLeft: '-8px' }"
        />
      </div>

      <!-- Time -->
      <span class="w-24 text-right font-mono text-xs tabular-nums text-muted-foreground">
        {{ formatDuration(replay.currentTimeMs / 1000) }}
        /
        {{ formatDuration(replay.totalDurationMs / 1000) }}
      </span>

      <!-- Speed -->
      <div class="flex items-center gap-1">
        <button
          v-for="s in speeds"
          :key="s"
          class="rounded px-1.5 py-0.5 text-xs font-medium transition-colors"
          :class="replay.speed === s
            ? 'bg-primary/15 text-primary'
            : 'text-muted-foreground hover:text-foreground'"
          @click="replay.setSpeed(s)"
        >
          {{ s }}x
        </button>
      </div>
    </div>
  </div>
</template>
