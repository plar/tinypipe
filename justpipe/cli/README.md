# justpipe CLI

Command-line interface for querying and analyzing justpipe pipeline runs.

## Docker-Style Run ID Prefixes

**All commands support Docker-style run ID prefixes!** Instead of typing the full 32-character run ID, you can use just the first 4-12 characters:

```bash
# Full ID (works)
justpipe show a3a4c48b35404f9c9ddcfa0b75886f26

# Prefix (also works!)
justpipe show a3a4c48b

# Minimum 4 characters
justpipe show a3a4

# Compare with prefixes
justpipe compare a3a4 b5f7
```

The CLI will automatically resolve the prefix to the full ID, or show an error if the prefix matches multiple runs.

## Installation

```bash
pip install -e .
# or
uv pip install -e .
```

This installs the CLI with all required dependencies:
- **click** - Enhanced CLI with better help and validation
- **rich** - Beautiful table formatting and colors

## Usage

### With uv

```bash
uv run justpipe [command] [options]
```

### With activated virtualenv

```bash
source .venv/bin/activate
justpipe [command] [options]
```

### Global installation

```bash
pip install -e .
justpipe [command] [options]
```

## Configuration

### Storage Directory

Set the storage directory using an environment variable:

```bash
export JUSTPIPE_STORAGE_DIR=~/.justpipe
```

Default: `~/.justpipe`

## Commands

### list

List pipeline runs with optional filtering.

**Usage**:
```bash
justpipe list [OPTIONS]
```

**Options**:
- `--pipeline, -p NAME` - Filter by pipeline name
- `--status, -s STATUS` - Filter by status (running/success/error/suspended)
- `--limit, -n NUMBER` - Maximum number of runs (default: 10)
- `--full` - Show full run IDs (32 chars) instead of short (12 chars)

**Examples**:
```bash
# List 10 most recent runs
justpipe list

# Filter by pipeline
justpipe list --pipeline my_pipeline

# Filter by status
justpipe list --status success

# Show more results
justpipe list --limit 50

# Combined filters
justpipe list --pipeline my_pipeline --status error --limit 20

# Show full run IDs (32 characters)
justpipe list --full
```

**Output**:
```
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Run ID          ┃ Pipeline          ┃ Status  ┃ Started           ┃ Duration ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ a1b2c3d4e5f6... │ my_pipeline       │ success │ 2026-02-02 14:30  │    2.34s │
│ e5f6g7h8i9j0... │ my_pipeline       │ error   │ 2026-02-02 14:25  │    0.12s │
└─────────────────┴───────────────────┴─────────┴───────────────────┴──────────┘

Showing 2 run(s)
```

---

### show

Show detailed information about a specific run.

**Usage**:
```bash
justpipe show <run-id>
```

**Arguments**:
- `run-id` - Full run ID (from `justpipe list`)

**Examples**:
```bash
justpipe show a1b2c3d4e5f6789012345678
```

**Output**:
```
Run: a1b2c3d4e5f6789012345678
============================================================
Pipeline: my_pipeline
Status: success
Started: 2026-02-02 14:30:00.123
Ended: 2026-02-02 14:30:02.456
Duration: 2.34s

Events: 27 total

Event Breakdown:
  step_start              6
  step_end                6
  start                   1
  finish                  1

Step Sequence:
  1. parse_input
  2. validate_data
  3. process_items
  4. generate_output
  5. save_results
  6. cleanup
```

---

### timeline

Generate execution timeline visualization.

**Usage**:
```bash
justpipe timeline <run-id> [OPTIONS]
```

**Arguments**:
- `run-id` - Full run ID

**Options**:
- `--format, -f FORMAT` - Output format: `ascii`, `html`, or `mermaid` (default: `ascii`)

**Examples**:
```bash
# ASCII timeline (terminal)
justpipe timeline a1b2c3d4e5f6

# HTML timeline (opens in browser)
justpipe timeline a1b2c3d4e5f6 --format html

# Mermaid diagram (for docs)
justpipe timeline a1b2c3d4e5f6 --format mermaid
```

**ASCII Output**:
```
my_pipeline - Execution Timeline (2.34s)

parse_input              ████                                            0.15s
validate_data                ████                                        0.20s
process_items                    ████████████████████                    1.80s ← Bottleneck
generate_output                                          ████            0.12s
save_results                                                 ███         0.05s
cleanup                                                         ██       0.02s

                        0                                        2.34s
```

**HTML Output**:
```
HTML timeline saved to: timeline_a1b2c3d4.html
Open in your browser to view.
```

The HTML file includes:
- Interactive timeline with hover tooltips
- Color-coded steps
- Bottleneck highlighting
- Responsive layout

**Mermaid Output**:
```
Mermaid diagram saved to: timeline_a1b2c3d4.mmd

View online at: https://mermaid.live

gantt
    title my_pipeline Execution Timeline
    dateFormat X
    axisFormat %S

    section Execution
    parse_input: 0, 150
    validate_data: 150, 350
    process_items: 350, 2150
    generate_output: 2150, 2270
    save_results: 2270, 2320
    cleanup: 2320, 2340
```

---

### compare

Compare two pipeline runs to identify differences.

**Usage**:
```bash
justpipe compare <run-id-1> <run-id-2>
```

**Arguments**:
- `run-id-1` - First run ID (baseline)
- `run-id-2` - Second run ID (comparison)

**Examples**:
```bash
# Compare two runs
justpipe compare a1b2c3d4e5f6789 e5f6g7h8i9j0abc

# Compare before/after deployment
justpipe list --pipeline my_pipeline --limit 2
justpipe compare <old-run-id> <new-run-id>
```

**Output**:
```
Run Comparison
============================================================

Run 1 (baseline): a1b2c3d4e5f67890...
Run 2 (compare):  e5f6g7h8i9j0abcd...

Pipeline: my_pipeline
Status:   success

Duration: 2.340s → 3.120s (+0.780s slower)

Step Timing Differences:

  ~ parse                        +0.012s
  ~ validate                     +0.045s
  ~ process                      +0.720s
  ~ finalize                     +0.003s

Event Count Difference: +12 events
```

**Use Cases**:
- Performance regression testing
- A/B testing pipeline versions
- Identifying bottlenecks after changes
- Comparing successful vs failed runs

---

### export

Export run data to JSON for external analysis.

**Usage**:
```bash
justpipe export <run-id> [OPTIONS]
```

**Arguments**:
- `run-id` - Full run ID to export

**Options**:
- `--output, -o FILE` - Output file path (default: `run_<id>.json`)
- `--format, -f FORMAT` - Export format: `json` (default: `json`)

**Examples**:
```bash
# Export to default file
justpipe export a1b2c3d4e5f6

# Export to specific file
justpipe export a1b2c3d4e5f6 --output /tmp/debug_run.json

# Export for analysis
justpipe export a1b2c3d4e5f6 -o analysis/run_data.json
```

**Output**:
```
Run exported to: run_a1b2c3d4.json
  Run ID: a1b2c3d4e5f6789012345678
  Pipeline: my_pipeline
  Events: 27
  Status: success
```

**Export Format** (JSON):
```json
{
  "run": {
    "id": "a1b2c3d4e5f6789012345678",
    "pipeline_name": "my_pipeline",
    "status": "success",
    "start_time": 1738529407.123,
    "start_time_iso": "2026-02-02T19:50:07.123456",
    "end_time": 1738529409.456,
    "end_time_iso": "2026-02-02T19:50:09.456789",
    "duration_seconds": 2.333,
    "metadata": {}
  },
  "events": [
    {
      "id": "evt_1",
      "run_id": "a1b2c3d4e5f6789012345678",
      "event_type": "start",
      "step_name": null,
      "timestamp": 1738529407.123,
      "timestamp_iso": "2026-02-02T19:50:07.123456",
      "payload": {}
    }
  ],
  "event_count": 27,
  "exported_at": "2026-02-02T19:50:10.123456"
}
```

**Use Cases**:
- External analysis with pandas/jupyter
- Sharing run data with team members
- Archiving important runs
- Custom visualization tools
- Integration with monitoring systems

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `JUSTPIPE_STORAGE_DIR` | Storage directory path | `~/.justpipe` |
| `JUSTPIPE_API_KEY` | Cloud API key (future) | - |

## Examples

### Workflow Example

```bash
# Set storage location
export JUSTPIPE_STORAGE_DIR=/path/to/project/.justpipe

# List recent runs
justpipe list --limit 5

# Find failed runs
justpipe list --status error

# Inspect a failed run
justpipe show e5f6g7h8i9j0

# Visualize timeline
justpipe timeline e5f6g7h8i9j0

# Export timeline to HTML for sharing
justpipe timeline e5f6g7h8i9j0 --format html

# Compare two runs
justpipe compare a1b2c3d4e5f6 e5f6g7h8i9j0

# Export run data for analysis
justpipe export e5f6g7h8i9j0 --output /tmp/failed_run.json
```

### Debugging Workflow

```bash
# Find recent runs of specific pipeline
justpipe list --pipeline data_processor

# Show details of latest run
RUN_ID=$(justpipe list --limit 1 | grep -oP '[a-f0-9]{32}' | head -1)
justpipe show $RUN_ID

# Check execution timeline
justpipe timeline $RUN_ID

# Export for detailed analysis
justpipe export $RUN_ID
```

### Performance Regression Testing

```bash
# Before deployment - capture baseline
justpipe list --pipeline my_pipeline --limit 1
BASELINE_ID=<run-id-from-list>

# After deployment - capture new run
# (run your pipeline)
justpipe list --pipeline my_pipeline --limit 1
NEW_RUN_ID=<run-id-from-list>

# Compare performance
justpipe compare $BASELINE_ID $NEW_RUN_ID

# If slower, investigate with timeline
justpipe timeline $NEW_RUN_ID --format html

# Export both for detailed analysis
justpipe export $BASELINE_ID --output baseline.json
justpipe export $NEW_RUN_ID --output new_run.json
```

### CI/CD Integration

```bash
#!/bin/bash
# Check if pipeline succeeded

export JUSTPIPE_STORAGE_DIR=/tmp/ci_pipeline

# Run pipeline
python my_pipeline.py

# Check status
LATEST_RUN=$(justpipe list --limit 1 --status success)
if [ -z "$LATEST_RUN" ]; then
    echo "Pipeline failed!"
    justpipe list --limit 1 --status error
    exit 1
fi

echo "Pipeline succeeded!"
```

## Troubleshooting

### Command not found

**Problem**: `justpipe: command not found`

**Solutions**:
1. Use `uv run justpipe` instead
2. Activate virtual environment: `source .venv/bin/activate`
3. Reinstall package: `uv pip install -e .`

### No runs found

**Problem**: `No runs found`

**Solutions**:
1. Check storage directory: `echo $JUSTPIPE_STORAGE_DIR`
2. Verify runs exist: `ls -la ~/.justpipe/`
3. Run a pipeline first to create data

### Run ID not found

**Problem**: `Run not found: abc123`

**Solution**: Use full run ID (32 characters), not truncated:
```bash
# Wrong (truncated from list output)
justpipe show a1b2c3d4...

# Correct (full ID)
justpipe show a1b2c3d4e5f6789012345678901234
```

## Architecture

### Components

```
justpipe/cli/
├── __init__.py
├── main.py              # CLI entry point (Click-based)
├── commands/
│   ├── list.py          # List command
│   ├── show.py          # Show command
│   └── timeline.py      # Timeline command
└── README.md            # This file
```

### Data Flow

```
User Command
    ↓
CLI Parser (Click)
    ↓
Command Handler (async)
    ↓
Storage Backend (SQLite)
    ↓
Formatted Output (Rich)
```

## API

### Programmatic Usage

You can also use CLI commands programmatically:

```python
import asyncio
from justpipe.cli.main import list_runs, show_run, timeline_run

# List runs
await list_runs(pipeline="my_pipeline", status="success", limit=10)

# Show run details
await show_run("a1b2c3d4e5f6")

# Generate timeline
await timeline_run("a1b2c3d4e5f6", format="ascii")
```

## Commands Summary

| Command | Phase | Status | Description |
|---------|-------|--------|-------------|
| `list` | 2 | ✅ Implemented | List pipeline runs with filters |
| `show` | 2 | ✅ Implemented | Show run details and events |
| `timeline` | 2 | ✅ Implemented | Visualize execution timeline |
| `compare` | 3 | ✅ Implemented | Compare two runs |
| `export` | 3 | ✅ Implemented | Export run data to JSON |

## Programmatic Replay

**Note**: Pipeline replay is available programmatically (not as a CLI command):

```python
from justpipe.observability import ReplayObserver, StorageObserver
from justpipe.observability import ObserverMeta
from justpipe.storage import SQLiteStorage

storage = SQLiteStorage("~/.justpipe")

# Load stored initial state
replay = ReplayObserver(storage, source_run_id="abc123...")
await replay.on_pipeline_start({}, {}, ObserverMeta(pipe_name="Replay"))
initial_state = replay.get_initial_state()

# Run with replayed state
async for event in pipe.run(initial_state):
    pass
```

See [Phase 3 Demo](../../examples/12_observability/phase3_demo.py) for full example.

## Future Commands

Planned for Phase 4 (Polish):
- `justpipe cleanup [--older-than N]` - Clean up old runs
- `justpipe stats` - Overall statistics
- `justpipe watch` - Real-time monitoring
- `justpipe dashboard` - Interactive web dashboard

## See Also

- [Observability PRD](../../docs/observability-prd.md) - Full product requirements
- [Phase 2 Implementation](../../docs/PHASE2_IMPLEMENTATION.md) - Implementation details
- [Storage Interface](../storage/interface.py) - Storage backend API
- [Examples](../../examples/12_observability/) - Usage examples

## Contributing

To add a new CLI command:

1. Create command file: `justpipe/cli/commands/mycommand.py`
2. Implement async function: `async def mycommand_function(...)`
3. Register in `main.py`:
   - Add Click command decorator and function
4. Add tests: `tests/unit/test_cli_mycommand.py`
5. Update this README

## License

MIT License - See [LICENSE](../../LICENSE) for details
