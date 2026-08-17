from src.server_settings import server_options


def test_server_options_defaults_to_local_development():
    assert server_options({}) == {
        "host": "127.0.0.1",
        "port": 8081,
        "title": "Adaptr",
        "show_welcome_message": False,
        "reload": False,
    }


def test_server_options_supports_docker_network_binding():
    assert server_options(
        {"NICEGUI_HOST": "0.0.0.0", "NICEGUI_PORT": "8081", "NICEGUI_RELOAD": "true"}
    )["host"] == "0.0.0.0"
