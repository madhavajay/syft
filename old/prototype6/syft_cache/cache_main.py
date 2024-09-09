import os
import hashlib
import json
import time
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename
from typing import Dict, List

app = Flask(__name__)

CACHE_FOLDER = "cache_files"
CHANGELOG_FILE = "changelog.json"
os.makedirs(CACHE_FOLDER, exist_ok=True)

class ChangeLogEntry:
    def __init__(self, filename: str, hash: str, modified: float, operation: str):
        self.filename = filename
        self.hash = hash
        self.modified = modified
        self.operation = operation

    def to_dict(self):
        return {
            "filename": self.filename,
            "hash": self.hash,
            "modified": self.modified,
            "operation": self.operation
        }

changelog: List[ChangeLogEntry] = []

def load_changelog():
    global changelog
    if os.path.exists(CHANGELOG_FILE):
        with open(CHANGELOG_FILE, 'r') as f:
            changelog = [ChangeLogEntry(**entry) for entry in json.load(f)]
    else:
        # Initialize changelog with existing files
        for root, _, filenames in os.walk(CACHE_FOLDER):
            for filename in filenames:
                file_path = os.path.join(root, filename)
                rel_path = os.path.relpath(file_path, CACHE_FOLDER)
                with open(file_path, "rb") as f:
                    file_hash = hashlib.md5(f.read()).hexdigest()
                changelog.append(ChangeLogEntry(
                    filename=rel_path,
                    hash=file_hash,
                    modified=os.path.getmtime(file_path),
                    operation='create'
                ))
        save_changelog()

def save_changelog():
    with open(CHANGELOG_FILE, 'w') as f:
        json.dump([entry.to_dict() for entry in changelog], f)

# Make sure to call load_changelog() before starting the Flask app
load_changelog()

@app.route('/files', methods=['GET'])
def list_files():
    files = {}
    for root, _, filenames in os.walk(CACHE_FOLDER):
        for filename in filenames:
            file_path = os.path.join(root, filename)
            rel_path = os.path.relpath(file_path, CACHE_FOLDER)
            with open(file_path, "rb") as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
            files[rel_path] = {
                "filename": rel_path,
                "hash": file_hash,
                "modified": os.path.getmtime(file_path)
            }
    return jsonify(files)

@app.route('/changelog/<float:last_sync_time>', methods=['GET'])
def get_changelog(last_sync_time):
    return jsonify([entry.to_dict() for entry in changelog if entry.modified > last_sync_time])

# Add this new route to handle the case when last_sync_time is 0
@app.route('/changelog/0', methods=['GET'])
def get_full_changelog():
    return jsonify([entry.to_dict() for entry in changelog])

@app.route('/files/<path:file_path>', methods=['GET'])
def download_file(file_path):
    full_path = os.path.join(CACHE_FOLDER, file_path)
    if not os.path.exists(full_path):
        return "File not found", 404
    return send_file(full_path)

@app.route('/files/<path:file_path>', methods=['PUT'])
def upload_file(file_path):
    full_path = os.path.join(CACHE_FOLDER, file_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    file = request.files['file']
    file.save(full_path)
    
    with open(full_path, "rb") as f:
        file_hash = hashlib.md5(f.read()).hexdigest()
    
    modified_time = time.time()
    changelog.append(ChangeLogEntry(
        filename=file_path,
        hash=file_hash,
        modified=modified_time,
        operation='update' if os.path.exists(full_path) else 'create'
    ))
    save_changelog()
    
    return jsonify({"filename": file_path, "status": "uploaded"})

@app.route('/files/<path:file_path>', methods=['DELETE'])
def delete_file(file_path):
    full_path = os.path.join(CACHE_FOLDER, file_path)
    if not os.path.exists(full_path):
        return "File not found", 404
    os.remove(full_path)
    
    changelog.append(ChangeLogEntry(
        filename=file_path,
        hash="",
        modified=time.time(),
        operation='delete'
    ))
    save_changelog()
    
    return jsonify({"filename": file_path, "status": "deleted"})

if __name__ == '__main__':
    app.run(debug=True)