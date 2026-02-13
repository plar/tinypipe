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

## Configuration

### Storage Directory

Set the storage directory using an environment variable:

```bash
export JUSTPIPE_STORAGE_PATH=~/.justpipe
```

Default: `~/.justpipe`

Each pipeline is stored in its own subdirectory: `~/.justpipe/<pipeline_hash>/runs.db`.

## Commands

### pipelines

List all known pipelines.

**Usage**:
```bash
justpipe pipelines
```

**Output**:
```
Pipeline                       Hash               Runs  Last Run             Success Rate
document_processor             a1b2c3d4e5f67890      42  2026-01-15 12:00:00        95.2%
data_pipeline                  b2c3d4e5f6789012      15  2026-01-16 08:30:00       100.0%

2 pipeline(s) found
```

---

### list

List pipeline runs with optional filtering.

**Usage**:
```bash
justpipe list [OPTIONS]
```

**Options**:
- `--pipeline, -p NAME` - Filter by pipeline name
- `--status, -s STATUS` - Filter by status (success/failed/timeout/cancelled/client_closed)
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
justpipe list --pipeline my_pipeline --status failed --limit 20

# Show full run IDs (32 characters)
justpipe list --full
```

---

### show

Show detailed information about a specific run.

**Usage**:
```bash
justpipe show <run-id>
```

**Examples**:
```bash
justpipe show a1b2c3d4
```

**Output**:
```
Run: a1b2c3d4e5f6789012345678
============================================================
Pipeline: my_pipeline
Status: success
Started: 2026-02-02 14:30:00
Ended: 2026-02-02 14:30:02
Duration: 2.3s

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

User Meta:
  version: 1.0
  batch_size: 100
```

---

### timeline

Generate execution timeline visualization.

**Usage**:
```bash
justpipe timeline <run-id> [OPTIONS]
```

**Options**:
- `--format, -f FORMAT` - Output format: `ascii`, `html`, or `mermaid` (default: `ascii`)

**Examples**:
```bash
# ASCII timeline (terminal)
justpipe timeline a1b2c3d4

# HTML timeline (opens in browser)
justpipe timeline a1b2c3d4 --format html

# Mermaid diagram (for docs)
justpipe timeline a1b2c3d4 --format mermaid
```

---

### compare

Compare two pipeline runs to identify differences.

**Usage**:
```bash
justpipe compare <run-id-1> <run-id-2>
```

**Examples**:
```bash
justpipe compare a1b2 e5f6
```

---

### export

Export run data to JSON for external analysis.

**Usage**:
```bash
justpipe export <run-id> [OPTIONS]
```

**Options**:
- `--output, -o FILE` - Output file path (default: `run_<id>.json`)
- `--format, -f FORMAT` - Export format: `json` (default: `json`)

**Examples**:
```bash
justpipe export a1b2c3d4
justpipe export a1b2c3d4 --output /tmp/debug_run.json
```

---

### stats

Show pipeline statistics.

**Usage**:
```bash
justpipe stats [OPTIONS]
```

**Options**:
- `--pipeline, -p NAME` - Filter by pipeline name
- `--days NUMBER` - Number of days to include (default: 7)

**Examples**:
```bash
justpipe stats
justpipe stats --pipeline my_pipeline --days 30
```

---

### cleanup

Clean up old pipeline runs.

**Usage**:
```bash
justpipe cleanup [OPTIONS]
```

**Options**:
- `--older-than DAYS` - Delete runs older than N days
- `--status STATUS` - Only delete runs with this status (success/failed/timeout/cancelled/client_closed)
- `--keep NUMBER` - Keep at least N most recent runs (default: 10)
- `--dry-run` - Show what would be deleted without deleting

**Examples**:
```bash
# Preview cleanup
justpipe cleanup --older-than 30 --dry-run

# Delete old failed runs
justpipe cleanup --older-than 7 --status failed

# Keep only last 5 runs
justpipe cleanup --keep 5
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `JUSTPIPE_STORAGE_PATH` | Storage directory path | `~/.justpipe` |
| `JUSTPIPE_PERSIST` | Enable persistence (`true`/`false`) | `false` |

## Architecture

### Components

```
justpipe/cli/
├── __init__.py
├── main.py              # CLI entry point (Click-based)
├── registry.py          # PipelineRegistry — scans per-pipeline storage dirs
├── formatting.py        # Shared formatting helpers
├── commands/
│   ├── list.py          # List command
│   ├── show.py          # Show command
│   ├── stats.py         # Stats command
│   ├── timeline.py      # Timeline command
│   ├── compare.py       # Compare command
│   ├── export.py        # Export command
│   ├── cleanup.py       # Cleanup command
│   └── pipelines.py     # Pipelines command
└── README.md            # This file
```

### Data Flow

```
User Command
    ↓
CLI Parser (Click)
    ↓
Command Handler (sync)
    ↓
PipelineRegistry → SQLiteBackend(s)
    ↓
Formatted Output (Rich)
```

### Storage Structure

```
~/.justpipe/
  <pipeline_hash>/
    pipeline.json         # Pipeline descriptor (name, topology, etc.)
    runs.db               # SQLite database with runs + events
```

## Contributing

To add a new CLI command:

1. Create command file: `justpipe/cli/commands/mycommand.py`
2. Implement sync function: `def mycommand_command(registry: PipelineRegistry, ...)`
3. Register in `main.py`:
   - Add Click command decorator and function
   - Call `get_registry()` and delegate to command function
4. Add tests: `tests/unit/test_cli_mycommand.py`
5. Update this README
