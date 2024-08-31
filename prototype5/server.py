"""
Welcome to the SyftBox User Server: The Magical User Registry! 🧙‍♂️📜

Toy Box Story:
Imagine a magical scroll that keeps track of all the toy owners in the kingdom.
Anyone can add a new owner's name to the scroll, and it never forgets a name!

Reality:
This is a simple Flask server that maintains a list of users. It allows adding new users
and retrieving the list of all users.
"""

import logging

from flask import Flask, jsonify, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Our magical scroll of users
users: set[str] = set()


@app.route("/users", methods=["GET", "POST"])
def manage_users():
    if request.method == "GET":
        # Reading the magical scroll
        logger.info("Someone's peeking at our user scroll!")
        return jsonify(list(users))
    elif request.method == "POST":
        # Adding a new name to the scroll
        new_user = request.json.get("username")
        if new_user and new_user not in users:
            users.add(new_user)
            logger.info(f"A new toy owner joined our kingdom: {new_user}")
            return jsonify({"message": f"User {new_user} added successfully"}), 201
        else:
            return jsonify({"message": "Invalid username or user already exists"}), 400


if __name__ == "__main__":
    app.run(debug=True, port=8082)

"""
Congratulations! You've set up the magical user registry. 🎉

This server will keep track of all the toy owners (users) in our SyftBox kingdom.
It's always ready to add new names or show the list of all known owners.

Next, let's create a client plugin that will use this magical scroll to create
toy boxes (folders) for each owner!
"""
