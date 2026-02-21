import type {
  PipelineSummary,
  Run,
  PipelineEvent,
  TimelineEntry,
  Comparison,
  Stats,
} from '@/types'

const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`)
  }
  return res.json()
}

async function post<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: 'POST' })
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`)
  }
  return res.json()
}

export const api = {
  listPipelines(): Promise<PipelineSummary[]> {
    return get('/pipelines')
  },

  getPipeline(hash: string): Promise<PipelineSummary> {
    return get(`/pipelines/${hash}`)
  },

  listRuns(
    hash: string,
    params?: { status?: string; limit?: number; offset?: number }
  ): Promise<Run[]> {
    const qs = new URLSearchParams()
    if (params?.status) qs.set('status', params.status)
    if (params?.limit) qs.set('limit', String(params.limit))
    if (params?.offset) qs.set('offset', String(params.offset))
    const q = qs.toString()
    return get(`/pipelines/${hash}/runs${q ? '?' + q : ''}`)
  },

  getRun(id: string): Promise<Run> {
    return get(`/runs/${id}`)
  },

  getEvents(runId: string, type?: string): Promise<PipelineEvent[]> {
    const q = type ? `?type=${type}` : ''
    return get(`/runs/${runId}/events${q}`)
  },

  getTimeline(runId: string): Promise<TimelineEntry[]> {
    return get(`/runs/${runId}/timeline`)
  },

  compare(run1: string, run2: string): Promise<Comparison> {
    return get(`/compare?run1=${run1}&run2=${run2}`)
  },

  getStats(hash: string, days = 7): Promise<Stats> {
    return get(`/stats/${hash}?days=${days}`)
  },

  async exportRun(runId: string): Promise<{ run: Run; events: PipelineEvent[] }> {
    const [run, events] = await Promise.all([this.getRun(runId), this.getEvents(runId)])
    return { run, events }
  },

  searchRuns(prefix: string, limit = 10): Promise<Run[]> {
    return get(`/runs/search?q=${encodeURIComponent(prefix)}&limit=${limit}`)
  },

  cleanupRuns(
    hash: string,
    params: { older_than_days?: number; status?: string; keep?: number; dry_run?: boolean }
  ): Promise<{ count: number; runs: Run[] }> {
    const qs = new URLSearchParams()
    if (params.older_than_days != null) qs.set('older_than_days', String(params.older_than_days))
    if (params.status) qs.set('status', params.status)
    if (params.keep != null) qs.set('keep', String(params.keep))
    if (params.dry_run != null) qs.set('dry_run', String(params.dry_run))
    const q = qs.toString()
    return post(`/pipelines/${hash}/cleanup${q ? '?' + q : ''}`)
  },
}
