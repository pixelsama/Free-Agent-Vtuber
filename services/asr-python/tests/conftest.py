import types

import pytest


@pytest.fixture
def dummy_funasr(monkeypatch):
    class DummyAutoModel:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def generate(self, input: str, device: str = "cpu"):
            return {"text": "你好，世界"}

    dummy_module = types.SimpleNamespace(AutoModel=DummyAutoModel)
    monkeypatch.setitem(__import__("sys").modules, "funasr", dummy_module)
    return DummyAutoModel
