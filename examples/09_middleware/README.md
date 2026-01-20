# 09 Middleware

This example demonstrates how to extend `justpipe` using custom middleware. Middleware wraps every step execution, allowing you to add cross-cutting concerns like logging, timing, tracing, or security checks.

## Key Concepts

1.  **Middleware Signature**: A middleware is a function that takes `(func, ctx: StepContext)` and returns a wrapped version of `func`. The `StepContext` provides:
    - `ctx.name`: The step name
    - `ctx.kwargs`: The decorator kwargs (e.g., `retries`, `timeout`)
    - `ctx.pipe_name`: The name of the pipe for correlation
2.  **`pipe.add_middleware(mw)`**: Registers a middleware for the entire pipeline.
3.  **Layered Execution**: Middleware are applied in order. The default `tenacity_retry_middleware` is applied first (if enabled), followed by your custom ones.
4.  **`rich` Integration**: This example uses the `rich` library for beautiful console output.

## How to Run

```bash
uv run python examples/09_middleware/main.py
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
