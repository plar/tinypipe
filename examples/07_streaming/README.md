# 07 Streaming (Chatbot)

This example demonstrates how to implement a streaming step that yields partial results (tokens) in real-time. This is essential for building responsive LLM applications.

## Key Concepts

1.  **Async Generators**: Steps defined as `async def` functions that `yield` values are treated as streaming steps.
2.  **`TOKEN` Events**: Each yielded value emits a `TOKEN` event.
3.  **Real-time Consumption**: The caller of `pipe.run()` can consume these tokens immediately as they are generated.
4.  **Integration**: Uses `openai` library if available and configured.

## How to Run

1.  (Optional) Set your OpenAI API key:
    ```bash
    export OPENAI_API_KEY="sk-..."
    ```
    *If not set, the example runs in "Mock Mode".*

2.  Run the example:
    ```bash
    uv run python examples/07_streaming/main.py
    ```

## Expected Output (Mock Mode)

```text
--- Streaming Chatbot ---
User asking: What is the meaning of life?
Generating response...
Received token: 'Thinking'
Received token: '...'
Received token: ' '
...
Full Response: Thinking... Life is complexity.
Finished with status: success
Graph saved to ...
```

## Pipeline Graph

```mermaid
graph TD
    subgraph startup[Startup Hooks]
        direction TB
        startup_0> Setup ]
    end
    startup --> Start
    Start(["▶ Start"])

    n0(["Respond ⚡"])
    n1["Start"]
    End(["■ End"])
    n0 --> End
    subgraph shutdown[Shutdown Hooks]
        direction TB
        shutdown_0> Cleanup ]
    end
    End --> shutdown

    Start --> n1
    n1 --> n0
    class n1 step;
    class n0 streaming;
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
