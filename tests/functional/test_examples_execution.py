import subprocess
import sys
from pathlib import Path
import pytest


def run_example(example_name: str) -> subprocess.CompletedProcess[str]:
    root = Path(__file__).parent.parent.parent
    example_script = root / "examples" / example_name / "main.py"

    result = subprocess.run(
        [sys.executable, str(example_script)],
        capture_output=True,
        text=True,
        cwd=root,
    )
    return result


@pytest.mark.slow
@pytest.mark.parametrize(
    "example_name,expected_output,graph_filename",
    [
        ("01_quick_start", ["Hello, World!"], "pipeline.mmd"),
        ("02_parallel_dag", ["Result: 52"], "pipeline.mmd"),
        (
            "06_subpipelines",
            [
                "Researching topic: Quantum Computing",
                "Drafting content...",
                "Report compiled:",
            ],
            "pipeline.mmd",
        ),
        (
            "08_reliability_retry",
            ["Attempt", "Successfully called flaky API"],
            "pipeline.mmd",
        ),
        (
            "12_observability",
            ["JUSTPIPE OBSERVABILITY DEMO", "Total Duration:"],
            "pipeline.mmd",
        ),
    ],
)
def test_standard_examples(
    example_name: str, expected_output: list[str], graph_filename: str
) -> None:
    root = Path(__file__).parent.parent.parent
    result = run_example(example_name)

    assert result.returncode == 0, (
        f"Example {example_name} failed with stderr: {result.stderr}"
    )

    for expected in expected_output:
        assert expected in result.stdout

    graph_file = root / "examples" / example_name / graph_filename
    assert graph_file.exists()


@pytest.mark.slow
def test_example_05_suspension_resume() -> None:
    root = Path(__file__).parent.parent.parent
    example_script = root / "examples" / "05_suspension_resume" / "main.py"

    # Simulate user input:
    # 1. "Maybe" (Safe)
    # 2. "Yes" (Forbidden - Game Over)
    process = subprocess.Popen(
        [sys.executable, str(example_script)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=root,
    )

    stdout, stderr = process.communicate(input="Maybe\nYes\n")

    assert process.returncode == 0
    assert "Game Over" in stdout
    assert "Forbidden word 'yes' used" in stdout
    assert "Maybe" in stdout

    graph_file = root / "examples" / "05_suspension_resume" / "pipeline.mmd"
    assert graph_file.exists()
