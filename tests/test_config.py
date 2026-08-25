from sentinel.config import get_default_config, load_config


def test_configuration_defaults_are_safe():
    config = load_config()
    default_config = get_default_config()

    assert config.environment == default_config["environment"]
    assert "HOSTLESS" not in str(default_config).upper()
    assert "PASSWORD" not in str(default_config).upper()
    assert config.docs_dir.name == "docs"


def test_runtime_paths_are_local():
    config = load_config()
    assert config.project_root.name == "stallion-sentinel"
    assert config.runtime_dir.name == ".runtime"
    assert config.runs_dir.name == "runs"
