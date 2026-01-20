# Specification: Exception Handling API (on_error)

## Overview
This track introduces a robust, user-defined exception handling mechanism for `justpipe`. It enables developers to define error handlers at both the global (pipeline) level and the granular (step) level. Handlers will receive full context about the failure and can return control primitives to dictate the pipeline's next move. Additionally, a rich default handler will ensure observability when no custom logic is provided.

## Functional Requirements

### 1. Hybrid Error Handling Definition
- **Step-Level:** Add an `on_error` parameter to `@pipe.step`, `@pipe.map`, and `@pipe.switch`.
  - Example: `@pipe.step(on_error=my_handler)`
- **Global-Level:** Add a `@pipe.on_error` decorator to define a catch-all handler for the pipeline.
- **Precedence:** Step-level handlers take precedence. If a step handler re-raises, it bubbles up to the global handler.

### 2. Default System Handler
- If NO user handlers are defined (or they propagate the error), a default system handler must activate.
- **Behavior:** It must log a structured error message containing:
  - Timestamp
  - Step Name
  - Error Type & Message
  - Stack Trace
  - Current State snapshot (optional/truncated)
- **Outcome:** It essentially performs a `Raise()`/`Stop()` action after logging, terminating the pipeline with an `ERROR` event.

### 3. Error Handler Signature
Handlers must accept arguments based on injection, supporting:
- `error` / `exception`: The raised Exception object.
- `state`: The current pipeline state.
- `context`: The pipeline context.
- `step_name`: The string name of the failing step.

### 4. Control Primitives (Return Values)
The runner must handle specific return values from error handlers:
- **`Retry()`**: Re-execute the failed step.
- **`Skip()`**: Mark step as finished with no output.
- **`Stop()`**: Gracefully terminate the pipeline.
- **`Raise()`** or raising an exception: Propagate the error.
- **`Next("step_name")`**: Redirect execution to a recovery step.
- **Raw Value**: Treated as the step's successful result (Substitution).

### 5. Integration with Runner
- Modify `_PipelineRunner` to catch exceptions in `_worker`.
- Invoke the appropriate handler chain (Step -> Global -> Default).
- Process the handler's return value.

## Non-Functional Requirements
- **Type Safety:** New primitives must be typed.
- **Async Support:** Handlers must support `async def`.
- **DX:** Clear distinction between "app logic error" and "pipeline crash".

## Out of Scope
- Complex back-off strategies for the `Retry` primitive (simple immediate retry only).
