import pytest

class MyState:
    def __init__(self):
        self.val = 0
        self.ok = False
        self.data = []

class MyContext:
    def __init__(self):
        self.val = 10

@pytest.fixture
def state():
    return MyState()

@pytest.fixture
def context():
    return MyContext()
