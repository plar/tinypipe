import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/api/client'
import type { PipelineSummary, Run, Stats } from '@/types'

export const usePipelinesStore = defineStore('pipelines', () => {
  /* ── State ───────────────────────────────────────────────── */
  const pipelines = ref<PipelineSummary[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Per-pipeline caches (keyed by hash)
  const detailCache = ref<Record<string, PipelineSummary>>({})
  const runsCache = ref<Record<string, Run[]>>({})
  const statsCache = ref<Record<string, Stats>>({})

  /* ── Computed ────────────────────────────────────────────── */
  const totalPipelines = computed(() => pipelines.value.length)

  const totalRuns = computed(() =>
    pipelines.value.reduce((sum, p) => sum + p.total_runs, 0)
  )

  const overallSuccessRate = computed(() => {
    const total = pipelines.value.reduce((sum, p) => sum + p.total_runs, 0)
    if (total === 0) return 0
    const successes = pipelines.value.reduce((sum, p) => sum + p.success_count, 0)
    return Math.round((successes / total) * 100)
  })

  /* ── Actions ─────────────────────────────────────────────── */
  async function fetchPipelines() {
    loading.value = true
    error.value = null
    try {
      pipelines.value = await api.listPipelines()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch pipelines'
    } finally {
      loading.value = false
    }
  }

  async function fetchDetail(hash: string) {
    try {
      detailCache.value[hash] = await api.getPipeline(hash)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch pipeline'
    }
  }

  async function fetchRuns(hash: string, params?: { status?: string; limit?: number; offset?: number }) {
    try {
      runsCache.value[hash] = await api.listRuns(hash, params)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch runs'
    }
  }

  async function fetchStats(hash: string, days = 7) {
    try {
      statsCache.value[hash] = await api.getStats(hash, days)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch stats'
    }
  }

  function getDetail(hash: string) {
    return detailCache.value[hash] ?? null
  }

  function getRuns(hash: string) {
    return runsCache.value[hash] ?? []
  }

  async function fetchMoreRuns(hash: string, params?: { status?: string; limit?: number }) {
    const current = runsCache.value[hash] ?? []
    const limit = params?.limit ?? 50
    const more = await api.listRuns(hash, { ...params, limit, offset: current.length })
    runsCache.value[hash] = [...current, ...more]
    return more.length
  }

  function getStats(hash: string) {
    return statsCache.value[hash] ?? null
  }

  return {
    pipelines,
    loading,
    error,
    totalPipelines,
    totalRuns,
    overallSuccessRate,
    fetchPipelines,
    fetchDetail,
    fetchRuns,
    fetchStats,
    getDetail,
    getRuns,
    fetchMoreRuns,
    getStats,
  }
})
