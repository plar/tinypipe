# Fuzzing Testing

## Overview

Fuzzing (property-based testing) uses the `hypothesis` library to automatically generate random inputs and discover edge cases, race conditions, and unexpected behaviors that manual tests might miss.

**Total: 16 fuzzing tests** covering basic pipeline features (10 tests) and advanced features (6 tests).

## What is Tested

### Basic Pipeline Features (`test_fuzz_pipeline.py`)

### 1. State Handling (`test_fuzz_pipeline_with_random_state`)
- **Strategy**: Generates arbitrary nested data structures (lists, dicts, primitives)
- **Tests**: Pipeline handles any JSON-serializable state without crashing
- **Edge Cases Found**: None type, deeply nested structures, empty collections

### 2. Dataclass State (`test_fuzz_pipeline_with_dataclass_state`)
- **Strategy**: Generates random dataclass instances with varying field values
- **Tests**: Pipeline correctly passes dataclass state to steps
- **Coverage**: Random integers, nested values, edge values (0, negative, large)

### 3. Queue Size Configuration (`test_fuzz_queue_size_configuration`)
- **Strategy**: Tests queue sizes from 0 (unbounded) to 10,000
- **Tests**: Pipeline handles various queue configurations without deadlock
- **Edge Cases**: queue_size=0, very small (1-10), very large (5000-10000)

### 4. Map Concurrency (`test_fuzz_map_concurrency`)
- **Strategy**: Random max_concurrency (1-100 or None) and item counts (0-100)
- **Tests**: Throttling works correctly, all items processed, no lost items
- **Edge Cases Found**:
  - Empty item lists (0 items)
  - Single item
  - More items than concurrency limit
  - Unlimited concurrency (None)

### 5. Timeout Values (`test_fuzz_pipeline_timeout`)
- **Strategy**: Random timeout values (0.001-10.0 seconds or None)
- **Tests**: Pipelines handle various timeout configurations
- **Edge Cases**: Very small timeouts (may timeout), large timeouts, None (unlimited)

### 6. Cancellation Timing (`test_fuzz_cancellation_timing`)
- **Strategy**: Random cancellation delays (0-0.05s) and step counts (1-10)
- **Tests**: Cancellation at random pipeline execution points
- **What it finds**: Race conditions in cancellation handling

### 7. Combined Edge Cases (`test_fuzz_combined_edge_cases`)
- **Strategy**: Combines queue_size + max_concurrency + item_count
- **Tests**: Multiple features interact correctly
- **Complexity**: Tests combinations that might not be manually tested

### 8. Step Names (`test_fuzz_step_names`)
- **Strategy**: Random alphanumeric step names (1-50 chars)
- **Tests**: Pipeline handles various naming patterns
- **Edge Cases**: Long names, mixed case, numbers

### 9. Pipeline Depth (`test_fuzz_pipeline_depth`)
- **Strategy**: Random pipeline chain lengths (1-5 steps)
- **Tests**: Sequential step chains of varying lengths
- **Coverage**: Short pipelines, medium, long chains

### 10. Error Handling (`test_fuzz_error_handling`)
- **Strategy**: Randomly raises or doesn't raise errors
- **Tests**: Pipeline gracefully handles errors when they occur
- **Coverage**: Error events emitted, pipeline stops, no corruption

## Benefits of Fuzzing

1. **Discovers Edge Cases**: Finds combinations not considered in manual tests
2. **Regression Prevention**: Automatically tests many scenarios (50-200 examples each)
3. **Minimal Maintenance**: Once written, adapts to code changes
4. **High Coverage**: Tests orders of magnitude more cases than manual tests
5. **Race Condition Detection**: Random timing helps expose concurrency issues

## Running Fuzzing Tests

```bash
# Run all fuzzing tests
uv run pytest tests/fuzzing/ -v

# Run with more examples (slower, more thorough)
uv run pytest tests/fuzzing/ -v --hypothesis-profile=thorough

# Run specific fuzzing test
uv run pytest tests/fuzzing/test_fuzz_pipeline.py::test_fuzz_map_concurrency -v

# Show hypothesis statistics
uv run pytest tests/fuzzing/ -v --hypothesis-show-statistics
```

## Configuration

Fuzzing tests use these hypothesis settings:

- **max_examples**: 10-50 per test (balance speed vs coverage)
- **deadline**: 1000-5000ms per example (prevents indefinite hangs)
- **suppress_health_check**: Used for async fixtures when needed

## Interpreting Results

When a fuzzing test fails:

1. **Falsifying Example**: Hypothesis shows the exact input that caused failure
2. **Shrinking**: Hypothesis automatically simplifies the failing input
3. **Reproducible**: Same seed produces same failure
4. **Minimal**: Failure example is minimal (easiest to debug)

Example output:
```
Falsifying example: test_fuzz_map_concurrency(
    max_concurrency=1,
    item_count=100,
)
```

This tells you exactly what inputs to use to reproduce the issue manually.

## Adding New Fuzzing Tests

To add a new fuzzing test:

```python
from hypothesis import given, strategies as st

@given(your_parameter=st.integers(min_value=0, max_value=100))
@settings(max_examples=50, deadline=2000)
@pytest.mark.asyncio
async def test_fuzz_your_feature(your_parameter: int):
    # Setup
    pipe = Pipe()

    # Configure with random parameter
    @pipe.step()
    async def step(state):
        # Your logic using your_parameter
        pass

    # Execute
    events = [e async for e in pipe.run(None)]

    # Assert invariants (things that should ALWAYS be true)
    assert some_invariant_holds
```

## Strategy Reference

Common hypothesis strategies used:

- `st.integers(min_value, max_value)` - Random integers
- `st.floats(min_value, max_value)` - Random floats
- `st.text()` - Random strings
- `st.booleans()` - True/False
- `st.none()` - None value
- `st.one_of(s1, s2, ...)` - Choose from strategies
- `st.lists(elements)` - Random lists
- `st.dictionaries(keys, values)` - Random dicts
- `st.builds(Class, arg1=st1, arg2=st2)` - Random class instances

## Known Limitations

1. **Timing-dependent tests**: Some tests are timing-sensitive (cancellation)
2. **Long execution time**: Fuzzing 500+ examples can take minutes
3. **Non-deterministic**: May occasionally fail due to timing (rare)
4. **Resource usage**: Tests with high concurrency may use significant CPU/memory

## Advanced Fuzzing Tests (`test_fuzz_advanced.py`)

### 11. Switch Routing (`test_fuzz_switch_routing`)
- **Strategy**: Random route selection from predefined routes
- **Tests**: Switch correctly routes to appropriate steps
- **Coverage**: Multiple routing paths, route validation

### 12. Retry Logic (`test_fuzz_retry_logic`)
- **Strategy**: Random retry counts (0-3) and failure patterns (0-2 failures)
- **Tests**: Retries work correctly with various failure scenarios
- **Coverage**: No retries, successful after retries, exhausted retries

### 13. Barrier with Workers (`test_fuzz_barrier_with_workers`)
- **Strategy**: Random worker counts (1-5)
- **Tests**: Barriers correctly wait for all workers to complete
- **Coverage**: Single worker, multiple workers, barrier timeout

### 14. Sub-Pipeline Nesting (`test_fuzz_sub_pipeline_nesting`)
- **Strategy**: Random nesting depth (1-3 levels)
- **Tests**: Nested sub-pipelines execute in correct order
- **Coverage**: Single level, multiple nesting levels, recursive execution

### 15. Multiple Sub-Pipelines (`test_fuzz_multiple_sub_pipelines`)
- **Strategy**: Random number of parallel sub-pipelines (1-3)
- **Tests**: Multiple sub-pipelines can run concurrently
- **Coverage**: Single sub-pipeline, multiple parallel sub-pipelines

### 16. Barrier Combinations (`test_fuzz_barrier_combinations`)
- **Strategy**: Random barrier usage + worker counts
- **Tests**: Barriers work correctly in different configurations
- **Coverage**: With/without barriers, various worker counts
