<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useRunStore } from '@/stores/run'
import { useReplayStore } from '@/stores/replay'
import { formatDuration, formatTimestamp, shortId } from '@/lib/utils'
import { statusBadgeVariant } from '@/lib/view-helpers'
import { useKeyboard } from '@/composables/useKeyboard'
import type { StepTiming, BarrierMetrics, PipelineSummary } from '@/types'
import { api } from '@/api/client'
import TabBar from '@/components/ui/TabBar.vue'
import MetricTile from '@/components/ui/MetricTile.vue'
import StatusIndicator from '@/components/ui/StatusIndicator.vue'
import Badge from '@/components/ui/Badge.vue'
import LoadingState from '@/components/ui/LoadingState.vue'
import ErrorBanner from '@/components/ui/ErrorBanner.vue'
import WaterfallTimeline from '@/components/timeline/WaterfallTimeline.vue'
import ConcurrencyChart from '@/components/timeline/ConcurrencyChart.vue'
import FailureAutopsy from '@/components/inspector/FailureAutopsy.vue'
import StepInspector from '@/components/inspector/StepInspector.vue'
import DagErrorBoundary from '@/components/dag/DagErrorBoundary.vue'
import DagCanvasPixi from '@/components/dag/DagCanvasPixi.vue'
import DagLegend from '@/components/dag/DagLegend.vue'
import ReplayControls from '@/components/replay/ReplayControls.vue'
import ArtifactBrowser from '@/components/artifacts/ArtifactBrowser.vue'
import { ArrowLeft, ChevronRight, GitCompareArrows } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const runStore = useRunStore()
const replay = useReplayStore()

const runId = computed(() => route.params.id as string)
const activeTab = ref('timeline')
const eventTypeFilter = ref('')
const expandedEvents = ref<Set<number>>(new Set())
const selectedStep = ref<string | null>(null)

// Replay state
const replayPipeline = ref<PipelineSummary | null>(null)
const replayLoading = ref(false)

const tabs = [
  { key: 'timeline', label: 'Timeline' },
  { key: 'events', label: 'Events' },
  { key: 'metrics', label: 'Metrics' },
  { key: 'replay', label: 'Replay' },
  { key: 'artifacts', label: 'Artifacts' },
  { key: 'meta', label: 'Meta' },
]

// Keyboard shortcuts
useKeyboard({
  tabKeys: tabs.map((t) => t.key),
  onTab: (key) => { activeTab.value = key },
  onEscape: () => { selectedStep.value = null },
})

// Metrics helpers
const metrics = computed(() => runStore.runtimeMetrics)

const stepLatencyRows = computed(() => {
  if (!metrics.value?.step_latency) return []
  return Object.entries(metrics.value.step_latency)
    .map(([name, t]: [string, StepTiming]) => ({
      name,
      count: t.count,
      avg: t.count > 0 ? t.total_s / t.count : 0,
      min: t.min_s,
      max: t.max_s,
    }))
    .sort((a, b) => b.avg - a.avg)
})

const barrierRows = computed(() => {
  if (!metrics.value?.barriers) return []
  return Object.entries(metrics.value.barriers)
    .map(([name, b]: [string, BarrierMetrics]) => ({ name, ...b }))
})

const eventTypeRows = computed(() => {
  if (!metrics.value?.events) return []
  return Object.entries(metrics.value.events)
    .sort(([, a], [, b]) => b - a)
})

const filteredEvents = computed(() => {
  if (!eventTypeFilter.value) return runStore.events
  return runStore.events.filter((e) => e.event_type === eventTypeFilter.value)
})

const eventTypes = computed(() => {
  const types = new Set(runStore.events.map((e) => e.event_type))
  return Array.from(types).sort()
})

// Inspector data
const inspectorOpen = computed(() => selectedStep.value !== null)
const inspectorStep = computed(() => {
  if (!selectedStep.value) return null
  return runStore.steps.find((s) => s.name === selectedStep.value) ?? null
})
const inspectorEvents = computed(() => {
  if (!selectedStep.value) return []
  return runStore.eventsForStep(selectedStep.value)
})

function selectStep(stepName: string) {
  selectedStep.value = selectedStep.value === stepName ? null : stepName
}

function closeInspector() {
  selectedStep.value = null
}

function toggleEvent(seq: number) {
  if (expandedEvents.value.has(seq)) {
    expandedEvents.value.delete(seq)
  } else {
    expandedEvents.value.add(seq)
  }
}

function goToCompare() {
  router.push({ path: '/compare', query: { run1: runId.value } })
}

// Load replay data when switching to replay tab
async function loadReplayData() {
  if (!runStore.run || replayPipeline.value) return
  replayLoading.value = true
  try {
    replayPipeline.value = await api.getPipeline(runStore.run.pipeline_hash)
    replay.setEvents(runStore.events)
  } finally {
    replayLoading.value = false
  }
}

watch(activeTab, (tab) => {
  if (tab === 'replay') loadReplayData()
})

onMounted(() => {
  runStore.fetchRun(runId.value)
})

watch(runId, (newId) => {
  runStore.fetchRun(newId)
  replayPipeline.value = null
  replay.reset()
})

onBeforeUnmount(() => {
  replay.reset()
})
</script>

<template>
  <div>
    <LoadingState v-if="runStore.loading" />
    <ErrorBanner v-else-if="runStore.error" :message="runStore.error" />
    <template v-else-if="runStore.run">
      <!-- Header -->
      <div class="mb-6">
        <div class="flex items-center justify-between">
          <RouterLink
            :to="`/pipeline/${runStore.run.pipeline_hash}`"
            class="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft class="h-3.5 w-3.5" />
            {{ runStore.run.pipeline_name }}
          </RouterLink>
          <button
            class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-accent/30 hover:text-foreground"
            @click="goToCompare"
          >
            <GitCompareArrows class="h-3.5 w-3.5" />
            Compare with...
          </button>
        </div>

        <div class="mt-2 flex items-center gap-3">
          <StatusIndicator :status="runStore.run.status" size="lg" :pulse="runStore.run.status === 'success'" />
          <h1 class="font-mono text-xl font-semibold text-foreground">
            {{ shortId(runStore.run.run_id, 16) }}
          </h1>
          <Badge :variant="statusBadgeVariant(runStore.run.status)">{{ runStore.run.status }}</Badge>
        </div>

        <div class="mt-2 flex gap-6 text-sm text-muted-foreground">
          <span>Started: {{ formatTimestamp(runStore.run.start_time) }}</span>
          <span v-if="runStore.run.end_time">Ended: {{ formatTimestamp(runStore.run.end_time) }}</span>
          <span>Duration: <strong class="text-foreground">{{ formatDuration(runStore.run.duration_seconds) }}</strong></span>
        </div>
      </div>

      <!-- Failure Autopsy -->
      <FailureAutopsy
        v-if="runStore.run.status === 'failed'"
        :run="runStore.run"
        :steps="runStore.steps"
        :events="runStore.events"
      />

      <!-- Tabs -->
      <div class="mb-6">
        <TabBar :tabs="tabs" :active="activeTab" @select="activeTab = $event" />
      </div>

      <!-- Timeline Tab -->
      <div v-if="activeTab === 'timeline'">
        <WaterfallTimeline
          :entries="runStore.timeline"
          :critical-path="runStore.criticalPath"
          :selected-step="selectedStep"
          @select-step="selectStep"
        />
        <ConcurrencyChart
          :entries="runStore.timeline"
          :min-ms="runStore.timelineRange.min"
          :span-ms="runStore.timelineRange.span"
        />
      </div>

      <!-- Events Tab -->
      <div v-if="activeTab === 'events'">
        <div class="mb-4 flex items-center gap-3">
          <select
            v-model="eventTypeFilter"
            class="rounded-md border border-border bg-input px-3 py-1.5 text-sm text-foreground"
          >
            <option value="">All types</option>
            <option v-for="t in eventTypes" :key="t" :value="t">{{ t }}</option>
          </select>
          <span class="text-xs text-muted-foreground">{{ filteredEvents.length }} event(s)</span>
        </div>

        <div class="divide-y divide-border overflow-hidden rounded-lg border border-border">
          <div v-for="event in filteredEvents" :key="event.seq" class="text-sm">
            <button
              class="flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-accent/30"
              @click="toggleEvent(event.seq)"
            >
              <span class="w-8 text-right font-mono text-xs text-muted-foreground">{{ event.seq }}</span>
              <Badge variant="muted">{{ event.event_type }}</Badge>
              <span class="flex-1 truncate font-mono text-xs text-muted-foreground">
                {{ event.step_name }}
              </span>
              <span class="text-xs text-muted-foreground">{{ formatTimestamp(event.timestamp) }}</span>
              <ChevronRight
                class="h-4 w-4 text-muted-foreground transition-transform"
                :class="{ 'rotate-90': expandedEvents.has(event.seq) }"
              />
            </button>
            <div
              v-if="expandedEvents.has(event.seq)"
              class="border-t border-border bg-muted/30 px-4 py-3"
            >
              <pre class="overflow-x-auto font-mono text-xs text-muted-foreground">{{ JSON.stringify(event.data, null, 2) }}</pre>
            </div>
          </div>
          <div v-if="filteredEvents.length === 0" class="px-4 py-8 text-center text-sm text-muted-foreground">
            No events found
          </div>
        </div>
      </div>

      <!-- Metrics Tab -->
      <div v-if="activeTab === 'metrics'">
        <div v-if="!metrics" class="rounded-lg border border-border bg-card p-8 text-center text-sm text-muted-foreground">
          No runtime metrics available for this run
        </div>
        <template v-else>
          <!-- Summary tiles -->
          <div class="mb-6 grid gap-4 sm:grid-cols-5 stagger-reveal">
            <MetricTile label="Tasks Started" :value="metrics.tasks.started" />
            <MetricTile label="Peak Active" :value="metrics.tasks.peak_active" />
            <MetricTile label="Tokens" :value="metrics.tokens" />
            <MetricTile label="Peak Queue" :value="metrics.queue.max_depth" />
            <MetricTile label="Suspends" :value="metrics.suspends" />
          </div>

          <!-- Step Latency table -->
          <div v-if="stepLatencyRows.length" class="mb-6 overflow-hidden rounded-lg border border-border">
            <h4 class="border-l-2 border-primary/40 pl-3 border-b border-border bg-card px-4 py-3 text-sm font-medium text-foreground">Step Latency</h4>
            <table class="w-full text-sm">
              <thead class="bg-muted/50 text-left text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th class="px-4 py-2 font-medium">Step</th>
                  <th class="px-4 py-2 text-right font-medium">Count</th>
                  <th class="px-4 py-2 text-right font-medium">Avg</th>
                  <th class="px-4 py-2 text-right font-medium">Min</th>
                  <th class="px-4 py-2 text-right font-medium">Max</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-border">
                <tr v-for="row in stepLatencyRows" :key="row.name" class="hover:bg-accent/20">
                  <td class="px-4 py-2 font-mono text-xs">{{ row.name }}</td>
                  <td class="px-4 py-2 text-right tabular-nums">{{ row.count }}</td>
                  <td class="px-4 py-2 text-right font-mono text-xs tabular-nums">{{ formatDuration(row.avg) }}</td>
                  <td class="px-4 py-2 text-right font-mono text-xs tabular-nums text-muted-foreground">{{ formatDuration(row.min) }}</td>
                  <td class="px-4 py-2 text-right font-mono text-xs tabular-nums text-muted-foreground">{{ formatDuration(row.max) }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Barrier Stats -->
          <div v-if="barrierRows.length" class="mb-6 overflow-hidden rounded-lg border border-border">
            <h4 class="border-l-2 border-primary/40 pl-3 border-b border-border bg-card px-4 py-3 text-sm font-medium text-foreground">Barrier Statistics</h4>
            <table class="w-full text-sm">
              <thead class="bg-muted/50 text-left text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th class="px-4 py-2 font-medium">Barrier</th>
                  <th class="px-4 py-2 text-right font-medium">Waits</th>
                  <th class="px-4 py-2 text-right font-medium">Releases</th>
                  <th class="px-4 py-2 text-right font-medium">Timeouts</th>
                  <th class="px-4 py-2 text-right font-medium">Max Wait</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-border">
                <tr v-for="row in barrierRows" :key="row.name" class="hover:bg-accent/20">
                  <td class="px-4 py-2 font-mono text-xs">{{ row.name }}</td>
                  <td class="px-4 py-2 text-right tabular-nums">{{ row.waits }}</td>
                  <td class="px-4 py-2 text-right tabular-nums">{{ row.releases }}</td>
                  <td class="px-4 py-2 text-right tabular-nums" :class="row.timeouts > 0 ? 'text-warning' : ''">{{ row.timeouts }}</td>
                  <td class="px-4 py-2 text-right font-mono text-xs tabular-nums">{{ formatDuration(row.max_wait_s) }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Map Stats -->
          <div v-if="metrics.maps.maps_started > 0" class="mb-6 rounded-lg border border-border bg-card p-4">
            <h4 class="border-l-2 border-primary/40 pl-3 mb-3 text-sm font-medium text-foreground">Map Statistics</h4>
            <div class="grid gap-4 sm:grid-cols-4">
              <div>
                <p class="text-xs uppercase tracking-wider text-muted-foreground">Maps Started</p>
                <p class="text-lg font-semibold tabular-nums">{{ metrics.maps.maps_started }}</p>
              </div>
              <div>
                <p class="text-xs uppercase tracking-wider text-muted-foreground">Maps Completed</p>
                <p class="text-lg font-semibold tabular-nums">{{ metrics.maps.maps_completed }}</p>
              </div>
              <div>
                <p class="text-xs uppercase tracking-wider text-muted-foreground">Workers Started</p>
                <p class="text-lg font-semibold tabular-nums">{{ metrics.maps.workers_started }}</p>
              </div>
              <div>
                <p class="text-xs uppercase tracking-wider text-muted-foreground">Peak Workers</p>
                <p class="text-lg font-semibold tabular-nums">{{ metrics.maps.peak_workers }}</p>
              </div>
            </div>
          </div>

          <!-- Event Type Breakdown -->
          <div v-if="eventTypeRows.length" class="rounded-lg border border-border bg-card p-4">
            <h4 class="border-l-2 border-primary/40 pl-3 mb-3 text-sm font-medium text-foreground">Event Type Breakdown</h4>
            <div class="space-y-2">
              <div v-for="[type, count] in eventTypeRows" :key="type" class="flex items-center gap-3">
                <span class="w-32 truncate font-mono text-xs text-muted-foreground">{{ type }}</span>
                <div class="flex-1">
                  <div class="h-4 overflow-hidden rounded bg-muted">
                    <div
                      class="h-full rounded bg-info transition-all"
                      :style="{ width: eventTypeRows.length ? (count / eventTypeRows[0]![1] * 100) + '%' : '0%' }"
                    />
                  </div>
                </div>
                <span class="w-10 text-right text-xs font-medium tabular-nums">{{ count }}</span>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- Replay Tab -->
      <div v-if="activeTab === 'replay'">
        <LoadingState v-if="replayLoading" text="Loading pipeline topology..." />
        <div v-else-if="replayPipeline?.topology">
          <DagErrorBoundary>
            <DagCanvasPixi
              :topology="replayPipeline.topology"
              :visual-ast="replayPipeline.visual_ast"
              :replay-statuses="replay.activeSteps"
              :replay-time-ms="replay.currentTimeMs"
              :replay-step-timings="replay.stepTimings"
            >
              <template #legend>
                <DagLegend />
              </template>
            </DagCanvasPixi>
          </DagErrorBoundary>
          <ReplayControls />
        </div>
        <div v-else class="rounded-lg border border-border bg-card p-8 text-center text-sm text-muted-foreground">
          No topology data available for replay
        </div>
      </div>

      <!-- Artifacts Tab -->
      <div v-if="activeTab === 'artifacts'">
        <ArtifactBrowser :steps="runStore.steps" />
      </div>

      <!-- Meta Tab -->
      <div v-if="activeTab === 'meta'">
        <div v-if="!runStore.run.run_meta || Object.keys(runStore.run.run_meta).length === 0" class="rounded-lg border border-border bg-card p-8 text-center text-sm text-muted-foreground">
          No user metadata for this run
        </div>
        <div v-else class="rounded-lg border border-border bg-card">
          <div
            v-for="(value, key) in runStore.run.run_meta"
            :key="String(key)"
            class="flex items-start gap-4 border-b border-border px-4 py-3 last:border-0"
          >
            <span class="w-40 shrink-0 font-mono text-xs text-muted-foreground">{{ key }}</span>
            <pre class="flex-1 overflow-x-auto font-mono text-xs text-foreground">{{ typeof value === 'object' ? JSON.stringify(value, null, 2) : value }}</pre>
          </div>
        </div>
      </div>

      <!-- Step Inspector Sidebar -->
      <StepInspector
        :open="inspectorOpen"
        :step="inspectorStep"
        :events="inspectorEvents"
        @close="closeInspector"
      />
    </template>
  </div>
</template>
