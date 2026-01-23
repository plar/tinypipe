import inspect
import logging
import time
import warnings
from typing import Any, AsyncGenerator, Callable, Dict, Union

try:
    from tenacity import retry, stop_after_attempt, wait_exponential

    HAS_TENACITY = True
except ImportError:
    HAS_TENACITY = False

    def retry(  # type: ignore[no-redef]
        *args: Any, **kwargs: Any
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return lambda f: f

    def stop_after_attempt(*args: Any, **kwargs: Any) -> Any:  # type: ignore[no-redef]
        return None

    def wait_exponential(*args: Any, **kwargs: Any) -> Any:  # type: ignore[no-redef]
        return None


from justpipe.types import StepContext

Middleware = Callable[
    [Callable[..., Any], StepContext],
    Callable[..., Any],
]


def tenacity_retry_middleware(
    func: Callable[..., Any],
    ctx: StepContext,
) -> Callable[..., Any]:
    retries: Union[int, Dict[str, Any]] = 0
    if ctx.config:
        retries = ctx.config.retries
    else:
        retries = ctx.kwargs.get("retries", 0)

    if not retries:
        return func

    if not HAS_TENACITY:
        warnings.warn(
            f"Step '{ctx.name}' requested retries, but 'tenacity' not installed.",
            UserWarning,
        )
        return func

    if inspect.isasyncgenfunction(func):
        warnings.warn(
            f"Streaming step '{ctx.name}' cannot retry automatically.", UserWarning
        )
        return func

    if isinstance(retries, int):
        return retry(
            stop=stop_after_attempt(retries + 1),
            wait=wait_exponential(
                min=ctx.kwargs.get("retry_wait_min", 0.1),
                max=ctx.kwargs.get("retry_wait_max", 10),
            ),
            reraise=ctx.kwargs.get("retry_reraise", True),
        )(func)

    conf = retries.copy()
    conf.setdefault("reraise", True)
    return retry(**conf)(func)  # type: ignore[no-any-return]


def simple_logging_middleware(
    func: Callable[..., Any], ctx: StepContext
) -> Callable[..., Any]:
    """A simple middleware that logs step execution time using the standard logging module."""
    logger = logging.getLogger("justpipe")

    if inspect.isasyncgenfunction(func):

        async def wrapped_gen(**inner_kwargs: Any) -> AsyncGenerator[Any, None]:
            start = time.perf_counter()
            try:
                async for item in func(**inner_kwargs):
                    yield item
            finally:
                elapsed = time.perf_counter() - start
                logger.debug(f"Step '{ctx.name}' took {elapsed:.4f}s")

        return wrapped_gen
    else:

        async def wrapped_func(**inner_kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                return await func(**inner_kwargs)
            finally:
                elapsed = time.perf_counter() - start
                logger.debug(f"Step '{ctx.name}' took {elapsed:.4f}s")

        return wrapped_func
