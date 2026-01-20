# 06 Sub-pipelines (Composition)

This example demonstrates how to compose pipelines by running one pipeline inside another. This allows you to build reusable, modular workflows.

## Key Concepts

1.  **`@pipe.sub(using=sub_pipe)`**: This decorator registers a step that executes a sub-pipeline.
2.  **State Adaptation**: The decorated function receives the parent's state and returns the state object to be passed to the sub-pipeline.
3.  **Shared State**: If both pipelines use the same state, the function can simply return the received state.
4.  **Event Namespacing**: Events from the sub-pipeline are automatically namespaced (e.g., `parent_step:child_step`).

## How to Run

```bash
uv run python examples/06_subpipelines/main.py
```

## Expected Output

```text
Starting Editor Pipeline...
-> Step started: assign_topic
[Editor] Assigned topic: Quantum Computing
-> Step started: delegate_research
[Editor] Delegating to Researcher pipeline...
-> Step started: delegate_research:gather_facts
  [Researcher] Researching topic: Quantum Computing
  [Researcher] Found 2 facts.
-> Step started: draft_report
[Editor] Drafting content...
[Editor] Report compiled: ... chars.

--- Final Output ---
Report on Quantum Computing:
- Fact 1 about Quantum Computing
- Fact 2 about Quantum Computing
```

## Pipeline Graph

```mermaid
graph TD
    Start(["▶ Start"])

    n0["Assign Topic"]
    n1[/"Delegate Research" /]
    n2["Draft Report"]
    End(["■ End"])
    n2 --> End

    Start --> n0
    n0 --> n1
    n1 --> n2
    class n0,n2 step;
    class n1 sub;
    class Start,End startEnd;

    subgraph cluster_n1 ["Delegate Research (Impl)"]
        direction TB
        n1_Start(["▶ Start"])

        n1_n0["Gather Facts"]
        n1_End(["■ End"])
        n1_n0 --> n1_End

        n1_Start --> n1_n0
    class n1_n0 step;
    class n1_Start,n1_End startEnd;
    end
    n1 -.- n1_Start

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
