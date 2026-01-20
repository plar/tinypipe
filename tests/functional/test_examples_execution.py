import subprocess
import sys
from pathlib import Path


def run_example(example_name: str) -> subprocess.CompletedProcess[str]:
    root = Path(__file__).parent.parent.parent
    example_script = root / "examples" / example_name / "main.py"

    result = subprocess.run(
        [sys.executable, str(example_script)], capture_output=True, text=True, cwd=root
    )
    return result


def test_example_01_quick_start() -> None:
    root = Path(__file__).parent.parent.parent
    result = run_example("01_quick_start")

    assert result.returncode == 0
    assert "Hello, World!" in result.stdout

    graph_file = root / "examples" / "01_quick_start" / "pipeline.mmd"
    assert graph_file.exists()


def test_example_02_parallel_dag() -> None:
    root = Path(__file__).parent.parent.parent
    result = run_example("02_parallel_dag")

    assert result.returncode == 0
    # The output should show results from both parallel branches
    assert "Result: 52" in result.stdout

    graph_file = root / "examples" / "02_parallel_dag" / "pipeline.mmd"
    assert graph_file.exists()


def test_example_03_dynamic_map() -> None:
    root = Path(__file__).parent.parent.parent
    result = run_example("03_dynamic_map")

    assert result.returncode == 0
    # We expect mock output since API key is likely missing in test env
    assert "Mock summary for:" in result.stdout
    assert "Summarized 3 articles" in result.stdout

    graph_file = root / "examples" / "03_dynamic_map" / "pipeline.mmd"
    assert graph_file.exists()


def test_example_04_dynamic_routing() -> None:
    root = Path(__file__).parent.parent.parent
    result = run_example("04_dynamic_routing")

    assert result.returncode == 0
    assert "Routing to: even_handler" in result.stdout
    assert "Final Value: 20" in result.stdout

    graph_file = root / "examples" / "04_dynamic_routing" / "pipeline.mmd"
    assert graph_file.exists()


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


def test_example_06_subpipelines() -> None:
    root = Path(__file__).parent.parent.parent
    result = run_example("06_subpipelines")

    assert result.returncode == 0
    assert "Researching topic: Quantum Computing" in result.stdout
    assert "Drafting content..." in result.stdout
    assert "Report compiled:" in result.stdout

    graph_file = root / "examples" / "06_subpipelines" / "pipeline.mmd"
    assert graph_file.exists()


def test_example_07_streaming() -> None:
    root = Path(__file__).parent.parent.parent
    result = run_example("07_streaming")

    assert result.returncode == 0
    assert "Received token:" in result.stdout
    assert "Full Response:" in result.stdout

    graph_file = root / "examples" / "07_streaming" / "pipeline.mmd"
    assert graph_file.exists()


def test_example_08_reliability_retry() -> None:
    root = Path(__file__).parent.parent.parent
    result = run_example("08_reliability_retry")

    assert result.returncode == 0
    assert "Attempt" in result.stdout
    assert "Successfully called flaky API" in result.stdout

    graph_file = root / "examples" / "08_reliability_retry" / "pipeline.mmd"
    assert graph_file.exists()


def test_example_09_middleware() -> None:
    root = Path(__file__).parent.parent.parent
    result = run_example("09_middleware")

    assert result.returncode == 0
    # Check if middleware printed timing information
    assert "Step 'greet' took" in result.stdout
    assert "Step 'respond' took" in result.stdout

    graph_file = root / "examples" / "09_middleware" / "pipeline.mmd"
    assert graph_file.exists()


def test_example_10_lifecycle_hooks() -> None:
    root = Path(__file__).parent.parent.parent
    result = run_example("10_lifecycle_hooks")

    assert result.returncode == 0
    assert "Connecting to mock database..." in result.stdout
    assert "Disconnecting from mock database..." in result.stdout
    assert "Data fetched from DB: some_value" in result.stdout

    graph_file = root / "examples" / "10_lifecycle_hooks" / "pipeline.mmd"
    assert graph_file.exists()


def test_example_11_visualization() -> None:
    root = Path(__file__).parent.parent.parent
    result = run_example("11_visualization")

    assert result.returncode == 0
    assert "Mermaid graph generated successfully" in result.stdout

    graph_file = root / "examples" / "11_visualization" / "pipeline.mmd"
    assert graph_file.exists()
    content = graph_file.read_text()
    assert "graph TD" in content
    assert "subgraph" in content or "-->" in content