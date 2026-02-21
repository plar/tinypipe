# [15 Real LLM Streaming](../README.md#ai--streaming)

This example demonstrates a production-style LLM streaming pipeline with automatic mock fallback when no API key is set.

## Key Concepts

1.  **Real API Integration**: Uses OpenAI's streaming API when `OPENAI_API_KEY` is set.
2.  **Mock Fallback**: Automatically falls back to a mock LLM when no key is present, making the example runnable anywhere.
3.  **Token Streaming**: The `call_llm` step is an async generator that `yield`s tokens as they arrive.
4.  **State Accumulation**: Tokens are collected in `state.tokens` and joined into `state.response`.
5.  **TestPipe Integration**: Includes an inline test showing how to mock the LLM step with `TestPipe`.

## How to Run

1.  (Optional) Set your OpenAI API key:
    ```bash
    export OPENAI_API_KEY="sk-..."
    ```
    *If not set, the example runs in mock mode.*

2.  Run the example:
    ```bash
    uv run python examples/15_real_llm_streaming/main.py
    ```

## Expected Output (Mock Mode)

```text
[Mock] Streaming response:

Python is a versatile, high-level programming language known for ...

--- Done (25 tokens) ---
Graph saved to .../pipeline.mmd

Test passed!
```

## Pipeline Graph

```mermaid
graph TD
    Start(["▶ Start"])

    n0["Build Prompt"]
    n1(["Call Llm ⚡"])
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

## See Also

- **[07 Streaming](../07_streaming)**: Basic streaming pattern with OpenAI.
- **[14 Testing Harness](../14_testing_harness)**: More `TestPipe` usage patterns.
