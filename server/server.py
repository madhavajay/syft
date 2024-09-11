import hashlib
import json
import os
import time

from flask import Flask, jsonify, request, send_file

app = Flask(__name__)

DATA_FOLDER = "server_data"
CHANGELOG_FOLDER = "server_changelog"

for folder in [DATA_FOLDER, CHANGELOG_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)


def get_file_hash(file_path):
    with open(file_path, "rb") as file:
        return hashlib.md5(file.read()).hexdigest()


@app.route("/push_changes", methods=["POST"])
def push_changes():
    changes = request.json["changes"]
    for change in changes:
        timestamp = time.time()
        change["timestamp"] = timestamp
        change_id = f"{timestamp}_{change['path'].replace('/', '_')}"
        change_file = os.path.join(CHANGELOG_FOLDER, change_id)
        with open(change_file, "w") as f:
            json.dump(change, f)

        file_path = os.path.join(DATA_FOLDER, change["path"])
        if change["type"] == "ADD" or change["type"] == "MODIFY":
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(change["content"].encode())
        elif change["type"] == "DELETE":
            if os.path.exists(file_path):
                os.remove(file_path)
                # Remove empty directories
                dir_path = os.path.dirname(file_path)
                while dir_path != DATA_FOLDER:
                    if not os.listdir(dir_path):
                        os.rmdir(dir_path)
                        dir_path = os.path.dirname(dir_path)
                    else:
                        break

    return jsonify({"status": "success"}), 200


@app.route("/get_full_changelog", methods=["GET"])
def get_full_changelog():
    changelog = []
    for filename in sorted(os.listdir(CHANGELOG_FOLDER)):
        print(filename)
        with open(os.path.join(CHANGELOG_FOLDER, filename), "r") as f:
            try:
                changelog.append(json.load(f))
            except Exception:
                print(f"Skipping file: {filename}")
    return jsonify(changelog)


@app.route("/get_file/<path:filename>", methods=["GET"])
def get_file(filename):
    file_path = os.path.join(DATA_FOLDER, filename)
    if os.path.exists(file_path):
        return send_file(file_path)
    else:
        return jsonify({"error": "File not found"}), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
