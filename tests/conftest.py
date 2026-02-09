import pytest
from typing import Any


class MyState:
    def __init__(self) -> None:
        self.val = 0
        self.ok = False
        self.data: list[Any] = []


class MyContext:
    def __init__(self) -> None:
        self.val = 10


@pytest.fixture
def state() -> MyState:
    return MyState()


@pytest.fixture
def context() -> MyContext:
    return MyContext()
