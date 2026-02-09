# Terminal Semantics

justpipe emits one terminal `EventType.FINISH` for all completed runtime paths. The event carries a structured payload `PipelineEndData`:

- `status: PipelineTerminalStatus`
- `duration_s: float`
- `error: str | None`
- `reason: str | None`
- `failure_kind`
- `failure_source`
- `failed_step: str | None`
- `errors: list[FailureRecord]`

## Status values
- `SUCCESS`
- `FAILED`
- `TIMEOUT`
- `CANCELLED`
- `CLIENT_CLOSED`

`FAILED` is further classified by diagnostics:
- `failure_kind`: `validation|startup|step|shutdown|infra`
- `failure_source`: `user_code|framework|external_dep`

You can configure `failure_source` classification via
`Pipe(..., failure_classification=FailureClassificationConfig(...))`.

`source_classifier` receives `FailureClassificationContext` and may return:
- `FailureSource` to override classification
- `None` to keep the framework default

`external_dependency_prefixes` extends the built-in module prefix list used by
the framework heuristic (`type(error).__module__.startswith(...)`).

Classifier errors are non-fatal. The run keeps the default source and appends an
infra diagnostic record with reason `classifier_error`.

## Ordering
`START` → … (step/map/barrier events) … → `FINISH`

If a timeout occurs, a `TIMEOUT` event is emitted before `FINISH`. Cooperative cancellation emits `CANCELLED` before `FINISH`.

Client-side stream close (`aclose()`) is a transport abort: shutdown cleanup runs, but terminal events are not emitted on the closed stream.

## Event Schema Notes
- `Event.type`: enum value
- `Event.stage`: step name or "system"
- `Event.data`: free-form except for `FINISH` (must be `PipelineEndData`)
- `timestamp`: epoch seconds (float)
- `EVENT_SCHEMA_VERSION`: exported constant in `justpipe.types` (currently `"1.0"`)

Schema version suggestion: treat the fields above as v1; any additions should be backward compatible (additive fields or new event types).
