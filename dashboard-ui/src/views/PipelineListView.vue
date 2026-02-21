<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { usePipelinesStore } from '@/stores/pipelines'
import { useUiStore } from '@/stores/ui'
import { formatDuration, relativeTime } from '@/lib/utils'
import { statusForRate } from '@/lib/view-helpers'
import { useKeyboard } from '@/composables/useKeyboard'
import MetricTile from '@/components/ui/MetricTile.vue'
import StatusIndicator from '@/components/ui/StatusIndicator.vue'
import LoadingState from '@/components/ui/LoadingState.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import ErrorBanner from '@/components/ui/ErrorBanner.vue'
import { LayoutGrid, List, ArrowRight } from 'lucide-vue-next'

const store = usePipelinesStore()
const ui = useUiStore()
const search = ref('')
const searchInputRef = ref<HTMLInputElement | null>(null)

onMounted(() => {
  store.fetchPipelines()
})

const avgDuration = computed(() => {
  const durations = store.pipelines
    .map((p) => p.avg_duration_seconds)
    .filter((d): d is number => d !== null)
  if (durations.length === 0) return '-'
  return formatDuration(durations.reduce((a, b) => a + b, 0) / durations.length)
})

const filtered = computed(() =>
  store.pipelines.filter((p) => p.name.toLowerCase().includes(search.value.toLowerCase()))
)

useKeyboard({
  searchRef: searchInputRef,
})
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-6 flex items-end justify-between">
      <div>
        <h1 class="text-2xl font-semibold text-foreground">Fleet Command</h1>
        <p class="mt-1 text-sm text-muted-foreground">
          Monitor and inspect all registered pipelines
        </p>
      </div>
      <div class="flex items-center gap-1 rounded-md border border-border p-0.5">
        <button
          class="rounded p-1.5 transition-colors"
          :class="ui.viewMode === 'cards' ? 'bg-accent text-foreground' : 'text-muted-foreground hover:text-foreground'"
          @click="ui.viewMode = 'cards'"
        >
          <LayoutGrid class="h-4 w-4" />
        </button>
        <button
          class="rounded p-1.5 transition-colors"
          :class="ui.viewMode === 'list' ? 'bg-accent text-foreground' : 'text-muted-foreground hover:text-foreground'"
          @click="ui.viewMode = 'list'"
        >
          <List class="h-4 w-4" />
        </button>
      </div>
    </div>

    <!-- Aggregate Metrics -->
    <div class="mb-8 grid gap-4 sm:grid-cols-3 stagger-reveal">
      <MetricTile
        label="Pipelines"
        :value="store.totalPipelines"
        sublabel="Registered"
      />
      <MetricTile
        label="Total Runs"
        :value="store.totalRuns"
        sublabel="Across all pipelines"
      />
      <MetricTile
        label="Avg Duration"
        :value="avgDuration"
        sublabel="Per run"
      />
    </div>

    <!-- Search -->
    <div v-if="store.pipelines.length > 0" class="mb-4">
      <input
        ref="searchInputRef"
        v-model="search"
        placeholder="Filter pipelines...  (press / to focus)"
        class="w-full rounded-md border border-border bg-input px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary/50 focus:outline-none focus:ring-1 focus:ring-primary/30"
      />
    </div>

    <!-- Loading -->
    <LoadingState v-if="store.loading" text="Discovering pipelines..." />

    <!-- Error -->
    <ErrorBanner v-else-if="store.error" :message="store.error" />

    <!-- Empty -->
    <EmptyState
      v-else-if="store.pipelines.length === 0"
      title="No Pipelines Discovered"
      description="Run a pipeline with persist=True to see data here."
    />

    <!-- No search results -->
    <div
      v-else-if="filtered.length === 0"
      class="rounded-lg border border-border bg-card p-8 text-center text-sm text-muted-foreground"
    >
      No pipelines match "{{ search }}"
    </div>

    <!-- Card grid -->
    <div
      v-else-if="ui.viewMode === 'cards'"
      class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 stagger-reveal"
    >
      <RouterLink
        v-for="p in filtered"
        :key="p.hash"
        :to="`/pipeline/${p.hash}`"
        class="group rounded-lg border border-border bg-card p-5 transition-all hover:border-primary/30 hover:shadow-lg hover:shadow-primary/5"
      >
        <div class="flex items-start justify-between">
          <div>
            <h3 class="font-semibold text-foreground group-hover:text-primary transition-colors">
              {{ p.name }}
            </h3>
            <p class="mt-0.5 font-mono text-xs text-muted-foreground">{{ p.hash.slice(0, 12) }}</p>
          </div>
          <StatusIndicator :status="statusForRate(p.success_rate)" size="md" />
        </div>

        <div class="mt-4 grid grid-cols-3 gap-3 text-center">
          <div>
            <p class="text-lg font-semibold tabular-nums">{{ p.total_runs }}</p>
            <p class="text-[10px] uppercase tracking-wider text-muted-foreground">Runs</p>
          </div>
          <div>
            <p class="text-lg font-semibold tabular-nums" :class="p.success_rate >= 90 ? 'text-success' : p.success_rate >= 70 ? 'text-warning' : 'text-destructive'">
              {{ p.success_rate.toFixed(0) }}%
            </p>
            <p class="text-[10px] uppercase tracking-wider text-muted-foreground">Success</p>
          </div>
          <div>
            <p class="text-lg font-semibold tabular-nums">{{ formatDuration(p.avg_duration_seconds) }}</p>
            <p class="text-[10px] uppercase tracking-wider text-muted-foreground">Avg</p>
          </div>
        </div>

        <div class="mt-4 flex items-center justify-between text-xs text-muted-foreground">
          <span v-if="p.last_run_time">{{ relativeTime(p.last_run_time) }}</span>
          <span v-else>No runs</span>
          <ArrowRight class="h-3.5 w-3.5 opacity-0 transition-opacity group-hover:opacity-100" />
        </div>
      </RouterLink>
    </div>

    <!-- List view -->
    <div
      v-else
      class="overflow-hidden rounded-lg border border-border"
    >
      <table class="w-full text-sm">
        <thead class="bg-muted/50 text-left text-xs uppercase tracking-wider text-muted-foreground">
          <tr>
            <th class="px-4 py-3 font-medium">Pipeline</th>
            <th class="px-4 py-3 font-medium">Runs</th>
            <th class="px-4 py-3 font-medium">Success</th>
            <th class="px-4 py-3 font-medium">Avg Duration</th>
            <th class="px-4 py-3 font-medium">Last Run</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-border">
          <tr
            v-for="p in filtered"
            :key="p.hash"
            class="cursor-pointer transition-colors hover:bg-accent/30"
            @click="$router.push(`/pipeline/${p.hash}`)"
          >
            <td class="px-4 py-3">
              <div class="flex items-center gap-2">
                <StatusIndicator :status="statusForRate(p.success_rate)" size="sm" />
                <span class="font-medium text-foreground">{{ p.name }}</span>
                <span class="font-mono text-xs text-muted-foreground">{{ p.hash.slice(0, 8) }}</span>
              </div>
            </td>
            <td class="px-4 py-3 tabular-nums">{{ p.total_runs }}</td>
            <td class="px-4 py-3 tabular-nums" :class="p.success_rate >= 90 ? 'text-success' : p.success_rate >= 70 ? 'text-warning' : 'text-destructive'">
              {{ p.success_rate.toFixed(0) }}%
            </td>
            <td class="px-4 py-3 tabular-nums">{{ formatDuration(p.avg_duration_seconds) }}</td>
            <td class="px-4 py-3 text-muted-foreground">
              {{ p.last_run_time ? relativeTime(p.last_run_time) : '-' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
