import main as main_module


def test_load_config_success():
    assert main_module.load_config() is True
    assert "redis" in main_module.config
