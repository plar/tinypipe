# 10 Lifecycle Hooks

This example demonstrates how to use lifecycle hooks (`on_startup` and `on_shutdown`) to manage resources like database connections.

## Key Concepts

1.  **Context**: The `Context` object is designed to hold persistent resources that are not part of the pipeline's functional state (e.g., DB connections, loggers, API clients).
2.  **`on_startup`**: This hook runs before any steps are executed. It's the ideal place to initialize resources.
3.  **`on_shutdown`**: This hook runs after the pipeline finishes (even if it failed with an error). It's the ideal place to clean up resources.
4.  **Resource Injection**: Steps can access the `Context` to use the initialized resources.

## How to Run

```bash
uv run python examples/10_lifecycle_hooks/main.py
```

## Expected Output

```text
Connecting to mock database...
Fetching data from DB...
Data fetched from DB: some_value
Disconnecting from mock database...
Pipeline finished.
```

## Pipeline Graph

```mermaid
graph TD
    subgraph startup[Startup Hooks]
        direction TB
        startup_0> Setup Db ]
    end
    startup --> Start
    Start(["▶ Start"])

    n0["Fetch"]
    End(["■ End"])
    n0 --> End
    subgraph shutdown[Shutdown Hooks]
        direction TB
        shutdown_0> Teardown Db ]
    end
    End --> shutdown

    Start --> n0
    class n0 step;
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
