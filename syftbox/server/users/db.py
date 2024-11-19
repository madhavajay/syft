import sqlite3

from pydantic import BaseModel, EmailStr
create_table_query = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    password TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    is_banned BOOLEAN DEFAULT 0
);
"""

class UserModel(BaseModel):
    id: int
    password: str
    email: EmailStr
    is_banned: bool

def verify_password(password: str, user: UserModel):
    return password == user.password

def get_db_connection():
    conn = sqlite3.connect("user_database.db")
    return conn

def init_user_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(create_table_query)
    add_user("changethis", "info@openmined.org")
    conn.commit()
    conn.close()

def add_user(password, email):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO users (password, email) 
        VALUES (?, ?)
        """, (password, email))
        conn.commit()
        print("User added successfully!")
    except sqlite3.IntegrityError as e:
        print(f"Error: {e}")
    finally:
        conn.close()
        
def get_user_by_email(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, email, is_banned FROM users WHERE email = ?", (email))
        user = cursor.fetchone()
        conn.close()
        conn.commit()
    except sqlite3.IntegrityError as e:
        print(f"Error: {e}")
    finally:
        conn.close()
    return UserModel(**dict(zip(UserModel.model_fields.keys(),user)))
        
def get_all_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    conn.close()
    return users

def delete_user(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    DELETE FROM users
    WHERE email = ?
    """, (email,))
    conn.commit()
    conn.close()
    print("User deleted successfully!")
    
def ban_user(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE users
    SET is_banned = 1
    WHERE email = ?
    """, (email,))
    conn.commit()
    conn.close()
    
def unban_user(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE users
    SET is_banned = 0
    WHERE email = ?
    """, (email,))
    conn.commit()
    conn.close()
    
def update_password(email, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE users
    SET password = ?
    WHERE email = ?
    """, (password, email))
    conn.commit()
    conn.close()
    print("Password updated successfully!")
    
    
# testing
if __name__ == "__main__":
    init_user_table()
    
    add_user("password123", "johndoe@example.com")
    add_user("securepass", "janedoe@example.com")

    users = get_all_users()
    print(users)

    ban_user("johndoe@example.com")
    users = get_all_users()
    print(users)
    
    unban_user("johndoe@example.com")
    unban_user("johndoe@example.com")

    update_password("johndoe@example.com", "changethis")

    delete_user("janedoe")

    users = get_all_users()
    print(users)
