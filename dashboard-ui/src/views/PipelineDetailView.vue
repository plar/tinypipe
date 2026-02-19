<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import type { PipelineSummary, Run, Stats } from '@/types'
import { api } from '@/api/client'
import DagGraph from '@/components/pipeline/DagGraph.vue'
import RunTable from '@/components/run/RunTable.vue'
import StatsPanel from '@/components/stats/StatsPanel.vue'

const route = useRoute()
const hash = computed(() => route.params.hash as string)

const pipeline = ref<PipelineSummary | null>(null)
const runs = ref<Run[]>([])
const stats = ref<Stats | null>(null)
const loading = ref(true)
const error = ref('')
const activeTab = ref<'dag' | 'runs' | 'stats'>('runs')
const statusFilter = ref('')

async function loadRuns() {
  runs.value = await api.listRuns(hash.value, {
    status: statusFilter.value || undefined,
    limit: 50,
  })
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
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <div v-if="loading" class="text-center text-muted-foreground py-8">Loading...</div>
    <div v-else-if="error" class="text-center text-destructive py-8">{{ error }}</div>
    <template v-else-if="pipeline">
      <!-- Header -->
      <div class="mb-6">
        <RouterLink to="/" class="text-sm text-muted-foreground hover:text-foreground">
          &larr; All Pipelines
        </RouterLink>
        <h1 class="mt-2 text-2xl font-bold text-foreground">{{ pipeline.name }}</h1>
        <p class="text-xs font-mono text-muted-foreground">{{ pipeline.hash }}</p>
      </div>

      <!-- Tabs -->
      <div class="mb-6 flex gap-1 rounded-lg bg-muted p-1">
        <button
          v-for="tab in (['dag', 'runs', 'stats'] as const)"
          :key="tab"
          class="rounded-md px-4 py-1.5 text-sm font-medium transition-colors capitalize"
          :class="activeTab === tab ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'"
          @click="activeTab = tab"
        >
          {{ tab === 'dag' ? 'DAG' : tab }}
        </button>
      </div>

      <!-- DAG tab -->
      <div v-if="activeTab === 'dag'">
        <DagGraph v-if="pipeline.topology" :topology="pipeline.topology" />
        <p v-else class="text-sm text-muted-foreground">No topology data available</p>
      </div>

      <!-- Runs tab -->
      <div v-if="activeTab === 'runs'">
        <div class="mb-4 flex items-center gap-3">
          <select
            v-model="statusFilter"
            class="rounded-md border border-input bg-background px-3 py-1.5 text-sm"
            @change="loadRuns()"
          >
            <option value="">All statuses</option>
            <option value="success">Success</option>
            <option value="failed">Failed</option>
            <option value="timeout">Timeout</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>
        <RunTable :runs="runs" />
      </div>

      <!-- Stats tab -->
      <div v-if="activeTab === 'stats' && stats">
        <StatsPanel :stats="stats" />
      </div>
    </template>
  </div>
</template>
