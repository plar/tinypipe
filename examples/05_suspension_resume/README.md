# 05 Suspension & Resume (Human-in-the-Loop)

This example demonstrates how to use the `Suspend` object to pause pipeline execution, wait for external input, and then resume the flow. It implements the classic game "Yes, No, Black, White".

## Key Concepts

1.  **`Suspend`**: Returning `Suspend(reason="...")` causes the pipeline to stop immediately and yield a `SUSPEND` event.
2.  **State Persistence**: The `state` object preserves all changes made before the suspension.
3.  **Resumption**: You can resume execution by calling `pipe.run()` again with the SAME `state` object and specifying the `start` step where the logic should continue.
4.  **Interactive Loops**: Combining `Suspend` with external loops allows for complex "Human-in-the-Loop" workflows.

## How to Run

```bash
uv run python examples/05_suspension_resume/main.py
```

## Game Rules

You will be asked a series of questions. You must answer them, but you are **FORBIDDEN** from using the words:
*   Yes
*   No
*   Black
*   White

If you use any of these words, the game is over!

## Pipeline Graph

```mermaid
graph TD
    Start(["▶ Start"])

    n0["Ask Question"]
    n1{"Check Answer"}
    n2["Game Over"]
    End(["■ End"])
    n0 --> End
    n2 --> End

    Start --> n0
    Start --> n1
    Start --> n2
     n1 -- "Result.CORRECT" --> n0
     n1 -- "Result.FORBIDDEN" --> n2
    class n0,n2 step;
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