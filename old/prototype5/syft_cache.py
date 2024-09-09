"""
Welcome to the SyftBox User Server: The Magical User Registry with Unbreakable Seals! 🧙‍♂️📜🔐

Toy Box Story:
Imagine a magical scroll that keeps track of all the toy owners in the kingdom.
Each owner must provide a unique magical seal (public key) when they register.
Once registered, their seal can never be changed!

Reality:
This is a Flask server that maintains a list of users with their associated public keys.
It allows adding new users with their public keys and retrieving the list of all users.
"""

import logging

from flask import Flask, jsonify, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Our magical scroll of users and their unbreakable seals
users: dict[str, str] = {}


@app.route("/users", methods=["GET", "POST"])
def manage_users():
    if request.method == "GET":
        # Reading the magical scroll
        logger.info("Someone's peeking at our user scroll!")
        return jsonify(list(users.keys()))
    elif request.method == "POST":
        # Adding a new name and seal to the scroll
        new_user = request.json.get("username")
        public_key = request.json.get("public_key")
        if new_user and public_key and new_user not in users:
            users[new_user] = public_key
            logger.info(f"A new toy owner joined our kingdom: {new_user}")
            return jsonify(
                {
                    "message": f"User {new_user} added successfully with their magical seal"
                }
            ), 201
        else:
            return jsonify(
                {
                    "message": "Invalid username, missing public key, or user already exists"
                }
            ), 400


@app.route("/users/<username>", methods=["GET"])
def get_user_public_key(username):
    if username in users:
        return jsonify({"username": username, "public_key": users[username]})
    else:
        return jsonify({"message": "User not found"}), 404


@app.route("/users/<username>/public_key", methods=["PUT"])
def update_public_key(username):
    return jsonify({"message": "Magical seals cannot be changed once set!"}), 403


if __name__ == "__main__":
    app.run(debug=False, port=8082)

"""
Congratulations! You've set up the magical user registry with unbreakable seals. 🎉

This server will keep track of all the toy owners (users) in our SyftBox kingdom,
along with their unique magical seals (public keys). Once a seal is set, it can never be changed!

Next, let's create a client plugin that will use this magical scroll to create
toy boxes (folders) for each owner and manage their magical seals!
"""
