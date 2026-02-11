#!/usr/bin/env python3
import re
import subprocess
import sys
from pathlib import Path


def run_tests() -> bool:
    """Run the examples execution tests to regenerate .mmd files."""
    print("Running examples execution tests to regenerate .mmd files...")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/functional/test_examples_execution.py"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("Error: Examples execution tests failed.")
        print(result.stdout)
        print(result.stderr)
        return False
    print("Tests passed successfully.")
    return True


def update_readmes() -> int:
    """Update README.md files in examples/ with content from pipeline.mmd."""
    root = Path(__file__).parent.parent
    examples_dir = root / "examples"

    updated_count = 0

    for example_path in examples_dir.iterdir():
        if not example_path.is_dir():
            continue

        mmd_file = example_path / "pipeline.mmd"
        readme_file = example_path / "README.md"

        if not mmd_file.exists():
            print(f"Skipping {example_path.name}: pipeline.mmd not found.")
            continue

        if not readme_file.exists():
            print(f"Skipping {example_path.name}: README.md not found.")
            continue

        print(f"Updating {readme_file}...")

        mmd_content = mmd_file.read_text().strip()
        readme_content = readme_file.read_text()

        # Regex to find the mermaid block
        # It looks for ```mermaid ... ```
        pattern = re.compile(r"```mermaid\n(.*?)\n```", re.DOTALL)

        if not pattern.search(readme_content):
            print(f"Warning: No mermaid block found in {readme_file}")
            continue

        new_readme_content = pattern.sub(
            f"```mermaid\n{mmd_content}\n```", readme_content
        )

        if new_readme_content != readme_content:
            readme_file.write_text(new_readme_content)
            print(f"Successfully updated {readme_file}")
            updated_count += 1
        else:
            print(f"No changes needed for {readme_file}")

    return updated_count


def main() -> None:
    if not run_tests():
        sys.exit(1)

    updated = update_readmes()
    print(f"\nDone! Updated {updated} README files.")


if __name__ == "__main__":
    main()
