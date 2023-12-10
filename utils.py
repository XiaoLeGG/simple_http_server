import sqlite3 as sql
import os
import uuid

user_data_file = "user_data.db"
cookie_file = "cookie.db"

def init_sql():
    if not os.path.exists(user_data_file):
        conn = sql.connect(user_data_file)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE user (uuid TEXT PRIMARY KEY, name TEXT NOT NULL, password TEXT NOT NULL)")
        conn.commit()
        conn.close()
    if not os.path.exists(cookie_file):
        conn = sql.connect(cookie_file)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE cookie (cookie TEXT PRIMARY KEY, uuid TEXT NOT NULL, expire_time DATETIME NOT NULL)")
        conn.commit()
        conn.close()

def verify_user(uuid : uuid.UUID, password : str) -> bool:
    conn = sql.connect(user_data_file)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user WHERE uuid = ? AND password = ?", (uuid, password))
    if cursor.fetchone() is None:
        return False
    else:
        return True

def create_user(uuid : uuid.UUID, user_name : str, password : str):
    conn = sql.connect(user_data_file)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO user VALUES (?, ?, ?)", (uuid, user_name.lower(), password))
    conn.commit()
    conn.close()

def get_user_by_name(user_name : str) -> uuid.UUID:
    conn = sql.connect(user_data_file)
    cursor = conn.cursor()
    cursor.execute("SELECT uuid FROM user WHERE name = ?", (user_name.lower(),))
    result = cursor.fetchone()
    if result is None:
        return None
    else:
        return uuid.UUID(result[0])

def get_user_by_cookie(cookie : uuid.UUID) -> uuid.UUID:
    conn = sql.connect(cookie_file)
    cursor = conn.cursor()
    cursor.execute("SELECT uuid FROM cookie WHERE cookie = ?", (cookie,))
    result = cursor.fetchone()
    if result is None:
        return None
    else:
        return uuid.UUID(result[0])

def set_cookie(uuid : uuid.UUID, cookie : uuid.UUID, persist_time : int):
    conn = sql.connect(cookie_file)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO cookie VALUES (?, ?, datetime('now', '+{} seconds'))".format(persist_time * 60 * 60 * 24), (cookie, uuid))
    conn.commit()
    conn.close()

def clean_cookie():
    conn = sql.connect(cookie_file)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cookie WHERE expire_time < datetime('now')")
    conn.commit()
    conn.close()

def clean_cookie_by_user(uuid : uuid.UUID):
    conn = sql.connect(cookie_file)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cookie WHERE uuid = ?", (uuid,))
    conn.commit()
    conn.close()

def clean_cookie_by_cookie(cookie : uuid.UUID):
    conn = sql.connect(cookie_file)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cookie WHERE cookie = ?", (cookie,))
    conn.commit()
    conn.close()

def file_explore_html(dir : str) -> str:
    
    if not os.path.exists(dir):
        return "<html><body><h1>File Not Exists</h1></body></html>"
    
    # Get the list of files and directories in the current directory


    files = os.listdir(dir)
    
    # Generate the HTML for the file explorer
    html = "<html><body>"
    html += "<h1>File Explorer</h1>"
    html += "<ul>"
    for file in files:
        html += f"<li>{file}</li>"
    html += "</ul>"
    html += "</body></html>"
    return html