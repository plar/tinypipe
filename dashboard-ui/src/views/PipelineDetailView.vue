<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import type { PipelineSummary, Run, Stats, TopologyNode } from '@/types'
import { api } from '@/api/client'
import { processEvents } from '@/lib/event-processor'
import { formatDuration, shortId, formatTimestamp } from '@/lib/utils'
import { useUiStore } from '@/stores/ui'
import DagCanvasPixi from '@/components/dag/DagCanvasPixi.vue'
import DagLegend from '@/components/dag/DagLegend.vue'
import Sidebar from '@/components/inspector/Sidebar.vue'
import DataTable from '@/components/ui/DataTable.vue'
import Badge from '@/components/ui/Badge.vue'
import TabBar from '@/components/ui/TabBar.vue'
import MetricTile from '@/components/ui/MetricTile.vue'
import StatusIndicator from '@/components/ui/StatusIndicator.vue'
import LoadingState from '@/components/ui/LoadingState.vue'
import Sparkline from '@/components/ui/Sparkline.vue'
import { ArrowLeft } from 'lucide-vue-next'

const route = useRoute()
const ui = useUiStore()
const hash = computed(() => route.params.hash as string)

const pipeline = ref<PipelineSummary | null>(null)
const runs = ref<Run[]>([])
const stats = ref<Stats | null>(null)
const loading = ref(true)
const error = ref('')
const activeTab = ref('dag')
const statusFilter = ref('')
const stepStatuses = ref<Record<string, string>>({})

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

async function loadRuns() {
  runs.value = await api.listRuns(hash.value, {
    status: statusFilter.value || undefined,
    limit: 50,
  })
}

const statusEntries = computed(() => {
  if (!stats.value) return []
  return Object.entries(stats.value.status_counts).sort(([, a], [, b]) => b - a)
})

const dailyActivityData = computed<Array<[string, number]>>(() => {
  if (!stats.value?.daily_activity) return []
  return Object.entries(stats.value.daily_activity).sort(([a], [b]) => a.localeCompare(b))
})

function statusBadgeVariant(s: string): 'success' | 'destructive' | 'warning' | 'muted' {
  switch (s) {
    case 'success': return 'success'
    case 'failed': return 'destructive'
    case 'timeout': return 'warning'
    default: return 'muted'
  }
}

onMounted(async () => {
  try {
    const [p, r, s] = await Promise.all([
      api.getPipeline(hash.value),
      api.listRuns(hash.value, { limit: 50 }),
      api.getStats(hash.value),
    ])
    pipeline.value = p
    runs.value = r
    stats.value = s

    // Compute step statuses from latest run's events for DAG coloring
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
</script>

<template>
  <div>
    <LoadingState v-if="loading" />
    <div v-else-if="error" class="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
      {{ error }}
    </div>
    <template v-else-if="pipeline">
      <!-- Header -->
      <div class="mb-6">
        <RouterLink to="/" class="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors">
          <ArrowLeft class="h-3.5 w-3.5" />
          Fleet Command
        </RouterLink>
        <h1 class="mt-2 text-2xl font-semibold text-foreground">{{ pipeline.name }}</h1>
        <p class="mt-0.5 font-mono text-xs text-muted-foreground">{{ pipeline.hash }}</p>
      </div>

      <!-- Tabs -->
      <div class="mb-6">
        <TabBar :tabs="tabs" :active="activeTab" @select="activeTab = $event" />
      </div>

      <!-- DAG Tab -->
      <div v-if="activeTab === 'dag'">
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
        <div v-else class="rounded-lg border border-border bg-card p-8 text-center text-sm text-muted-foreground">
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
          <span class="text-xs text-muted-foreground">{{ runs.length }} run(s)</span>
        </div>

        <!-- Runs table -->
        <div class="overflow-hidden rounded-lg border border-border">
          <table class="w-full text-sm">
            <thead class="bg-muted/50 text-left text-xs uppercase tracking-wider text-muted-foreground">
              <tr>
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
                @click="$router.push(`/run/${run.run_id}`)"
              >
                <td class="px-4 py-3 font-mono text-xs">{{ shortId(run.run_id) }}</td>
                <td class="px-4 py-3">
                  <div class="flex items-center gap-2">
                    <StatusIndicator :status="run.status" size="sm" />
                    <Badge :variant="statusBadgeVariant(run.status)">{{ run.status }}</Badge>
                  </div>
                </td>
                <td class="px-4 py-3 text-muted-foreground">{{ formatTimestamp(run.start_time) }}</td>
                <td class="px-4 py-3 tabular-nums">{{ formatDuration(run.duration_seconds) }}</td>
              </tr>
              <tr v-if="runs.length === 0">
                <td colspan="4" class="px-4 py-8 text-center text-muted-foreground">No runs found</td>
              </tr>
            </tbody>
          </table>
        </div>
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
          <h4 class="mb-3 text-sm font-medium text-foreground">Status Breakdown</h4>
          <div class="space-y-2">
            <div v-for="[status, count] in statusEntries" :key="status" class="flex items-center gap-3">
              <span class="w-24 text-sm text-muted-foreground capitalize">{{ status }}</span>
              <div class="flex-1">
                <div class="h-5 overflow-hidden rounded bg-muted">
                  <div
                    class="h-full rounded transition-all"
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
          <h4 class="mb-3 text-sm font-medium text-foreground">Daily Activity</h4>
          <Sparkline :data="dailyActivityData" :height="48" :bars="true" />
          <div class="mt-2 flex justify-between text-[9px] font-mono text-muted-foreground">
            <span>{{ dailyActivityData[0]?.[0] }}</span>
            <span>{{ dailyActivityData[dailyActivityData.length - 1]?.[0] }}</span>
          </div>
        </div>

        <!-- Recent errors -->
        <div v-if="stats.recent_errors.length" class="rounded-lg border border-border bg-card p-4">
          <h4 class="mb-3 text-sm font-medium text-foreground">Recent Errors</h4>
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
    </template>
  </div>
</template>
