import os
import json
from flask import Flask, request, jsonify, send_file
import time
import hashlib

app = Flask(__name__)

DATA_FOLDER = 'server_data'
CHANGELOG_FOLDER = 'server_changelog'

for folder in [DATA_FOLDER, CHANGELOG_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

def get_file_hash(file_path):
    with open(file_path, 'rb') as file:
        return hashlib.md5(file.read()).hexdigest()

@app.route('/push_changes', methods=['POST'])
def push_changes():
    changes = request.json['changes']
    for change in changes:
        timestamp = time.time()
        change['timestamp'] = timestamp  # Add timestamp to the change object
        change_id = f"{timestamp}_{change['path']}"
        change_file = os.path.join(CHANGELOG_FOLDER, change_id)
        with open(change_file, 'w') as f:
            json.dump(change, f)

        if change['type'] == 'ADD' or change['type'] == 'MODIFY':
            file_path = os.path.join(DATA_FOLDER, change['path'])
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'wb') as f:
                f.write(change['content'].encode())
        elif change['type'] == 'DELETE':
            file_path = os.path.join(DATA_FOLDER, change['path'])
            if os.path.exists(file_path):
                os.remove(file_path)

    return jsonify({'status': 'success'}), 200

@app.route('/get_full_changelog', methods=['GET'])
def get_full_changelog():
    changelog = []
    for filename in sorted(os.listdir(CHANGELOG_FOLDER)):
        with open(os.path.join(CHANGELOG_FOLDER, filename), 'r') as f:
            changelog.append(json.load(f))
    return jsonify(changelog)

@app.route('/get_file/<path:filename>', methods=['GET'])
def get_file(filename):
    file_path = os.path.join(DATA_FOLDER, filename)
    if os.path.exists(file_path):
        return send_file(file_path)
    else:
        return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    app.run(debug=True)