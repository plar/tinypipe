from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional, Union, List


def _resolve_name(target: Union[str, Callable[..., Any]]) -> str:
    if isinstance(target, str):
        return target

    if hasattr(target, "__name__"):
        return target.__name__

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


@dataclass
class Next:
    target: Union[str, Callable[..., Any], None]
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def stage(self) -> Optional[str]:
        if self.target is None:
            return None
        return _resolve_name(self.target)


@dataclass
class Map:
    items: List[Any]
    target: str


@dataclass
class Run:
    pipe: Any  # Avoid circular import, typed as Any
    state: Any


@dataclass
class Suspend:
    reason: str
