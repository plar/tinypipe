# 08 Reliability & Retry

This example demonstrates how `justpipe` integrates with `tenacity` to provide automatic retry logic for flaky steps.

## Key Concepts

1.  **`retries` parameter**: You can specify the number of retries for any step in the `@pipe.step` decorator.
2.  **`retry_wait_min` / `retry_wait_max`**: Control the exponential backoff timing between retries.
3.  **Automatic Integration**: If `tenacity` is installed, `justpipe` uses it to wrap the step function.
4.  **Error Handling**: If all retries fail, an `ERROR` event is yielded.

## How to Run

Make sure you have `tenacity` installed (or install this project with `[retry]` or `[examples]` extras):

```bash
uv run python examples/08_reliability_retry/main.py
```

## Expected Output

```text
Running pipeline with automatic retries...
Attempt 1: Calling flaky API...
Attempt 1: FAILED (simulated)
Attempt 2: Calling flaky API...
Attempt 2: FAILED (simulated)
Attempt 3: Calling flaky API...
Attempt 3: SUCCESS!

Successfully called flaky API after 3 attempts.
```

## Pipeline Graph

```mermaid
graph TD
    Start(["▶ Start"])

    n0["Flaky Call"]
    End(["■ End"])
    n0 --> End

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
