import pytest
from typing import List, Any


class MyState:
    def __init__(self) -> None:
        self.val = 0
        self.ok = False
        self.data: List[Any] = []


class MyContext:
    def __init__(self) -> None:
        self.val = 10


@pytest.fixture
def state() -> MyState:
    return MyState()


@pytest.fixture
def context() -> MyContext:
    return MyContext()
