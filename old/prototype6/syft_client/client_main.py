from flask import Flask, jsonify, request, render_template
from flask_apscheduler import APScheduler
import os
import importlib
import time
import sys
import logging
import shutil
from shared_state import SharedState
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import sqlite3

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# Dictionary to store running plugins and their job IDs
running_plugins = {}

# Dictionary to store loaded plugins
loaded_plugins = {}

import json
import os

CONFIG_FILE = "syft_config.json"


def load_or_create_config():
    if os.path.exists(CONFIG_FILE) and not os.environ.get("SYFT_RECONFIGURE"):
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        return config

    config = {}
    config["syftbox_folder"] = get_user_input(
        "Enter the path for SyftBox folder", os.path.expanduser("~/Desktop/SyftBox")
    )
    config["syft_folder"] = get_user_input(
        "Enter the path for Syft folder", os.path.expanduser("~/.syft")
    )
    config["port"] = int(get_user_input("Enter the port to use", 8082))

    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

    return config


def get_user_input(prompt, default):
    user_input = input(f"{prompt} (default: {default}): ").strip()
    return user_input if user_input else default


def process_folder_input(user_input, default_path):
    if not user_input:
        return default_path
    if "/" not in user_input:
        # User only provided a folder name, use it with the default parent path
        parent_path = os.path.dirname(default_path)
        return os.path.join(parent_path, user_input)
    return os.path.expanduser(user_input)


def reinitialize_sync_db(syftbox_folder):
    db_path = os.path.join(syftbox_folder, ".sync_checkpoints.db")
    print("db_path", os.path.abspath(db_path))

    # Delete existing database if it exists
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
            logger.info(f"Deleted existing .sync_checkpoints.db at {db_path}")
        except Exception as e:
            logger.error(f"Failed to delete existing .sync_checkpoints.db: {str(e)}")
            return

    # Initialize new database
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS file_timestamps
                     (relative_path TEXT PRIMARY KEY, timestamp REAL)""")
        conn.commit()
        conn.close()
        logger.info(f"Initialized new .sync_checkpoints.db at {db_path}")
    except Exception as e:
        logger.error(f"Failed to initialize new .sync_checkpoints.db: {str(e)}")


def initialize_shared_state():
    config = load_or_create_config()

    shared_state = SharedState()
    shared_state.set("syftbox_folder", config["syftbox_folder"])
    shared_state.set("syft_folder", config["syft_folder"])

    logger.info(f"SyftBox folder set to: {config['syftbox_folder']}")
    logger.info(f"Syft folder set to: {config['syft_folder']}")

    # Reinitialize the sync database
    reinitialize_sync_db(config["syftbox_folder"])

    return shared_state, config["port"]


def run_plugin(plugin_name):
    try:
        logger.info(f"Running plugin: {plugin_name}")
        module = loaded_plugins[plugin_name]["module"]
        module.run(shared_state)
    except Exception as e:
        logger.exception(f"Error in plugin {plugin_name}: {str(e)}")


def load_plugins():
    plugins_dir = os.path.join(os.path.dirname(__file__), "plugins")
    sys.path.insert(0, os.path.dirname(plugins_dir))

    loaded_plugins = {}

    if os.path.exists(plugins_dir) and os.path.isdir(plugins_dir):
        for item in os.listdir(plugins_dir):
            if item.endswith(".py") and not item.startswith("__"):
                plugin_name = item[:-3]
                try:
                    module = importlib.import_module(f"plugins.{plugin_name}")
                    default_schedule = getattr(
                        module, "DEFAULT_SCHEDULE", 5000
                    )  # Default to 5000ms if not specified
                    description = getattr(
                        module, "DESCRIPTION", "No description available."
                    )
                    loaded_plugins[plugin_name] = {
                        "module": module,
                        "schedule": default_schedule,
                        "description": description,
                    }
                    logger.info(f"Plugin {plugin_name} loaded successfully")
                except Exception as e:
                    logger.exception(f"Failed to load plugin {plugin_name}: {str(e)}")

    return loaded_plugins


def start_plugin(plugin_name):
    if plugin_name not in loaded_plugins:
        return jsonify(error=f"Plugin {plugin_name} is not loaded"), 400

    if plugin_name in running_plugins:
        return jsonify(error=f"Plugin {plugin_name} is already running"), 400

    try:
        plugin_info = loaded_plugins[plugin_name]
        job = scheduler.add_job(
            func=run_plugin,
            trigger="interval",
            seconds=plugin_info["schedule"] / 1000,
            id=plugin_name,
            args=[plugin_name],
        )
        running_plugins[plugin_name] = {
            "job": job,
            "start_time": time.time(),
            "schedule": plugin_info["schedule"],
        }
        logger.info(
            f"Plugin {plugin_name} started with interval {plugin_info['schedule']}ms"
        )
        return jsonify(message=f"Plugin {plugin_name} started successfully"), 200
    except Exception as e:
        logger.exception(f"Failed to start plugin {plugin_name}")
        return jsonify(error=f"Failed to start plugin {plugin_name}: {str(e)}"), 500


def generate_key_pair():
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return private_pem, public_pem


def is_valid_datasite_name(name):
    return name.isalnum() or all(c.isalnum() or c in ("-", "_") for c in name)


@app.route("/plugins", methods=["GET"])
def list_plugins():
    plugins = []
    for plugin_name, plugin_info in loaded_plugins.items():
        plugins.append(
            {
                "name": plugin_name,
                "default_schedule": plugin_info["schedule"],
                "is_running": plugin_name in running_plugins,
                "description": plugin_info["description"],
            }
        )
    return jsonify(plugins=plugins)


@app.route("/launch", methods=["POST"])
def launch_plugin():
    plugin_name = request.json.get("plugin_name")
    if not plugin_name:
        return jsonify(error="Plugin name is required"), 400

    return start_plugin(plugin_name)


@app.route("/running", methods=["GET"])
def list_running_plugins():
    running = {}
    for name, data in running_plugins.items():
        job = data["job"]
        running[name] = {
            "is_running": job.next_run_time is not None,
            "run_time": time.time() - data["start_time"],
            "schedule": data["schedule"],
        }
    return jsonify(running_plugins=running)


@app.route("/kill", methods=["POST"])
def kill_plugin():
    plugin_name = request.json.get("plugin_name")
    if not plugin_name:
        return jsonify(error="Plugin name is required"), 400

    if plugin_name not in running_plugins:
        return jsonify(error=f"Plugin {plugin_name} is not running"), 400

    try:
        # Stop the scheduler job
        scheduler.remove_job(plugin_name)

        # Call the stop method if it exists
        plugin_module = loaded_plugins[plugin_name]["module"]
        if hasattr(plugin_module, "stop"):
            plugin_module.stop()

        # Remove the plugin from running_plugins
        del running_plugins[plugin_name]

        logger.info(f"Plugin {plugin_name} stopped successfully")
        return jsonify(message=f"Plugin {plugin_name} stopped successfully"), 200
    except Exception as e:
        logger.exception(f"Failed to stop plugin {plugin_name}")
        return jsonify(error=f"Failed to stop plugin {plugin_name}: {str(e)}"), 500


@app.route("/state", methods=["GET"])
def get_shared_state():
    return jsonify(shared_state.data)


@app.route("/state/update", methods=["POST"])
def update_shared_state():
    key = request.json.get("key")
    value = request.json.get("value")
    logger.info(f"Received request to update {key} with value: {value}")
    if key is not None:
        old_value = shared_state.get(key)
        shared_state.set(key, value)
        new_value = shared_state.get(key)
        logger.info(f"Updated {key}: old value '{old_value}', new value '{new_value}'")
        return jsonify(
            message=f"Updated key '{key}' from '{old_value}' to '{new_value}'"
        ), 200
    return jsonify(error="Invalid request"), 400


@app.route("/")
def plugin_manager():
    return render_template("index.html")


@app.route("/datasites", methods=["GET"])
def list_datasites():
    datasites = shared_state.get("my_datasites")
    return jsonify(datasites=datasites)


@app.route("/datasites", methods=["POST"])
def add_datasite():
    name = request.json.get("name")
    if not name:
        return jsonify(error="Datasite name is required"), 400

    if not is_valid_datasite_name(name):
        return jsonify(
            error="Invalid datasite name. Use only alphanumeric characters, hyphens, and underscores."
        ), 400

    syft_folder = shared_state.get("syft_folder")
    if not syft_folder:
        return jsonify(error="syft_folder is not set in shared state"), 500

    datasite_path = os.path.join(syft_folder, name)
    if os.path.exists(datasite_path):
        return jsonify(error=f"Datasite '{name}' already exists"), 409

    try:
        os.makedirs(datasite_path)
        private_key, public_key = generate_key_pair()

        with open(os.path.join(datasite_path, "private_key.pem"), "wb") as f:
            f.write(private_key)
        with open(os.path.join(datasite_path, "public_key.pem"), "wb") as f:
            f.write(public_key)

        return jsonify(message=f"Datasite '{name}' created successfully"), 201
    except Exception as e:
        logger.exception(f"Failed to create datasite {name}")
        return jsonify(error=f"Failed to create datasite: {str(e)}"), 500


@app.route("/datasites/<name>", methods=["DELETE"])
def remove_datasite(name):
    if not is_valid_datasite_name(name):
        return jsonify(error="Invalid datasite name"), 400

    syft_folder = shared_state.get("syft_folder")
    if not syft_folder:
        return jsonify(error="syft_folder is not set in shared state"), 500

    datasite_path = os.path.join(syft_folder, name)
    if not os.path.exists(datasite_path):
        return jsonify(error=f"Datasite '{name}' does not exist"), 404

    try:
        shutil.rmtree(datasite_path)
        return jsonify(message=f"Datasite '{name}' removed successfully"), 200
    except Exception as e:
        logger.exception(f"Failed to remove datasite {name}")
        return jsonify(error=f"Failed to remove datasite: {str(e)}"), 500


if __name__ == "__main__":
    shared_state, port = initialize_shared_state()
    loaded_plugins = load_plugins()  # Load all plugins at startup
    app.run(host="0.0.0.0", port=port, debug=True)
