# Middleware Guide

Middleware allows you to inject logic that wraps around every step execution in your pipeline. It is the primary way to implement cross-cutting concerns like logging, retries, timing, and security.

## How it Works

A middleware is a function that receives the original step function and a `StepContext`, and returns a new "wrapped" function.

### Middleware Signature

```python
from typing import Any, Callable
from justpipe.types import StepContext

def my_middleware(func: Callable[..., Any], ctx: StepContext) -> Callable[..., Any]:
    async def wrapped(**kwargs):
        # 1. Logic BEFORE the step
        print(f"Entering step: {ctx.name}")
        
        # 2. Execute the actual step
        result = await func(**kwargs)
        
        # 3. Logic AFTER the step
        print(f"Exiting step: {ctx.name}")
        return result
    
    return wrapped
```

## Registering Middleware

Add middleware to your pipeline using `pipe.add_middleware()`. Middleware are applied in the order they are added.

```python
from justpipe import Pipe

pipe = Pipe(State)
pipe.add_middleware(my_middleware)
```

## The StepContext

The `StepContext` object provides metadata about the step currently being wrapped:

| Property | Description |
| :--- | :--- |
| `ctx.name` | The registered name of the step. |
| `ctx.pipe_name` | The name of the pipeline (useful for correlation). |
| `ctx.kwargs` | All extra keyword arguments passed to the `@pipe.step` decorator. |
| `ctx.retries` | The retry configuration for this step. |

## Advanced: Handling Streaming Steps

If your pipeline includes streaming steps (using `yield`), your middleware must handle async generators.

```python
import inspect

def timing_middleware(func, ctx):
    if inspect.isasyncgenfunction(func):
        async def wrapped_gen(**kwargs):
            # Start timer
            async for item in func(**kwargs):
                yield item
            # End timer
        return wrapped_gen
    else:
        async def wrapped(**kwargs):
            # Simple async logic
            return await func(**kwargs)
        return wrapped
```

## Built-in Middleware

- **Retry Middleware**: If `tenacity` is installed and you use the `retries` parameter in `@pipe.step()`, justpipe automatically applies a retry middleware as the first layer.

For a full runnable example, see **[Example 09: Middleware](../../examples/09_middleware)**.
