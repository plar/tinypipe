# 03 Dynamic Map (News Summarizer)

This example demonstrates the `Map` feature, which allows you to spawn dynamic parallel tasks based on a list of items at runtime. It simulates (or performs) parallel summarization of news articles using the Google Gemini API.

## Key Concepts

1.  **`Map(items=[...], target="step_name")`**: Returning this object triggers the runner to execute "step_name" for each item in the list concurrently.
2.  **Item Injection**: The target step receives the item as an argument (based on payload mapping).
3.  **Barrier Synchronization**: Steps that follow the map target (like `compile_report`) will wait for ALL mapped tasks to complete.
4.  **Integration**: Uses `google-generativeai` if available and configured.

## How to Run

1.  (Optional) Set your Gemini API key:
    ```bash
    export GEMINI_API_KEY="your-key-here"
    ```
    *If not set, the example runs in "Mock Mode".*

2.  Run the example:
    ```bash
    uv run python examples/03_dynamic_map/main.py
    ```

## Expected Output (Mock Mode)

```text
Found 3 articles to process.
Processing: Python 3.13 released...
Processing: AI models are gettin...
Processing: The weather tomorrow...

--- Report ---
Summarized 3 articles:

- Mock summary for: Python 3.13 released with new features...
- Mock summary for: AI models are getting smaller and faster...
- Mock summary for: The weather tomorrow will be sunny with a chance of rain...
Finished with status: success
Graph saved to ...
```

## Pipeline Graph

```mermaid
graph TD
    subgraph startup[Startup Hooks]
        direction TB
        startup_0> Setup ]
    end
    startup --> Start
    Start(["▶ Start"])

    n0["Compile Report"]
    n1[["Fan Out"]]
    n2["Start"]
    n3@{ shape: procs, label: "Summarize" }
    End(["■ End"])
    n0 --> End
    n3 --> End
    subgraph shutdown[Shutdown Hooks]
        direction TB
        shutdown_0> Cleanup ]
    end
    End --> shutdown

    Start --> n2
    n1 --> n0
    n1 -. map .-> n3
    n2 --> n1
    class n0,n2,n3 step;
    class n1 map;
    class Start,End startEnd;

    %% Styling
    classDef default fill:#f8f9fa,stroke:#dee2e6,stroke-width:1px;
    classDef step fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#0d47a1;
    classDef streaming fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#e65100;
    classDef map fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20;
    classDef switch fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#4a148c;
    classDef sub fill:#f1f8e9,stroke:#558b2f,stroke-width:2px,color:#33691e;
    classDef isolated fill:#fce4ec,stroke:#c2185b,stroke-width:2px,stroke-dasharray: 5 5,color:#880e4f;
    classDef startEnd fill:#e8f5e9,stroke:#388e3c,stroke-width:3px,color:#1b5e20;
```
