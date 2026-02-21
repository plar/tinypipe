<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { TopologyNode } from '@/types'
import { api } from '@/api/client'
import { processEvents } from '@/lib/event-processor'
import { formatDuration, shortId, formatTimestamp } from '@/lib/utils'
import { statusBadgeVariant } from '@/lib/view-helpers'
import { usePipelinesStore } from '@/stores/pipelines'
import { useUiStore } from '@/stores/ui'
import DagErrorBoundary from '@/components/dag/DagErrorBoundary.vue'
import DagCanvasPixi from '@/components/dag/DagCanvasPixi.vue'
import DagLegend from '@/components/dag/DagLegend.vue'
import Sidebar from '@/components/inspector/Sidebar.vue'
import DataTable from '@/components/ui/DataTable.vue'
import Badge from '@/components/ui/Badge.vue'
import TabBar from '@/components/ui/TabBar.vue'
import MetricTile from '@/components/ui/MetricTile.vue'
import StatusIndicator from '@/components/ui/StatusIndicator.vue'
import LoadingState from '@/components/ui/LoadingState.vue'
import ErrorBanner from '@/components/ui/ErrorBanner.vue'
import Sparkline from '@/components/ui/Sparkline.vue'
import CleanupDialog from '@/components/ui/CleanupDialog.vue'
import { ArrowLeft, Trash2, GitCompareArrows } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const store = usePipelinesStore()
const ui = useUiStore()
const hash = computed(() => route.params.hash as string)

const loading = ref(true)
const error = ref('')
const activeTab = ref((route.query.tab as string) || 'dag')
const statusFilter = ref('')
const stepStatuses = ref<Record<string, string>>({})

// Cleanup dialog
const showCleanup = ref(false)

// Select-to-compare
const selectedRuns = ref<string[]>([])

// Pagination
const loadingMore = ref(false)
const hasMore = ref(true)

// Use store for cached data
const pipeline = computed(() => store.getDetail(hash.value))
const runs = computed(() => store.getRuns(hash.value))
const stats = computed(() => store.getStats(hash.value))

// Topology node inspector
const selectedTopologyNode = computed<TopologyNode | null>(() => {
  if (!ui.selectedNode || !pipeline.value?.topology) return null
  return pipeline.value.topology.nodes[ui.selectedNode] ?? null
})

const upstreamNodes = computed<string[]>(() => {
  if (!ui.selectedNode || !pipeline.value?.topology) return []
  return Object.entries(pipeline.value.topology.nodes)
    .filter(([, node]) => node.targets.includes(ui.selectedNode!))
    .map(([name]) => name)
})

const nodeDetailRows = computed(() => {
  if (!ui.selectedNode || !selectedTopologyNode.value) return []
  const node = selectedTopologyNode.value
  const rows: Array<{ key: string; value: unknown }> = [
    { key: 'Name', value: ui.selectedNode },
    { key: 'Kind', value: node.kind },
  ]
  if (node.targets.length > 0) {
    rows.push({ key: 'Targets', value: node.targets.join(', ') })
  }
  if (upstreamNodes.value.length > 0) {
    rows.push({ key: 'Upstream', value: upstreamNodes.value.join(', ') })
  }
  return rows
})

const tabs = [
  { key: 'dag', label: 'DAG' },
  { key: 'runs', label: 'Runs' },
  { key: 'stats', label: 'Stats' },
]

function switchTab(tab: string) {
  activeTab.value = tab
  router.replace({ query: { ...route.query, tab } })
}

async function loadRuns() {
  selectedRuns.value = []
  hasMore.value = true
  await store.fetchRuns(hash.value, {
    status: statusFilter.value || undefined,
    limit: 50,
  })
  if (runs.value.length < 50) hasMore.value = false
}

async function loadMoreRuns() {
  loadingMore.value = true
  try {
    const count = await store.fetchMoreRuns(hash.value, {
      status: statusFilter.value || undefined,
      limit: 50,
    })
    if (count < 50) hasMore.value = false
  } finally {
    loadingMore.value = false
  }
}

// Compare selected runs
const canCompare = computed(() => selectedRuns.value.length === 2)

function compareSelected() {
  if (!canCompare.value) return
  router.push({
    path: '/compare',
    query: { run1: selectedRuns.value[0], run2: selectedRuns.value[1] },
  })
}

function toggleRunSelection(runId: string) {
  const idx = selectedRuns.value.indexOf(runId)
  if (idx >= 0) {
    selectedRuns.value.splice(idx, 1)
  } else if (selectedRuns.value.length < 2) {
    selectedRuns.value.push(runId)
  }
}

// Stats computeds
const statusEntries = computed(() => {
  if (!stats.value) return []
  return Object.entries(stats.value.status_counts).sort(([, a], [, b]) => b - a)
})

const dailyActivityData = computed<Array<[string, number]>>(() => {
  if (!stats.value?.daily_activity) return []
  return Object.entries(stats.value.daily_activity).sort(([a], [b]) => a.localeCompare(b))
})

// Duration trend sparkline (computed from runs data)
const durationTrendData = computed<Array<[string, number]>>(() => {
  return store.getRuns(hash.value)
    .filter(r => r.duration_seconds !== null)
    .reverse() // oldest first
    .map(r => [shortId(r.run_id, 8), r.duration_seconds!] as [string, number])
})

// Error heatmap by step
const failureHotspots = computed(() => {
  const counts: Record<string, number> = {}
  for (const run of store.getRuns(hash.value)) {
    if (run.status === 'failed' && run.error_step) {
      counts[run.error_step] = (counts[run.error_step] || 0) + 1
    }
  }
  return Object.entries(counts).sort(([, a], [, b]) => b - a)
})

const maxFailureCount = computed(() => {
  if (failureHotspots.value.length === 0) return 1
  return failureHotspots.value[0]![1]
})

function onCleanupDone(count: number) {
  if (count > 0) {
    // Refresh data after cleanup
    store.fetchRuns(hash.value, { limit: 50 })
    store.fetchStats(hash.value)
  }
}

onMounted(async () => {
  try {
    await Promise.all([
      store.fetchDetail(hash.value),
      store.fetchRuns(hash.value, { limit: 50 }),
      store.fetchStats(hash.value),
    ])

    if (runs.value.length < 50) hasMore.value = false

    // Compute step statuses from latest run's events for DAG coloring
    const r = store.getRuns(hash.value)
    if (r.length > 0) {
      try {
        const latestEvents = await api.getEvents(r[0]!.run_id)
        const steps = processEvents(latestEvents)
        const statuses: Record<string, string> = {}
        for (const step of steps) {
          statuses[step.name] = step.status
        }
        stepStatuses.value = statuses
      } catch {
        // Non-critical — DAG still works without status colors
      }
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
})

// Re-fetch when navigating to a different pipeline
watch(hash, async (newHash) => {
  loading.value = true
  error.value = ''
  stepStatuses.value = {}
  selectedRuns.value = []
  hasMore.value = true
  try {
    await Promise.all([
      store.fetchDetail(newHash),
      store.fetchRuns(newHash, { limit: 50 }),
      store.fetchStats(newHash),
    ])
    if (runs.value.length < 50) hasMore.value = false
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <LoadingState v-if="loading" />
    <ErrorBanner v-else-if="error" :message="error" />
    <template v-else-if="pipeline">
      <!-- Header -->
      <div class="mb-6">
        <div class="flex items-center justify-between">
          <RouterLink to="/" class="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors">
            <ArrowLeft class="h-3.5 w-3.5" />
            Fleet Command
          </RouterLink>
          <button
            class="inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            @click="showCleanup = true"
          >
            <Trash2 class="h-3.5 w-3.5" />
            Cleanup
          </button>
        </div>
        <h1 class="mt-2 text-2xl font-semibold text-foreground">{{ pipeline.name }}</h1>
        <p class="mt-0.5 font-mono text-xs text-muted-foreground">{{ pipeline.hash }}</p>
      </div>

      <!-- Tabs -->
      <div class="mb-6">
        <TabBar :tabs="tabs" :active="activeTab" @select="switchTab" />
      </div>

      <!-- DAG Tab (v-show to persist WebGL context) -->
      <div v-show="activeTab === 'dag'">
        <DagErrorBoundary>
          <DagCanvasPixi
            v-if="pipeline.topology"
            :topology="pipeline.topology"
            :visual-ast="pipeline.visual_ast"
            :step-statuses="stepStatuses"
            @navigate-sub="$router.push(`/pipeline/${$event}`)"
          >
            <template #legend>
              <DagLegend />
            </template>
          </DagCanvasPixi>
        </DagErrorBoundary>
        <div v-if="!pipeline.topology" class="rounded-lg border border-border bg-card p-8 text-center text-sm text-muted-foreground">
          No topology data available for this pipeline.
        </div>
      </div>

      <!-- Runs Tab -->
      <div v-if="activeTab === 'runs'">
        <!-- Filter -->
        <div class="mb-4 flex items-center gap-3">
          <select
            v-model="statusFilter"
            class="rounded-md border border-border bg-input px-3 py-1.5 text-sm text-foreground"
            @change="loadRuns()"
          >
            <option value="">All statuses</option>
            <option value="success">Success</option>
            <option value="failed">Failed</option>
            <option value="timeout">Timeout</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <span class="text-xs text-muted-foreground">
            Showing {{ runs.length }} run(s){{ hasMore ? '+' : '' }}
          </span>
        </div>

        <!-- Runs table -->
        <div class="overflow-hidden rounded-lg border border-border">
          <table class="w-full text-sm">
            <thead class="bg-muted/50 text-left text-xs uppercase tracking-wider text-muted-foreground">
              <tr>
                <th class="w-10 px-4 py-3 font-medium"></th>
                <th class="px-4 py-3 font-medium">Run ID</th>
                <th class="px-4 py-3 font-medium">Status</th>
                <th class="px-4 py-3 font-medium">Started</th>
                <th class="px-4 py-3 font-medium">Duration</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-border">
              <tr
                v-for="run in runs"
                :key="run.run_id"
                class="cursor-pointer transition-colors hover:bg-accent/30"
                :class="{ 'bg-primary/5': selectedRuns.includes(run.run_id) }"
              >
                <td class="px-4 py-3" @click.stop>
                  <input
                    type="checkbox"
                    :checked="selectedRuns.includes(run.run_id)"
                    :disabled="!selectedRuns.includes(run.run_id) && selectedRuns.length >= 2"
                    class="rounded border-border"
                    @change="toggleRunSelection(run.run_id)"
                  />
                </td>
                <td class="px-4 py-3 font-mono text-xs" @click="$router.push(`/run/${run.run_id}`)">{{ shortId(run.run_id) }}</td>
                <td class="px-4 py-3" @click="$router.push(`/run/${run.run_id}`)">
                  <div class="flex items-center gap-2">
                    <StatusIndicator :status="run.status" size="sm" />
                    <Badge :variant="statusBadgeVariant(run.status)">{{ run.status }}</Badge>
                  </div>
                </td>
                <td class="px-4 py-3 text-muted-foreground" @click="$router.push(`/run/${run.run_id}`)">{{ formatTimestamp(run.start_time) }}</td>
                <td class="px-4 py-3 tabular-nums" @click="$router.push(`/run/${run.run_id}`)">{{ formatDuration(run.duration_seconds) }}</td>
              </tr>
              <tr v-if="runs.length === 0">
                <td colspan="5" class="px-4 py-8 text-center text-muted-foreground">No runs found</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Load more -->
        <div v-if="hasMore" class="mt-4 text-center">
          <button
            class="rounded-md border border-border px-4 py-1.5 text-sm text-muted-foreground hover:bg-accent/30 hover:text-foreground disabled:opacity-50"
            :disabled="loadingMore"
            @click="loadMoreRuns"
          >
            {{ loadingMore ? 'Loading...' : 'Load more' }}
          </button>
        </div>

        <!-- Floating compare bar -->
        <Teleport to="body">
          <Transition name="slide-up">
            <div
              v-if="selectedRuns.length > 0"
              class="fixed bottom-6 left-1/2 z-40 flex -translate-x-1/2 items-center gap-3 rounded-lg border border-border bg-card px-4 py-2.5 shadow-lg"
            >
              <span class="text-sm text-muted-foreground">{{ selectedRuns.length }} run(s) selected</span>
              <button
                class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                :disabled="!canCompare"
                @click="compareSelected"
              >
                <span class="flex items-center gap-1.5">
                  <GitCompareArrows class="h-3.5 w-3.5" />
                  Compare
                </span>
              </button>
              <button
                class="text-xs text-muted-foreground hover:text-foreground"
                @click="selectedRuns = []"
              >
                Clear
              </button>
            </div>
          </Transition>
        </Teleport>
      </div>

      <!-- Stats Tab -->
      <div v-if="activeTab === 'stats' && stats">
        <!-- Summary tiles -->
        <div class="mb-6 grid gap-4 sm:grid-cols-4 stagger-reveal">
          <MetricTile label="Total Runs" :value="stats.total_runs" :sublabel="`Last ${stats.days} days`" />
          <MetricTile label="Success Rate" :value="`${stats.success_rate}%`" />
          <MetricTile
            label="Avg Duration"
            :value="stats.duration_stats ? formatDuration(stats.duration_stats.avg) : '-'"
          />
          <MetricTile label="Failures" :value="stats.failed_count" />
        </div>

        <!-- Status breakdown -->
        <div class="mb-6 rounded-lg border border-border bg-card p-4">
          <h4 class="border-l-2 border-primary/40 pl-3 mb-3 text-sm font-medium text-foreground">Status Breakdown</h4>
          <div class="space-y-2">
            <div v-for="[status, count] in statusEntries" :key="status" class="flex items-center gap-3">
              <span class="w-24 text-sm text-muted-foreground capitalize">{{ status }}</span>
              <div class="flex-1">
                <div class="h-5 overflow-hidden rounded bg-muted">
                  <div
                    class="h-full rounded status-bar"
                    :class="{
                      'bg-success': status === 'success',
                      'bg-destructive': status === 'failed',
                      'bg-warning': status === 'timeout',
                      'bg-muted-foreground': status === 'cancelled' || status === 'client_closed',
                    }"
                    :style="{ width: stats.total_runs ? (count / stats.total_runs * 100) + '%' : '0%' }"
                  />
                </div>
              </div>
              <span class="w-12 text-right text-sm font-medium tabular-nums">{{ count }}</span>
            </div>
          </div>
        </div>

        <!-- Daily Activity -->
        <div v-if="dailyActivityData.length > 1" class="mb-6 rounded-lg border border-border bg-card p-4">
          <h4 class="border-l-2 border-primary/40 pl-3 mb-3 text-sm font-medium text-foreground">Daily Activity</h4>
          <Sparkline :data="dailyActivityData" :height="48" :bars="true" />
          <div class="mt-2 flex justify-between text-[9px] font-mono text-muted-foreground">
            <span>{{ dailyActivityData[0]?.[0] }}</span>
            <span>{{ dailyActivityData[dailyActivityData.length - 1]?.[0] }}</span>
          </div>
        </div>

        <!-- Duration Trend -->
        <div v-if="durationTrendData.length > 1" class="mb-6 rounded-lg border border-border bg-card p-4">
          <h4 class="border-l-2 border-primary/40 pl-3 mb-3 text-sm font-medium text-foreground">Duration Trend</h4>
          <Sparkline :data="durationTrendData" :height="48" color="var(--color-warning)" />
          <div class="mt-2 flex justify-between text-[9px] font-mono text-muted-foreground">
            <span>{{ durationTrendData[0]?.[0] }}</span>
            <span>{{ durationTrendData[durationTrendData.length - 1]?.[0] }}</span>
          </div>
        </div>

        <!-- Failure Hotspots (Error Heatmap by Step) -->
        <div v-if="failureHotspots.length" class="mb-6 rounded-lg border border-border bg-card p-4">
          <h4 class="border-l-2 border-primary/40 pl-3 mb-3 text-sm font-medium text-foreground">Failure Hotspots</h4>
          <div class="space-y-2">
            <div v-for="[step, count] in failureHotspots" :key="step" class="flex items-center gap-3">
              <span class="w-40 truncate font-mono text-xs text-muted-foreground">{{ step }}</span>
              <div class="flex-1">
                <div class="h-4 overflow-hidden rounded bg-muted">
                  <div
                    class="h-full rounded bg-destructive/70 transition-all"
                    :style="{ width: (count / maxFailureCount * 100) + '%' }"
                  />
                </div>
              </div>
              <span class="w-10 text-right text-xs font-medium tabular-nums">{{ count }}</span>
            </div>
          </div>
        </div>

        <!-- Recent errors -->
        <div v-if="stats.recent_errors.length" class="rounded-lg border border-border bg-card p-4">
          <h4 class="border-l-2 border-primary/40 pl-3 mb-3 text-sm font-medium text-foreground">Recent Errors</h4>
          <div class="space-y-2">
            <div
              v-for="err in stats.recent_errors"
              :key="err.run_id"
              class="rounded-md border border-destructive/20 bg-destructive/5 p-3 text-sm"
            >
              <div class="flex items-center gap-2">
                <RouterLink
                  :to="`/run/${err.run_id}`"
                  class="font-mono text-xs text-destructive hover:underline"
                >
                  {{ err.run_id.slice(0, 12) }}
                </RouterLink>
                <span v-if="err.error_step" class="text-xs text-destructive/70">
                  at {{ err.error_step }}
                </span>
              </div>
              <p v-if="err.error_message" class="mt-1 truncate text-destructive/80">
                {{ err.error_message }}
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- Topology Node Inspector Sidebar -->
      <Sidebar
        :open="ui.inspectorOpen"
        :title="ui.selectedNode ?? 'Node'"
        @close="ui.closeInspector"
      >
        <template v-if="selectedTopologyNode">
          <div class="mb-4 flex items-center gap-2">
            <Badge variant="muted">{{ selectedTopologyNode.kind }}</Badge>
            <span class="font-mono text-sm font-medium text-foreground">{{ ui.selectedNode }}</span>
          </div>
          <DataTable :rows="nodeDetailRows" />

          <!-- Downstream targets as clickable links -->
          <div v-if="selectedTopologyNode.targets.length" class="mt-4">
            <h4 class="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">Downstream</h4>
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="target in selectedTopologyNode.targets"
                :key="target"
                class="rounded-md border border-border bg-muted/50 px-2 py-1 font-mono text-xs text-foreground hover:bg-accent/30 transition-colors"
                @click="ui.selectNode(target)"
              >
                {{ target }}
              </button>
            </div>
          </div>

          <!-- Upstream sources as clickable links -->
          <div v-if="upstreamNodes.length" class="mt-4">
            <h4 class="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">Upstream</h4>
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="source in upstreamNodes"
                :key="source"
                class="rounded-md border border-border bg-muted/50 px-2 py-1 font-mono text-xs text-foreground hover:bg-accent/30 transition-colors"
                @click="ui.selectNode(source)"
              >
                {{ source }}
              </button>
            </div>
          </div>
        </template>
      </Sidebar>

      <!-- Cleanup Dialog -->
      <CleanupDialog
        v-if="showCleanup"
        :pipeline-hash="hash"
        :pipeline-name="pipeline.name"
        @close="showCleanup = false"
        @cleaned="onCleanupDone"
      />
    </template>
  </div>
</template>

<style scoped>
.status-bar {
  transition: width 0.6s ease-out;
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.2s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
  transform: translate(-50%, 10px);
}
</style>
