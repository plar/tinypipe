# 01 Quick Start

This example demonstrates the most basic usage of `justpipe`.

## Key Concepts

1.  **State Definition**: Using a dataclass to hold the pipeline state.
2.  **Pipe Initialization**: Creating a `Pipe[StateT, ContextT]` instance.
3.  **Step Registration**: Using `@pipe.step` to define the execution flow.
4.  **Async Execution**: Running the pipeline with `pipe.run()`.
5.  **Event Handling**: Listening for `TOKEN` events from streaming steps.
6.  **Visualization**: Generating a Mermaid diagram of the graph.

## How to Run

From the project root:

```bash
uv run python examples/01_quick_start/main.py
```

## Expected Output

```text
Starting pipeline...
Received token: Hello, World!
Finished with status: success
Graph saved to .../pipeline.mmd
```

## Pipeline Graph

```mermaid
graph TD
    Start(["▶ Start"])

    n0["Greet"]
    n1(["Respond ⚡"])
    End(["■ End"])
    n1 --> End

    Start --> n0
    n0 --> n1
    class n0 step;
    class n1 streaming;
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
