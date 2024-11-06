import os
import platform
import shutil
import sys
from dataclasses import asdict

import psutil

from syftbox.app.manager import list_app
from syftbox.lib import DEFAULT_CONFIG_PATH, ClientConfig


def debug_report() -> str:
    config_path = os.environ.get("SYFTBOX_CLIENT_CONFIG_PATH", DEFAULT_CONFIG_PATH)
    client_config = None
    apps = []
    try:
        client_config = ClientConfig.load(config_path)
        apps_dir, apps = list_app(client_config)
        client_config = asdict(client_config)
        del client_config["_server_client"]
    except Exception:
        pass

    syftbox_path = shutil.which("syftbox")

    return {
        "system": {
            "resources": {
                "cpus": psutil.cpu_count(logical=True),
                "architecture": platform.machine(),
                "ram": f"{psutil.virtual_memory().total / (1024**3):.2f} GB",
            },
            "operating_system": {
                "name": "macOS" if platform.system() == "Darwin" else platform.system(),
                "version": platform.release(),
            },
            "python": {
                "version": platform.python_version(),
                "binary_location": sys.executable,
            },
        },
        "syftbox": {
            "command": syftbox_path or "syftbox executable not found in PATH",
            "client_config_path": str(config_path),
            "client_config": client_config,
            "apps_dir": str(apps_dir),
            "apps": apps,
        },
        "syftbox_env": {key: value for key, value in os.environ.items() if key.startswith("SYFT")},
    }


def debug_report_yaml() -> str:
    import yaml

    return yaml.dump(debug_report(), default_flow_style=False, sort_keys=False)
