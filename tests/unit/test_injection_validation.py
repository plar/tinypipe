import pytest
from typing import Any
from dataclasses import dataclass
from justpipe import Pipe, DefinitionError


@dataclass
class State:
    value: int = 0


def test_step_valid_injection() -> None:
    pipe: Pipe[State, None] = Pipe()

    @pipe.step()
    def valid_step(state: State) -> None:
        pass

    @pipe.step()
    def valid_step_alias(s: State) -> None:
        pass


def test_step_invalid_injection() -> None:
    pipe: Pipe[State, None] = Pipe()

    with pytest.raises(DefinitionError, match="unrecognized parameters"):
        # 2 unknown params should fail
        @pipe.step()
        def invalid_step(param1: Any, param2: Any) -> None:
            pass


def test_map_valid_injection() -> None:
    pipe: Pipe[State, None] = Pipe()

    @pipe.step()
    def processor(item: Any) -> None:
        pass

    @pipe.map(using=processor)
    def valid_map(state: State) -> list[int]:
        return [1, 2]

    @pipe.step()
    def item_processor(item: Any) -> None:
        pass

    # item_processor is valid as a map target because it has 1 unknown param
    @pipe.map(using=item_processor)
    def another_valid_map(state: State) -> list[int]:
        return [1, 2]


def test_map_invalid_injection() -> None:
    pipe: Pipe[State, None] = Pipe()

    @pipe.step()
    def processor(item: Any) -> None:
        pass

    with pytest.raises(DefinitionError, match="unrecognized parameters"):
        # Map step itself with 2 unknowns should fail
        @pipe.map(using=processor)
        def invalid_map(state: State, extra1: Any, extra2: Any) -> list[int]:
            return [1, 2]


def test_step_with_default_values() -> None:
    pipe: Pipe[State, None] = Pipe()

    # Defaults are skipped, so only 1 unknown (item) is allowed.
    # Here we have 0 unknowns because 'extra' has a default.
    @pipe.step()
    def step_with_defaults(state: State, extra: int = 10) -> None:
        pass

    # 1 unknown + 1 with default = OK
    @pipe.step()
    def step_with_one_unknown_and_default(item: Any, state: State, extra: int = 10) -> None:
        pass

    with pytest.raises(DefinitionError, match="unrecognized parameters"):
        # 2 unknowns + 1 with default = FAIL
        @pipe.step()
        def step_with_two_unknowns_and_default(a: Any, b: Any, state: State, extra: int = 10) -> None:
            pass