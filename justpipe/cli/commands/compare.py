"""Compare command for CLI."""

from justpipe.storage.interface import StorageBackend
from justpipe.observability.compare import compare_runs, format_comparison


async def compare_command(
    storage: StorageBackend,
    run1_id_prefix: str,
    run2_id_prefix: str,
) -> None:
    """Compare two pipeline runs.

    Args:
        storage: Storage backend
        run1_id_prefix: First run ID or prefix (baseline)
        run2_id_prefix: Second run ID or prefix (comparison)
    """
    try:
        # Resolve prefixes to full IDs
        run1_id = await storage.resolve_run_id(run1_id_prefix)
        if not run1_id:
            print(f"Error: Run not found: {run1_id_prefix}")
            return

        run2_id = await storage.resolve_run_id(run2_id_prefix)
        if not run2_id:
            print(f"Error: Run not found: {run2_id_prefix}")
            return

        comparison = await compare_runs(storage, run1_id, run2_id)
        output = format_comparison(comparison)
        print(output)

    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
