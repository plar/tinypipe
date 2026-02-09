# Observability and Event Schema

## Event schema version
- `EVENT_SCHEMA_VERSION = "1.0"` is exported from `justpipe.types`.
- Fields:
  - `type`: `EventType`
  - `stage`: step name or `"system"`
  - `data`: free-form except for `FINISH` (must be `PipelineEndData`)
  - `timestamp`: epoch seconds (float)

Backward compatibility: new fields should be additive; schema version should only change on breaking shape changes.

## FINISH payload
- `EventType.FINISH.data` is always `PipelineEndData` with:
  - `status: PipelineTerminalStatus`
  - `duration_s: float`
  - `error: str | None`
  - `reason: str | None`

## Observer guidance
- Observers SHOULD handle unknown event types gracefully.
- Observers SHOULD check `EVENT_SCHEMA_VERSION` if they rely on event shape assumptions.
- Logging/metrics observers should treat FINISH as the terminal record and prefer `status` over string parsing.
