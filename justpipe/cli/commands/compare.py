"""Compare command for CLI."""

from __future__ import annotations

from justpipe.cli.formatting import resolve_or_exit
from justpipe.cli.registry import PipelineRegistry
from justpipe.observability.compare import compare_runs, format_comparison


def compare_command(
    registry: PipelineRegistry,
    run1_id_prefix: str,
    run2_id_prefix: str,
) -> None:
    """Compare two pipeline runs."""
    result1 = resolve_or_exit(registry, run1_id_prefix)
    if result1 is None:
        return

    result2 = resolve_or_exit(registry, run2_id_prefix)
    if result2 is None:
        return

    annotated1, backend1 = result1
    annotated2, backend2 = result2

    events1 = backend1.get_events(annotated1.run.run_id)
    events2 = backend2.get_events(annotated2.run.run_id)

    comparison = compare_runs(
        annotated1.run,
        events1,
        annotated2.run,
        events2,
        pipeline1_name=annotated1.pipeline_name,
        pipeline2_name=annotated2.pipeline_name,
    )
    output = format_comparison(comparison)
    print(output)
