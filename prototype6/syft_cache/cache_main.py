from flask import Flask, request, jsonify, render_template, redirect, url_for
import re
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import sqlite3

app = Flask(__name__)

# SQLite database setup
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, public_key TEXT)''')
    conn.commit()
    conn.close()

init_db()

def validate_username(username):
    return True

def validate_public_key(public_key):
    # try:
    #     serialization.load_pem_public_key(public_key.encode())
    #     return True
    # except:
    #     return False
    return True

@app.route('/')
def index():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT username FROM users")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return render_template('index.html', users=users)

@app.route('/users', methods=['POST'])
def add_user():
    username = request.form.get('username')
    public_key = request.form.get('public_key')

    if not username or not public_key:
        return "Username and public key are required", 400

    if not validate_username(username):
        return "Invalid username format", 400

    if not validate_public_key(public_key):
        return "Invalid public key format", 400

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, public_key) VALUES (?, ?)", (username, public_key))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return "Username already exists", 409
    finally:
        conn.close()

    return redirect(url_for('index'))

@app.route('/users/<username>', methods=['DELETE'])
def remove_user(username):
    if not validate_username(username):
        return "Invalid username format", 400

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE username = ?", (username,))
    if c.rowcount == 0:
        conn.close()
        return "User not found", 404
    conn.commit()
    conn.close()

    return "User removed successfully", 200

@app.route('/users/<username>', methods=['GET'])
def get_user(username):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()

    if user:
        return jsonify({"username": user[0], "public_key": user[1]})
    else:
        return "User not found", 404

@app.route('/users/<username>', methods=['PUT'])
def update_user(username):
    new_public_key = request.form.get('public_key')

    if not new_public_key:
        return "Public key is required", 400

    if not validate_public_key(new_public_key):
        return "Invalid public key format", 400

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET public_key = ? WHERE username = ?", (new_public_key, username))
    if c.rowcount == 0:
        conn.close()
        return "User not found", 404
    conn.commit()
    conn.close()

    return redirect(url_for('index'))

# Add this new route to get all users
@app.route('/users', methods=['GET'])
def get_all_users():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT username FROM users")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return jsonify(users)

if __name__ == '__main__':
    app.run(debug=True)