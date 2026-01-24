from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional, Union, List
import time


class DefinitionError(Exception):
    """Raised when a pipeline or step is defined incorrectly."""

    pass


def _resolve_name(target: Union[str, Callable[..., Any]]) -> str:
    if isinstance(target, str):
        return target

    if hasattr(target, "func") and hasattr(target.func, "__name__"):
        return str(target.func.__name__)

    if hasattr(target, "__name__"):
        return str(target.__name__)

    if callable(target):
        return str(type(target).__name__)

    raise ValueError(f"Cannot resolve name for {target}")


class EventType(Enum):
    START = "start"
    TOKEN = "token"
    STEP_START = "step_start"
    STEP_END = "step_end"
    ERROR = "error"
    FINISH = "finish"
    SUSPEND = "suspend"


@dataclass
class Event:
    type: EventType
    stage: str
    data: Any = None
    timestamp: float = field(default_factory=time.time)


class _Stop:
    def __repr__(self) -> str:
        return "Stop"

    def __bool__(self) -> bool:
        return False


Stop = _Stop()


@dataclass
class _Next:
    target: Union[str, Callable[..., Any], None]
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def stage(self) -> Optional[str]:
        if self.target is None:
            return None
        return _resolve_name(self.target)


@dataclass
class _Map:
    items: List[Any]
    target: str


@dataclass
class _Run:
    pipe: Any  # Avoid circular import, typed as Any
    state: Any


@dataclass
class Suspend:
    reason: str


@dataclass
class Retry:
    """Primitive to signal the runner to retry the current step."""

    pass


@dataclass
class Skip:
    """Primitive to signal the runner to skip the current step and its children."""

    pass


@dataclass
class Raise:
    """Primitive to signal the runner to propagate the exception."""

    exception: Optional[Exception] = None


@dataclass
class StepContext:
    """Context passed to middleware containing step metadata."""

    name: str
    kwargs: Dict[str, Any]
    pipe_name: str
    retries: Union[int, Dict[str, Any]] = 0


@dataclass
class StepInfo:
    """Information about a registered step for introspection."""

    name: str
    timeout: Optional[float]
    retries: int
    barrier_timeout: Optional[float]
    has_error_handler: bool
    targets: List[str]
    kind: str  # "step", "map", or "switch"


@dataclass
class HookSpec:
    """Lifecycle hook with its injection metadata."""

    func: Callable[..., Any]
    injection_metadata: Dict[str, str]
