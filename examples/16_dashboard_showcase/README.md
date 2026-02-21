# [16 Dashboard Showcase](../README.md#production-reliability)

A comprehensive example that exercises every dashboard feature through a cloud video rendering pipeline with three contrasting scenarios.

## Key Concepts

1.  **Full Node Coverage**: Uses all 5 node kinds — step, map, switch, sub-pipeline, and barrier.
2.  **Meta Protocol**: Demonstrates all three meta scopes (`step`, `run`, `pipeline`).
3.  **Persistence**: Writes runs to SQLite via `persist=True` for dashboard consumption.
4.  **Scenario Comparison**: Runs 3 scenarios (fast success, retry recovery, timeout failure) for side-by-side comparison.
5.  **Sub-pipelines**: Nests a GPU render farm pipeline inside the main video pipeline.
6.  **Barrier Types**: Uses both `ANY` (asset fetch race) and `ALL` (analysis merge, frame compositing) barriers.
7.  **Streaming Tokens**: Preview generation yields tokens for real-time replay.

## How to Run

```bash
uv run python examples/16_dashboard_showcase/main.py
```

Then launch the dashboard:

```bash
JUSTPIPE_STORAGE_PATH=/tmp/justpipe_showcase uv run justpipe dashboard
```

## Expected Output

```text
======================================================================
VIDEO RENDER PIPELINE - Dashboard Showcase
======================================================================

  Running: Quick Promo (Summer Promo 2026)
    -> SUCCESS in 0.xxs (run: ...)

  Running: Feature Film (The Last Algorithm)
    -> SUCCESS in 0.xxs (run: ...)

  Running: Deadline Crunch (Q4 Launch Trailer)
    -> TIMEOUT in 0.xxs (run: ...)

======================================================================
RESULTS
======================================================================

  [+] Quick Promo            success     ...
  [+] Feature Film           success     ...
  [x] Deadline Crunch        timeout     ...
```

## Pipeline Graph

```mermaid
graph TD
    subgraph startup[Startup Hooks]
        direction TB
        startup_0> Warmup Gpu Pool ]
    end
    startup --> Start
    Start(["▶ Start"])

    subgraph parallel_n14[Parallel]
        direction LR
        n5["Fetch Cdn"]
        n6["Fetch Origin"]
    end

    n0["Accept Job"]
    n1@{ shape: procs, label: "Analyze Scene" }
    n2["Composite Frames"]
    n3["Deliver"]
    n4[["Extract Scenes"]]
    n7(["Generate Preview ⚡"])
    n8["Hi Quality"]
    n9["Lo Quality"]
    n10["Merge Analysis"]
    n11["Normalize Assets (Any)"]
    n12[/"Render Farm" /]
    n13{"Select Strategy"}
    n14["Validate Job"]
    End(["■ End"])
    n3 --> End
    subgraph shutdown[Shutdown Hooks]
        direction TB
        shutdown_0> Release Gpu Pool ]
    end
    End --> shutdown

    Start --> n0
    n0 --> n14
    n2 --> n7
    n4 -. map .-> n1
    n4 --> n10
    n5 --> n11
    n6 --> n11
    n7 --> n3
    n8 --> n12
    n9 --> n12
    n10 --> n13
    n11 --> n4
    n12 --> n2
     n13 -- "high" --> n8
     n13 -- "low" --> n9
    n14 --> n5
    n14 --> n6
    class n0,n1,n10,n11,n14,n2,n3,n5,n6,n8,n9 step;
    class n7 streaming;
    class n4 map;
    class n13 switch;
    class n12 sub;
    class Start,End startEnd;

    subgraph cluster_n12 ["Render Farm (Impl)"]
        direction TB
        n12_Start(["▶ Start"])

        n12_n0["Allocate Gpu"]
        n12_n1["Release Gpu"]
        n12_n2["Render Frames"]
        n12_End(["■ End"])
        n12_n1 --> n12_End

        n12_Start --> n12_n0
        n12_n0 --> n12_n2
        n12_n2 --> n12_n1
    class n12_n0,n12_n1,n12_n2 step;
    class n12_Start,n12_End startEnd;
    end
    n12 -.- n12_Start

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

- **[12 Observability](../12_observability)**: Foundational observability concepts used here.
- **[13 Barrier Types](../13_barrier_types)**: Deep dive into ANY vs ALL barriers.
- **[06 Sub-pipelines](../06_subpipelines)**: Sub-pipeline composition pattern.
