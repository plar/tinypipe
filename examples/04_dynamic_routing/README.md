# 04 Dynamic Routing (Switch)

This example demonstrates how to use the `@pipe.switch` decorator to route execution based on the return value of a step.

## Key Concepts

1.  **Declarative Routing**: Use `@pipe.switch` to map return values to step names (or functions).
2.  **`routes` parameter**: A dictionary mapping values (e.g., `EVEN`/`ODD`, strings, bools, enums) to target steps.
3.  **Callable Routes**: You can also pass a function to `routes` for more complex logic (`routes=lambda x: ...`).
4.  **Branching**: Creating multiple paths in your graph that are only executed under certain conditions.

## How to Run

```bash
uv run python examples/04_dynamic_routing/main.py
```

## Expected Output

```text
--- Running with Even Value (10) ---
Checking value: 10
Routing to: even_handler
Final Value: 20
Message: Value was even, so we doubled it.

--- Running with Odd Value (7) ---
Checking value: 7
Routing to: odd_handler
Final Value: 8
Message: Value was odd, so we incremented it.
```

## Pipeline Graph

```mermaid
graph TD
    Start(["▶ Start"])

    n0["Even Handler"]
    n1{"Number Detector"}
    n2["Odd Handler"]
    n3["Start"]
    End(["■ End"])
    n0 --> End
    n2 --> End

    Start --> n3
     n1 -- "NumberType.EVEN" --> n0
     n1 -- "NumberType.ODD" --> n2
    n3 --> n1
    class n0,n2,n3 step;
    class n1 switch;
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