import os
from pathlib import Path


def get_api_key(env_var: str) -> str | None:
    """
    Retrieve an API key from environment variables.
    If not found, print a warning and return None.
    """
    key = os.getenv(env_var)
    if not key:
        print(
            f"Warning: {env_var} environment variable not set. Using mock/fallback mode."
        )
        return None
    return key


def save_graph(pipe, filename: str | Path) -> None:
    """
    Generate and save the Mermaid graph for the given pipe.
    """
    path = Path(filename)
    # Ensure directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        graph_code = pipe.graph()
        path.write_text(graph_code, encoding="utf-8")
        print(f"Graph saved to {path}")
    except Exception as e:
        print(f"Failed to save graph: {e}")
