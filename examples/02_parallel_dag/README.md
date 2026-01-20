# 02 Parallel DAG (Static Fan-out/Fan-in)

This example demonstrates how to execute multiple steps in parallel and synchronize them using an implicit barrier.

## Key Concepts

1.  **Static Fan-out**: Defining multiple `to` targets in a step (`to=["step_a", "step_b"]`).
2.  **Implicit Barrier Synchronization**: A step that is targeted by multiple preceding steps (like `combine`) will wait for all of them to complete before executing.
3.  **Shared State**: Both parallel branches can safely modify the state (if using different fields) or read from it.

## How to Run

```bash
uv run python examples/02_parallel_dag/main.py
```

## Expected Output

```text
Starting parallel calculations for input: 10
Branch A finished: 20
Branch B finished: 32
Combined result: 52
>>> Result: 52
Graph saved to .../pipeline.mmd
```

## Pipeline Graph

```mermaid
graph TD
    Start(["▶ Start"])

    subgraph parallel_n3[Parallel]
        direction LR
        n0["Calc A"]
        n1["Calc B"]
    end

    n2(["Combine ⚡"])
    n3["Start"]
    End(["■ End"])
    n2 --> End

    Start --> n3
    n0 --> n2
    n1 --> n2
    n3 --> n0
    n3 --> n1
    class n0,n1,n3 step;
    class n2 streaming;
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
