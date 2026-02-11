# [11 Visualization](../README.md#getting-started)

This example demonstrates how `justpipe` can automatically generate Mermaid diagrams of your pipelines.

## Key Concepts

1.  **Automatic Discovery**: `justpipe` tracks the `to` targets of every step to build a directed graph.
2.  **`pipe.graph()`**: This method returns a string containing the Mermaid.js code for the pipeline.
3.  **No Execution Required**: You can generate the graph immediately after defining the pipe, without needing to run it.
4.  **Complex Topologies**: The visualization handles parallel branches, joins, and even mentions of sub-pipelines (though sub-pipelines are currently visualized as single nodes in the parent graph).

## How to Run

```bash
uv run python examples/11_visualization/main.py
```

## How to View

You can copy the generated Mermaid code into the [Mermaid Live Editor](https://mermaid.live/) or use a VS Code extension that supports Mermaid.

## Pipeline Graph

```mermaid
graph TD
    Start(["▶ Start"])

    subgraph parallel_n0[Parallel]
        direction LR
        n3["Process A"]
        n4["Process B"]
    end

    n0["Input"]
    n1["Join"]
    n2["Output"]
    n5[/"Sub Flow" /]
    End(["■ End"])
    n2 --> End

    Start --> n0
    n0 --> n3
    n0 --> n4
    n1 --> n2
    n3 --> n1
    n4 --> n5
    n5 --> n1
    class n0,n1,n2,n3,n4 step;
    class n5 sub;
    class Start,End startEnd;

    subgraph cluster_n5 ["Sub Flow (Impl)"]
        direction TB
        n5_Start(["▶ Start"])

        n5_n0["Sub Step 1"]
        n5_n1["Sub Step 2"]
        n5_End(["■ End"])
        n5_n1 --> n5_End

        n5_Start --> n5_n0
        n5_n0 --> n5_n1
    class n5_n0,n5_n1 step;
    class n5_Start,n5_End startEnd;
    end
    n5 -.- n5_Start

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

## See Also

- **[examples/README.md](../README.md#visual-guide)**: Full guide to the colors and shapes used in these graphs.
- **[06 Sub-pipelines](../06_subpipelines)**: Visualizing nested flows.
