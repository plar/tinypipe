# [14 Testing Harness](../README.md#getting-started)

This example demonstrates how to use `TestPipe` to write clean, isolated unit tests for your pipelines.

## Features Shown

1.  **Step Mocking**: Replace expensive or side-effect-heavy steps (like sending emails or DB calls) with `AsyncMock`.
2.  **Signature Preservation**: Mocks automatically receive the correct dependency-injected arguments (`state`, `ctx`, etc.).
3.  **Event Inspection**: Easily verify the execution path using `result.step_starts`.
4.  **Automatic Restoration**: Using `with TestPipe(pipe)` ensures your original pipeline is restored even if the test fails.

## Running the Demo

```bash
uv run examples/14_testing_harness/main.py
```

## Example Snippet

```python
with TestPipe(pipe) as tester:
    # Mock a step
    mock_step = tester.mock("send_email", return_value="ok")
    
    # Run pipeline
    result = await tester.run(initial_state)
    
    # Assertions
    mock_step.assert_called_once()
    assert result.final_state.is_done
```

## See Also

- **[12 Observability](../12_observability)**: How  captures events under the hood.
- **[01 Quick Start](../01_quick_start)**: The pipeline we tested here.
