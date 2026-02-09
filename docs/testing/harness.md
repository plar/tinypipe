# Testing Harness (`TestPipe`)

Writing unit tests for asynchronous, event-driven pipelines can be challenging. `justpipe` provides a specialized `TestPipe` harness designed to make testing predictable, isolated, and expressive.

## Key Concepts

- **`TestPipe`**: A wrapper for your pipeline that allows you to mock steps and hooks without permanently modifying the original `Pipe` object.
- **Mocking**: Replace side-effect-heavy steps (API calls, DB writes) with `AsyncMock`.
- **`TestResult`**: A container returned after a run that holds the final state and a full trace of all events.

## Basic Usage

The most common pattern is using the `TestPipe` as a context manager. This ensures that any mocks you create are automatically removed when the test finishes.

```python
import pytest
from justpipe import Pipe, TestPipe

# Your production pipeline
pipe = Pipe(state_type=UserState)

@pipe.step(to="notify_user")
async def fetch_user_data(state: UserState):
    state.processed = True

@pipe.step()
async def notify_user(state: UserState):
    # Imagine this sends a real email
    pass

@pytest.mark.asyncio
async def test_pipeline():
    # Use the harness
    with TestPipe(pipe) as tester:
        # 1. Mock the notification step
        mock_notify = tester.mock("notify_user")
        
        # 2. Run the pipeline
        result = await tester.run(UserState(user_id=42))
        
        # 3. Assertions
        mock_notify.assert_called_once()
        assert result.final_state.processed is True
        assert result.was_called("fetch_user_data")
```

## Mocking Lifecycle Hooks

You can mock startup hooks and error handlers to avoid real side effects like database connections during tests.

### Mocking Startup
`tester.mock_startup()` replaces all `@pipe.on_startup` hooks with a single mock.

```python
with TestPipe(pipe) as tester:
    # Prevent real DB connections or heavy setup
    mock_start = tester.mock_startup(return_value=None)
    
    await tester.run(initial_state)
    mock_start.assert_called_once()
```

### Mocking Error Handlers
`tester.mock_on_error()` replaces the global `@pipe.on_error` handler. This is useful for verifying that your pipeline correctly triggers error recovery or for forcing a terminal failure.

```python
from justpipe import Skip

with TestPipe(pipe) as tester:
    # Force the error handler to skip the failing branch
    tester.mock_on_error(return_value=Skip())
    
    # Simulate a failure in a step
    tester.mock("check_connection", side_effect=RuntimeError("Down!"))
    
    result = await tester.run(state)
    
    # Verify downstream was never reached because we skipped the branch
    assert not result.was_called("process_stream")
```

## Testing Streams (Tokens)

If your steps `yield` data tokens, you can access them directly from the result via the `tokens` property.

```python
@pipe.step()
async def process_stream(state):
    yield "token_1"
    yield "token_2"

# In your test:
result = await tester.run(state)
assert result.tokens == ["token_1", "token_2"]
```

## Inspecting Errors

If a step fails, you can easily retrieve the error message associated with that specific stage.

```python
with TestPipe(pipe) as tester:
    # Mock a terminal failure (handler raises exception)
    tester.mock_on_error(side_effect=ValueError("Terminal Failure"))
    tester.mock("check_connection", side_effect=RuntimeError("Original Error"))
    
    result = await tester.run(state)
    
    # Retrieve the specific error message for a step
    err_msg = result.find_error("check_connection")
    assert "Terminal Failure" in err_msg
```

## Advanced Assertions Reference

The `TestResult` object provides several helpers to verify the execution path:

| Method / Property | Description |
| :--- | :--- |
| `result.was_called(name)` | Returns `True` if the step/hook with that name executed. |
| `result.step_starts` | A list of step names in the order they were started. |
| `result.tokens` | A list of all data items yielded by steps (EventType.TOKEN). |
| `result.find_error(name)` | Returns the error message string if a specific step failed. |
| `result.final_state` | The state of the pipeline after execution finished. |
| `result.events` | The raw list of all `Event` objects emitted during the run. |

## Why use `TestPipe` instead of `unittest.mock.patch`?

1.  **Dependency Injection Aware**: `TestPipe` mocks are "wrapped" by the pipeline's invoker. They automatically receive the correct `state`, `ctx`, and other injected parameters based on their signature.
2.  **Middleware Integrity**: Mocks are still executed through the pipeline's middleware (like retries). This allows you to test if your **retry logic** works when a mock fails.
3.  **State Safety**: Manual mocking of `pipe.registry` can leak between tests if not restored perfectly. `TestPipe` handles this safely via its `restore()` method or context manager.
