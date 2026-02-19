export interface PipelineSummary {
  name: string
  hash: string
  total_runs: number
  success_count: number
  success_rate: number
  avg_duration_seconds: number | null
  last_run_time: string | null
  topology?: PipelineTopology | null
}

export interface PipelineTopology {
  name: string
  nodes: Record<string, TopologyStep>
}

export interface TopologyStep {
  kind: string
  targets: string[]
}

export interface Run {
  run_id: string
  pipeline_name: string
  pipeline_hash: string
  status: string
  start_time: string
  end_time: string | null
  duration_seconds: number | null
  error_message: string | null
  error_step: string | null
  run_meta: Record<string, unknown> | null
}

export interface PipelineEvent {
  seq: number
  event_type: string
  step_name: string
  timestamp: string
  data: Record<string, unknown> | null
}

export interface TimelineEntry {
  step_name: string
  start_time: string
  end_time: string
  duration_seconds: number
  status: string
}

export interface Comparison {
  run1_id: string
  run2_id: string
  pipeline1_name: string
  pipeline2_name: string
  duration_diff: number
  status_same: boolean
  pipeline_same: boolean
  step_timing_diff: Record<string, number>
  new_steps: string[]
  removed_steps: string[]
  event_count_diff: number
}

export interface Stats {
  total_runs: number
  days: number
  status_counts: Record<string, number>
  success_count: number
  failed_count: number
  success_rate: number
  duration_stats: {
    avg: number
    min: number
    max: number
    total: number
  } | null
  daily_activity: Record<string, number>
  recent_errors: Array<{
    run_id: string
    start_time: string
    error_message: string | null
    error_step: string | null
  }>
}
