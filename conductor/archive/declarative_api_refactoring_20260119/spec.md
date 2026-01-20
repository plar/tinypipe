# Feature PRD: Declarative API Refactoring

## 1. Problem Statement
The current `justpipe` API suffers from a "Split-Brain" personality.
- **Topology** is defined in decorators (`to="next"`).
- **Control Flow** is defined in function bodies (`return Next("other")`).
- **Consequence:** The static visualization (`pipe.graph()`) often lies about the actual runtime behavior. Refactoring is fragile (string literals), and unit testing requires mocking the framework.

## 2. Solution Philosophy
**"The Decorator is the Law."**
- **Strict Separation:** Steps perform work and return **Data**. Decorators define **Routing**.
- **One Step, One Job:** 
    - `@pipe.step`: Linear execution.
    - `@pipe.map`: Fan-out dispatch.
    - `@pipe.switch`: Conditional branching.
- **Refactoring Safety:** Support passing Python function references (objects) as targets, not just strings.

## 3. Detailed Specifications

### 3.1. `@pipe.map` (Declarative Fan-Out)
A specialized decorator for the Map-Reduce pattern.

**API Signature:**
```python
def map(
    self,
    name: str | Callable | None = None,
    using: str | Callable = None,  # Mandatory
    to: str | List[str] | Callable | None = None,
    **kwargs
)
```

**Behavior:**
1.  **Wraps User Logic:** The decorated function is expected to return an `Iterable` (e.g., `List[T]`).
2.  **Internal Transformation:** The wrapper automatically converts this `Iterable` into the internal `Map(items=..., target=using)` object.
3.  **Validation:** If the user function returns a non-iterable, raise a `ValueError` at runtime.
4.  **Metadata:** Registers `using` target in `_step_metadata` for accurate visualization (e.g., `FanOut -.-> Worker`).

**Example:**
```python
@pipe.map("fan_out", using=process_item, to="reducer")
async def fan_out(state):
    return state.items  # Returns Data, not Map object
```

### 3.2. `@pipe.switch` (Declarative Branching)
A specialized decorator for conditional execution.

**API Signature:**
```python
def switch(
    self,
    name: str | Callable | None = None,
    routes: Dict[Any, str | Callable] | Callable[[Any], str] = None, # Mandatory
    default: str | Callable | None = None, # Optional Fallback
    **kwargs
)
```

**Unified `routes` Argument:**
The `routes` parameter serves as the single source of truth for branching, supporting two modes:

#### Mode A: Static Dictionary (The "Switch Case")
Maps a return value (Data) to a Target (Step).
- **Keys:** Any hashable value (Enum, str, bool, int).
- **Values:** Step Name (`str`) OR Step Function Reference (`Callable`).

```python
@pipe.switch("check_status", 
    routes={
        Status.OK: process_success,       # Function Reference (Safe)
        Status.ERROR: "handle_error"      # String Name
    },
    default="unknown_status_handler"      # Fallback for unexpected values
)
async def check_status(state) -> Status:
    return Status.OK
```

#### Mode B: Dynamic Router (The "Selector")
A pure function that maps the result to a step name.
- **Input:** The return value of the step.
- **Output:** The name of the next step (`str`).

```python
def hash_router(user_id: int) -> str:
    return f"shard_{user_id % 3}"

@pipe.switch("shard", routes=hash_router)
async def shard(state) -> int:
    return state.user_id
```

**Runtime Validation:**
- If the step returns a value that is **not found** in the `routes` dictionary (Mode A):
  1. If `default` is provided, transition to the `default` step.
  2. If `default` is **None**, the framework **MUST** raise a `ValueError` immediately (Strict Mode).

### 3.3. Refactoring Support (Function References)
All `to=`, `using=`, and `routes=` arguments **MUST** support accepting a `Callable` (the function object of another step).
- **Resolution:** The framework must resolve `func.__name__` (or the registered alias) at definition time.
- **Benefit:** IDE renaming of a function automatically updates the pipeline topology.
- **Avoid:** Relying solely on string literals.

### 3.4. Early Exit (Short-Circuiting)
- **Problem:** Need a way to stop execution immediately (e.g., Auth failure).
- **Solution:** Introduce a `Stop` sentinel or explicit signal.
- **API:**
    - If a step returns `Stop` (imported from `justpipe`), the pipeline terminates gracefully.
    - Alternatively, allow `routes` to map to `Stop`? e.g. `{Status.BANNED: Stop}`.

### 3.5. Global Error Handling (`@pipe.on_error`)
Aligns with `on_startup` and `on_shutdown` for consistency.

**API Signature:**
```python
def on_error(self, exception_type: Type[Exception], **kwargs)
```

**Behavior:**
- Registers a handler step for the specified exception type (and subclasses).
- The handler receives the exception instance (via dependency injection, e.g., `error: ValueError`).
- **Return Value:** The handler must return a Control Flow decision:
    - `str` (Step Name): Redirect execution to this recovery step.
    - `Stop`: Terminate the pipeline gracefully.
    - `None` (default): Rethrow the exception (Crash).

**Default Contextual Handler:**
- The framework **MUST** provide a built-in default handler (if no user handler is defined) or simplify the creation of one.
- **Requirement:** When an unhandled exception occurs, the default behavior/message must include:
    - **What:** The Exception Type and Message.
    - **Where:** The Step Name where it occurred.
    - **Context:** A snapshot of the State (if serializable/printable) or relevant keys.
- **Example:**
  ```text
  [JustPipe Error] Step 'process_payment' failed with ValueError: 'Invalid Currency'.
  Context: State(user_id=123, cart_total=0.0)
  ```

## 4. Implementation Plan
1.  **Update `Pipe` Class:**
    - Add `map()` decorator method.
    - Add `switch()` decorator method.
    - Add `on_error()` decorator method.
    - Update `step()` to ensure `_resolve_name` handles Callables robustly.
2.  **Update `_PipelineRunner`:**
    - Modify `_handle_task_result` to detect "Switch" steps.
    - Implement the routing logic (Dict lookup vs Func call).
    - Implement the "Missing Case" exception and `default` fallback.
    - Implement `Stop` signal handling.
    - Implement `_handle_error` logic to look up registered `on_error` handlers before crashing.
    - **Implement default error logging** with rich context in `_report_error`.
3.  **Update Visualization:**
    - Ensure `generate_mermaid_graph` reads `map_target` and `switch_routes` from metadata.
    - Draw "Decision Diamonds" for Switches.
    - Draw dotted lines for Map targets.
    - Draw Error Handler nodes (optional, maybe disjoint subgraph).

## 5. Migration & Advanced Topics
- **Implicitly Deprecated:** Returning `Next(...)` or `Map(...)` objects manually.
- **Escape Hatch:** Keep `Next` and `Map` accessible for "Nuclear" options (advanced users doing things decorators can't handle), but hide from main docs.
- **Loops:** Ensure the runner can handle cycles (infinite recursion protection or "stack safe" execution) to support Agent loops.
