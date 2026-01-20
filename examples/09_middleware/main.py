import asyncio
import time
from pathlib import Path
from typing import Any, Callable
from justpipe import Pipe, EventType, StepContext
from examples.utils import save_graph

try:
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


# 1. Define custom middleware
def timing_middleware(
    func: Callable[..., Any], ctx: StepContext
) -> Callable[..., Any]:
    """Middleware that measures and logs execution time of a step."""
    import inspect

    def log_timing(duration: float) -> None:
        msg = f"Step '{ctx.name}' took {duration:.4f}s"
        if HAS_RICH:
            console.print(Panel(msg, title="Middleware Log", border_style="blue"))
        else:
            print(f"DEBUG: {msg}")

    # Handle async generators (streaming steps)
    if inspect.isasyncgenfunction(func):

        async def wrapped_gen(*args: Any, **kw: Any) -> Any:
            start_time = time.perf_counter()
            try:
                async for item in func(*args, **kw):
                    yield item
            finally:
                log_timing(time.perf_counter() - start_time)

        return wrapped_gen

    # Handle regular async functions
    async def wrapped(*args: Any, **kw: Any) -> Any:
        start_time = time.perf_counter()
        try:
            return await func(*args, **kw)
        finally:
            log_timing(time.perf_counter() - start_time)

    return wrapped


pipe = Pipe[None, None]()

# 2. Add the middleware to the pipeline
pipe.add_middleware(timing_middleware)


# Define respond first so we can reference it
@pipe.step()
async def respond():
    await asyncio.sleep(0.2)
    yield "Hello, Middleware!"


@pipe.step(to=respond)
async def greet():
    await asyncio.sleep(0.1)


async def main():
    if HAS_RICH:
        console.print(
            "[bold green]Running pipeline with Timing Middleware...[/bold green]"
        )
    else:
        print("Running pipeline with Timing Middleware...")

    async for event in pipe.run(None):
        if event.type == EventType.TOKEN:
            if HAS_RICH:
                console.print(f"[bold yellow]Token:[/bold yellow] {event.data}")
            else:
                print(f"Token: {event.data}")

    save_graph(pipe, Path(__file__).parent / "pipeline.mmd")


if __name__ == "__main__":
    asyncio.run(main())
