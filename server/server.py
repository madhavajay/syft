import argparse
import hashlib
import json
import os
import time

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI()

DATA_FOLDER = "server_data"
CHANGELOG_FOLDER = "server_changelog"

for folder in [DATA_FOLDER, CHANGELOG_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)


def get_file_hash(file_path):
    with open(file_path, "rb") as file:
        return hashlib.md5(file.read()).hexdigest()


@app.post("/push_changes")
async def push_changes(request: Request):
    data = await request.json()
    changes = data["changes"]

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

    return JSONResponse({"status": "success"}, status_code=200)


@app.get("/get_full_changelog")
async def get_full_changelog():
    changelog = []
    for filename in sorted(os.listdir(CHANGELOG_FOLDER)):
        try:
            with open(os.path.join(CHANGELOG_FOLDER, filename), "r") as f:
                changelog.append(json.load(f))
        except Exception:
            print(f"Skipping file: {filename}")
    return JSONResponse(changelog)


@app.get("/get_file/{filename:path}")
async def get_file(filename: str):
    file_path = os.path.join(DATA_FOLDER, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    else:
        raise HTTPException(status_code=404, detail="File not found")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run FastAPI server")
    parser.add_argument(
        "--port",
        type=int,
        default=5001,
        help="Port to run the server on (default: 5001)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run the server in debug mode with hot reloading",
    )

    args = parser.parse_args()

    uvicorn.run(
        "server:app" if args.debug else app,  # Use import string in debug mode
        host="0.0.0.0",
        port=args.port,
        log_level="debug" if args.debug else "info",
        reload=args.debug,  # Enable hot reloading only in debug mode
    )
