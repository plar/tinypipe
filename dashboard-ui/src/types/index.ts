/* ── Node / topology types ─────────────────────────────────── */

export type NodeKind = 'step' | 'map' | 'switch' | 'sub' | 'barrier'

export type EventTypeName =
  | 'START' | 'FINISH' | 'SUSPEND' | 'TIMEOUT' | 'CANCELLED'
  | 'STEP_START' | 'STEP_END' | 'STEP_ERROR' | 'TOKEN'
  | 'BARRIER_WAIT' | 'BARRIER_RELEASE'
  | 'MAP_START' | 'MAP_WORKER' | 'MAP_COMPLETE'

export type RunStatus = 'success' | 'failed' | 'timeout' | 'cancelled' | 'client_closed'

export interface TopologyNode {
  kind: NodeKind | string
  targets: string[]
  sub_pipeline_hash?: string
}

export interface PipelineTopology {
  name: string
  nodes: Record<string, TopologyNode>
}

/* ── API response types ────────────────────────────────────── */

export interface PipelineSummary {
  name: string
  hash: string
  total_runs: number
  success_count: number
  success_rate: number
  avg_duration_seconds: number | null
  last_run_time: string | null
  topology?: PipelineTopology | null
  visual_ast?: VisualASTData | null
}

export interface Run {
  run_id: string
  pipeline_name: string
  pipeline_hash: string
  status: RunStatus | string
  start_time: string
  end_time: string | null
  duration_seconds: number | null
  error_message: string | null
  error_step: string | null
  run_meta: Record<string, unknown> | null
}

export interface PipelineEvent {
  seq: number
  event_type: EventTypeName | string
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

/* ── Runtime metrics (from FINISH event payload) ───────────── */
/* Mirrors Python dataclasses serialized via dataclasses.asdict() */

export interface QueueMetrics {
  max_depth: number
}

export interface TaskMetrics {
  started: number
  completed: number
  peak_active: number
}

export interface StepTiming {
  count: number
  total_s: number
  min_s: number
  max_s: number
}

export interface BarrierMetrics {
  waits: number
  releases: number
  timeouts: number
  total_wait_s: number
  max_wait_s: number
}

export interface MapMetrics {
  maps_started: number
  maps_completed: number
  workers_started: number
  peak_workers: number
}

export interface RuntimeMetrics {
  queue: QueueMetrics
  tasks: TaskMetrics
  step_latency: Record<string, StepTiming>
  barriers: Record<string, BarrierMetrics>
  maps: MapMetrics
  events: Record<string, number>
  tokens: number
  suspends: number
}

export interface FinishPayload {
  status: RunStatus | string
  duration_s: number
  reason: string | null
  error: string | null
  metrics: RuntimeMetrics | null
}

/* ── VisualAST types (from Python visualization.ast) ───────── */

export type VisualNodeKind = 'step' | 'streaming' | 'map' | 'switch' | 'sub'

export interface VisualNode {
  id: string
  name: string
  kind: VisualNodeKind
  is_entry: boolean
  is_terminal: boolean
  is_isolated: boolean
  is_map_target: boolean
  barrier_type: 'all' | 'any'
  sub_graph?: VisualASTData | null
}

export interface VisualEdge {
  source: string
  target: string
  label?: string | null
  is_map_edge: boolean
}

export interface ParallelGroup {
  id: string
  source_id: string
  node_ids: string[]
}

export interface VisualASTData {
  nodes: Record<string, VisualNode>
  edges: VisualEdge[]
  parallel_groups: ParallelGroup[]
  startup_hooks: string[]
  shutdown_hooks: string[]
}

/* ── Full pipeline detail (with topology) ──────────────────── */

export interface PipelineTopologyFull extends PipelineSummary {
  topology: PipelineTopology
}
