# Barrier Types (Fan-In Control)

This example demonstrates how to control step execution behavior when multiple dependencies (parents) are involved.

## Concepts

### `BarrierType.ALL` (Default)
The standard "AND-Join". The step waits for **all** incoming connections to complete before running.
- **Use Case:** Aggregating results, ensuring all preconditions are met (e.g., "Wait for payment AND inventory check").

### `BarrierType.ANY` (OR-Join)
The "First-to-Finish" pattern. The step runs as soon as **any one** of the incoming connections completes.
- **Behavior:**
    - Triggers immediately on the first completion.
    - Subsequent completions from other parents are **ignored** for the current execution wave (they won't trigger the step again).
- **Use Case:**
    - **Racing:** Querying multiple redundant APIs/databases and taking the fastest response.
    - **Fast Path:** Proceeding with partial data if one source is much faster.
    - **Redundancy:** Implementing "Backup" logic where a second task runs in parallel but the main flow proceeds if the primary succeeds first.

## The Example Pipeline

1.  **Race (ANY):** `fetch_from_cache` and `fetch_from_db` run in parallel. `normalize_user_data` listens to both with `BarrierType.ANY`. It proceeds as soon as the fastest one finishes.
2.  **Aggregation (ALL):** `check_fraud` and `check_credit` run in parallel. `finalize_decision` waits for **both** (`BarrierType.ALL`) before making the final approval.

## Pipeline Graph

```mermaid
graph TD
    Start(["▶ Start"])

    subgraph parallel_n5[Parallel]
        direction LR
        n0["Check Credit"]
        n1["Check Fraud"]
    end

    subgraph parallel_n6[Parallel]
        direction LR
        n2["Fetch From Cache"]
        n3["Fetch From Db"]
    end

    n4["Finalize Decision"]
    n5["Normalize User Data (Any)"]
    n6["Start"]
    End(["■ End"])
    n4 --> End

    Start --> n6
    n0 --> n4
    n1 --> n4
    n2 --> n5
    n3 --> n5
    n5 --> n0
    n5 --> n1
    n6 --> n2
    n6 --> n3
    class n0,n1,n2,n3,n4,n5,n6 step;
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
