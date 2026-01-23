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
class StepConfig:
    """Unified configuration for a pipeline step."""

    name: str
    func: Optional[Callable[..., Any]] = None
    timeout: Optional[float] = None
    retries: Union[int, Dict[str, Any]] = 0
    barrier_timeout: Optional[float] = None
    on_error: Optional[Callable[..., Any]] = None
    
    # Routing
    map_target: Optional[str] = None
    switch_routes: Union[Dict[Any, str], str, None] = None
    switch_default: Optional[str] = None
    
    # Sub-pipeline
    sub_pipeline: Optional[str] = None
    sub_pipeline_obj: Any = None  # Typed as Any to avoid circular imports

    extra: Dict[str, Any] = field(default_factory=dict)

    def get_kind(self) -> str:
        """Determine the kind of step based on configuration."""
        if self.map_target:
            return "map"
        if self.switch_routes:
            return "switch"
        if self.sub_pipeline:
            return "sub"
        return "step"

    def get_targets(self) -> List[str]:
        """Return all downstream targets configured in this step."""
        targets: List[str] = []
        
        if self.map_target:
            targets.append(self.map_target)
            
        if self.switch_routes and isinstance(self.switch_routes, dict):
            targets.extend(t for t in self.switch_routes.values() if t != "Stop")
            
        if self.switch_default:
            targets.append(self.switch_default)
            
        return targets


@dataclass
class StepContext:
    """Context passed to middleware containing step metadata."""

    name: str
    kwargs: Dict[str, Any]
    pipe_name: str
    config: Optional[StepConfig] = None


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

