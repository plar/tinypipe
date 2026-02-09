# Concurrency and State Management

This guide explains how to safely manage state in concurrent justpipe pipelines.

## Core Principle

**justpipe gives you complete freedom over state management.** The library provides the execution framework, but **you are responsible for concurrent safety** when using parallel patterns (`@pipe.map`, parallel branches).

**The library provides:**
- Async execution primitives
- No built-in state synchronization (by design)
- Freedom to choose your concurrency strategy

**You are responsible for:**
- Choosing safe state patterns (immutable, locked, separate fields)
- Using async primitives (`asyncio.Lock`, etc.) when needed
- Understanding when race conditions can occur

## State Mutability: Sequential vs Concurrent

**Can you modify state to collect information from steps?**

**Yes, BUT:**
- ✅ **Safe for sequential execution** - steps run one after another
- ❌ **Unsafe for concurrent execution** - multiple steps run simultaneously (map, parallel branches)

### Sequential Execution (Safe to Mutate)

```python
from dataclasses import dataclass

@dataclass
class State:
    results: list = field(default_factory=list)
    counter: int = 0

pipe = Pipe(State)

@pipe.step(to="step2")
async def step1(state: State):
    state.results.append("from step1")
    state.counter += 1
    # Safe: only one step runs at a time

@pipe.step()
async def step2(state: State):
    state.results.append("from step2")
    state.counter += 1
    print(state.results)  # ["from step1", "from step2"]
```

### Concurrent Execution (Requires Locking)

When using `@pipe.map()` or parallel execution patterns, multiple workers run simultaneously. Without locking, you get race conditions:

```python
from dataclasses import dataclass, field

# BAD: Mutable state WITHOUT locking
@dataclass
class State:
    counter: int = 0
    results: list = field(default_factory=list)

@pipe.map(each="worker")
async def create_workers(state: State):
    return range(10)  # 10 concurrent workers

@pipe.step()
async def worker(state: State, item: int):
    state.counter += 1  # RACE CONDITION!
    state.results.append(item)  # RACE CONDITION!
    # Multiple workers modify state simultaneously without coordination
    # Final counter might be < 10 (lost updates)
    # List might have missing/corrupted data
```

**Solution:** Add locking for concurrent access (see "Handling Mutable State" below)

## Recommended Patterns

### 1. Immutable Dataclasses (Recommended)

Use `frozen=True` to prevent attribute reassignment:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class State:
    user_id: int
    config: dict  # WARNING: dict is still mutable!

pipe = Pipe(State)

@pipe.step()
async def process(state: State):
    # This will raise FrozenInstanceError ✓
    # state.user_id = 123

    # But this works and is DANGEROUS for concurrent steps! ✗
    # state.config['key'] = 'value'  # Dict is still mutable!

    # Safe: only read from state
    user_data = await fetch_user_data(state.user_id)

    # ❌ WRONG: Returning data doesn't pass it anywhere!
    # return user_data  # Data is silently ignored (lost)
    # return "some_data"  # Treated as step name - error if step not found!

    # ✅ RIGHT: Store in external system or yield for streaming
    await save_to_database(user_data)  # External storage
    # OR: yield user_data  # Stream as TOKEN events
```

**Important:**
- `frozen=True` prevents **attribute reassignment** but doesn't prevent **mutation** of mutable objects
- For true immutability, use immutable collections (see "Deep Immutability" section below)
- **Return values control flow** (return step names, `Stop`, `Suspend`), they don't pass data
- **To pass data**: mutate state (if safe), use context, external storage, or `yield` for streaming

## Summary: Where to Store Data

| Pattern | Use Case | Concurrent-Safe? | Example |
|---------|----------|------------------|---------|
| **Immutable State** | Configuration, input parameters | ✅ Yes | `@dataclass(frozen=True)` with immutable collections |
| **Mutable State (Sequential)** | Collecting results in linear pipeline | ✅ Yes | `state.results.append(x)` in sequential steps |
| **Mutable State (Concurrent)** | Shared data across parallel workers | ❌ No (requires locking) | Must use `asyncio.Lock` |
| **Context with Locking** | Collecting results from concurrent steps | ✅ Yes | Separate from state, explicit locks |
| **Yield for streaming** | Stream data as TOKEN events | ✅ Yes | `yield data` - emits TOKEN events |
| **External storage** | Persistent results | ✅ Yes | Database, Redis, file system |

**Note:** Return values control flow (step names, `Stop`, `Suspend`), not data passing!

**Quick Answer:**
- **Sequential pipeline?** → Mutable state is fine, no locking needed
- **Concurrent steps (map/parallel)?** → Use Context with locking, or immutable state

### 2. Named Tuples

For simple state objects:

```python
from typing import NamedTuple

class State(NamedTuple):
    user_id: int
    config: dict
    count: int = 0

pipe = Pipe(State)

@pipe.step()
async def process_batch(state: State):
    # State is immutable - read configuration
    batch_size = state.count
    batch = await fetch_batch(state.user_id, batch_size)

    # Store results externally or yield for streaming
    await save_batch_results(batch)  # External storage
    # OR: yield batch  # Stream as TOKEN events
```

### 3. Pydantic Models

For data validation and immutability:

```python
from pydantic import BaseModel

class State(BaseModel):
    user_id: int
    api_key: str
    max_retries: int = 3

    class Config:
        frozen = True  # Immutable

pipe = Pipe(State)

@pipe.step()
async def fetch_data(state: State):
    # State provides validated, immutable configuration
    data = await api.fetch(
        user_id=state.user_id,
        api_key=state.api_key,
        retries=state.max_retries
    )

    # Store or stream the fetched data
    await cache.set(f"user:{state.user_id}", data)  # External storage
    # OR: yield data  # Stream as TOKEN events
```

## Handling Mutable State (Advanced)

If you absolutely need mutable state (e.g., large shared data structures), implement your own locking:

### Pattern 1: Explicit Locking

```python
import asyncio
from dataclasses import dataclass, field

@dataclass
class MutableState:
    """State with manual concurrency control."""
    counter: int = 0
    results: list = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def increment(self):
        """Thread-safe increment."""
        async with self._lock:
            self.counter += 1

    async def add_result(self, value: Any):
        """Thread-safe append."""
        async with self._lock:
            self.results.append(value)

pipe = Pipe(MutableState)

@pipe.map(each="worker", max_concurrency=10)
async def create_workers(state: MutableState):
    return range(100)

@pipe.step()
async def worker(state: MutableState, item: int):
    # Use locked methods
    await state.increment()
    await state.add_result(item * 2)
```

**Warning:** Manual locking reduces parallelism. Only use when necessary.

### Pattern 1b: Modifying Different Fields Concurrently

**Question:** What if concurrent steps modify different fields of the same state?

```python
import asyncio
from dataclasses import dataclass, field

@dataclass
class MutableState:
    """State with per-field locks for fine-grained concurrency."""
    field_a: int = 0
    field_b: int = 0
    _lock_a: asyncio.Lock = field(default_factory=asyncio.Lock)
    _lock_b: asyncio.Lock = field(default_factory=asyncio.Lock)

pipe = Pipe(MutableState)

@pipe.map(each="step_a")
async def spawn_a(state: MutableState):
    return range(10)

@pipe.step()
async def step_a(state: MutableState, item: int):
    async with state._lock_a:
        state.field_a += item  # Only locks field_a

@pipe.map(each="step_b")
async def spawn_b(state: MutableState):
    return range(10)

@pipe.step()
async def step_b(state: MutableState, item: int):
    async with state._lock_b:
        state.field_b += item  # Only locks field_b
```

**When is this safe?**
- ✅ Each field has its own dedicated lock
- ✅ Steps only modify their designated field
- ✅ No step reads field X while another writes to field X

**When is this UNSAFE (even with separate fields)?**
- ❌ **Without locks on each field** - race conditions can occur
- ❌ **Reading multiple fields together** - may see inconsistent state:
  ```python
  # UNSAFE: Reading both fields without coordination
  if state.field_a + state.field_b > 100:  # Race condition!
      ...
  ```
- ❌ **Object-level races** - Python objects aren't inherently thread-safe
- ❌ **Memory visibility** - changes may not be immediately visible to other tasks

**Better alternatives:**
1. **Split into separate contexts:**
   ```python
   @dataclass
   class Context:
       data_a: dict = field(default_factory=dict)
       data_b: dict = field(default_factory=dict)
       lock_a: asyncio.Lock = field(default_factory=asyncio.Lock)
       lock_b: asyncio.Lock = field(default_factory=asyncio.Lock)
   ```

2. **Use immutable state + mutable context:**
   ```python
   @dataclass(frozen=True)
   class State:
       config: dict  # Immutable configuration

   @dataclass
   class Context:
       results_a: list = field(default_factory=list)
       results_b: list = field(default_factory=list)
       lock: asyncio.Lock = field(default_factory=asyncio.Lock)
   ```

**Recommendation:** Per-field locking is complex and error-prone. Prefer immutable state or use Context with appropriate locking.

### Pattern 2: Context for Mutable Data

Keep mutable data in context, not state:

```python
from dataclasses import dataclass
import asyncio

@dataclass(frozen=True)  # State is immutable
class State:
    user_id: int

@dataclass
class Context:
    """Mutable context shared across pipeline."""
    cache: dict = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def get_cached(self, key: str):
        async with self._lock:
            return self.cache.get(key)

    async def set_cached(self, key: str, value: Any):
        async with self._lock:
            self.cache[key] = value

pipe = Pipe(State, Context)

@pipe.step()
async def fetch_data(state: State, context: Context):
    # Check cache (thread-safe)
    cached = await context.get_cached(f"user_{state.user_id}")
    if cached:
        return cached

    # Fetch and cache
    data = await fetch_from_api(state.user_id)
    await context.set_cached(f"user_{state.user_id}", data)
    return data
```

## Best Practices

### 1. Use Immutable Collections

```python
# Good
@dataclass(frozen=True)
class State:
    items: tuple  # Immutable
    results: frozenset  # Immutable

# Bad
@dataclass(frozen=True)
class State:
    items: list  # Mutable! frozenset prevents reassignment but list is still mutable
```

### 2. Deep Immutability

```python
from typing import Mapping

# Good - truly immutable
@dataclass(frozen=True)
class State:
    config: Mapping[str, Any]  # Use Mapping instead of dict
    items: tuple[int, ...]

# Create with immutable types
state = State(
    config=types.MappingProxyType({"key": "value"}),
    items=(1, 2, 3)
)
```

### 3. Read-Only State Access

```python
@pipe.step()
async def transform(state: State):
    # Don't modify state - only read from it
    # State remains unchanged throughout the pipeline
    result = process_data(state.user_id, state.config)

    # Store results externally or yield for streaming
    await db.save(result)  # External storage
    # OR: yield result  # Stream as TOKEN events
    # OR: return 'next_step'  # Flow control only
```

**Important:**
- Returning non-string objects (dict, list, etc.) → **silently ignored** (data lost)
- Returning strings → treated as step names for flow control (error if step not found)
- Return special objects: `Stop`, `Suspend`, `_Next('step_name')` for flow control
- State is passed by reference and shared across all steps
- **To pass data**: mutate state (if safe), use context, external storage, or `yield`

### 4. Limit max_concurrency for External Resources

```python
# Good: prevents overwhelming external APIs
@pipe.map(each="api_call", max_concurrency=5)
async def batch_process(state: State):
    return range(1000)

@pipe.step()
async def api_call(state: State, item: int):
    # Only 5 concurrent API calls despite 1000 items
    return await external_api.process(item)
```

## Testing Immutability

Test that your state is truly immutable:

```python
import pytest

def test_state_immutability():
    state = State(user_id=123, config={})

    # Should raise FrozenInstanceError
    with pytest.raises(Exception):
        state.user_id = 456

def test_concurrent_safety():
    """Test that concurrent access doesn't cause races."""
    state = State(counter=0)

    async def increment_many():
        tasks = [worker(state, i) for i in range(100)]
        results = await asyncio.gather(*tasks)
        # Verify no data corruption
        assert len(set(results)) == 100  # All unique

    asyncio.run(increment_many())
```

## Common Pitfalls

### 1. Frozen dataclass with mutable fields

```python
# WRONG - still has race conditions!
@dataclass(frozen=True)
class State:
    items: list  # List is mutable!

state = State(items=[1, 2, 3])
# state.items = [4, 5, 6]  # This fails (good)
state.items.append(4)  # This succeeds (bad!)
```

**Fix:** Use `tuple` instead of `list`.

### 2. Sharing locks incorrectly

```python
# WRONG - each state instance gets its own lock!
@dataclass
class State:
    counter: int = 0
    _lock: asyncio.Lock = asyncio.Lock()  # Class-level, all instances share

# RIGHT - each instance gets its own lock
@dataclass
class State:
    counter: int = 0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
```

### 3. Forgetting to await lock acquisition

```python
# WRONG
with state._lock:  # Missing await!
    state.counter += 1

# RIGHT
async with state._lock:
    state.counter += 1
```

## Summary

**justpipe gives you freedom - you choose your concurrency strategy:**

- **Simplest:** Use immutable state (frozen dataclasses, NamedTuples, Pydantic)
- **Sequential:** Mutable state is safe when steps run one-at-a-time
- **Concurrent + mutable:** Use `asyncio.Lock` for explicit synchronization
- **Best of both:** Immutable state + mutable context with locking
- **External storage:** Database, Redis, file system for results
- **Streaming:** Use `yield` to emit TOKEN events

**Key principles:**
- The library doesn't enforce any pattern - you decide
- You are responsible for concurrent safety using async primitives
- Test your assumptions about immutability and locking
- Use `max_concurrency` to limit parallelism
- Return values control flow, not data passing

For more patterns, see the [examples directory](../../examples/).
