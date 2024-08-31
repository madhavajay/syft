from flask import Flask, request, jsonify, send_file, abort
from io import BytesIO

app = Flask(__name__)

# In-memory storage for user-specific outboxes
outbox_storage = {}

def get_user_outbox(user_id):
    return outbox_storage.setdefault(user_id, {})

def get_nested_item(storage, path_parts):
    for part in path_parts[:-1]:
        storage = storage.setdefault(part, {})
    return storage

# Endpoint to upload a file to a specific user's outbox
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files or 'target_user' not in request.form or 'filepath' not in request.form:
        return "File part, target_user, or filepath missing", 400
    
    file = request.files['file']
    target_user = request.form['target_user']
    filepath = request.form['filepath'].strip('/')
    
    if file.filename == '' or target_user == '' or filepath == '':
        return "No selected file, target_user, or filepath", 400
    
    path_parts = filepath.split('/')
    storage = get_nested_item(get_user_outbox(target_user), path_parts)
    storage[path_parts[-1]] = file.read()
    
    return jsonify({"target_user": target_user, "filepath": filepath, "size": len(storage[path_parts[-1]])}), 200

# Endpoint to list all files in a user's outbox
@app.route('/files/<user_id>', methods=['GET'])
def list_files(user_id):
    def list_directory(storage):
        files = {}
        for key, value in storage.items():
            if isinstance(value, dict):
                files[key] = list_directory(value)
            else:
                files[key] = len(value)
        return files
    
    user_outbox = get_user_outbox(user_id)
    return jsonify(list_directory(user_outbox))

# Endpoint to get the list of all known users
@app.route('/users', methods=['GET'])
def list_users():
    return jsonify(list(outbox_storage.keys()))

# Endpoint to download a file from a user's outbox
@app.route('/download/<user_id>/<path:filepath>', methods=['GET'])
def download_file(user_id, filepath):
    path_parts = filepath.split('/')
    storage = get_nested_item(get_user_outbox(user_id), path_parts)
    
    if path_parts[-1] in storage:
        return send_file(BytesIO(storage[path_parts[-1]]), download_name=path_parts[-1], as_attachment=True)
    else:
        abort(404, description="File not found")

# Endpoint to register a new user
@app.route('/register', methods=['POST'])
def register_user():
    if 'user_id' not in request.form:
        return "user_id missing", 400
    
    user_id = request.form['user_id']
    
    if user_id in outbox_storage:
        return jsonify({"message": f"User {user_id} already exists."}), 200
    else:
        outbox_storage[user_id] = {}
        return jsonify({"message": f"User {user_id} registered successfully."}), 201

        
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8082)
