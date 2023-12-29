import sqlite3 as sql
import os
import uuid as ud
import pytz
from datetime import datetime, timedelta
from jinja2 import Template

user_data_file = "user_data.db"
cookie_file = "user_data.db"

def get_current_time() -> datetime:
    current_time = datetime.now()
    gmt_timezone = pytz.timezone('GMT')
    current_time_gmt = current_time.astimezone(gmt_timezone)
    return current_time_gmt

def init_sql():
    conn = sql.connect(user_data_file)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (uuid TEXT PRIMARY KEY, name TEXT NOT NULL, password TEXT NOT NULL)")
    conn.commit()
    conn.close()

    conn = sql.connect(cookie_file)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS cookies (cookie TEXT PRIMARY KEY, uuid TEXT NOT NULL, expire_time DATETIME NOT NULL)")
    conn.commit()
    conn.close()

def verify_user(uuid : ud.UUID, password : str) -> bool:
    conn = sql.connect(user_data_file)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE uuid = ? AND password = ?", (str(uuid), password))
    if cursor.fetchone() is None:
        return False
    else:
        return True
    
def get_root_dir() -> str:
    return f".{ os.path.sep } "

def get_data_dir() -> str:
    data_dir = f".{ os.path.sep }data"
    if not os.path.exists(data_dir):
        os.mkdir(data_dir)
    return data_dir

def generate_folder(user_name : str):
    folder_name = os.path.join(get_data_dir(), user_name)
    if not os.path.exists(folder_name):
        os.mkdir(folder_name)
    return folder_name

def create_user(user_name : str, password : str) -> ud.UUID:
    exist_uuid = get_user_by_name(user_name)
    if exist_uuid is not None:
        raise Exception("User already exists.")
    uuid = ud.uuid4()
    generate_folder(user_name.lower())
    conn = sql.connect(user_data_file)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users VALUES (?, ?, ?)", (str(uuid), user_name.lower(), password))
    conn.commit()
    conn.close()
    return uuid

def get_user_by_name(user_name : str) -> ud.UUID:
    conn = sql.connect(user_data_file)
    cursor = conn.cursor()
    cursor.execute("SELECT uuid FROM users WHERE name = ?", (user_name.lower(),))
    result = cursor.fetchone()
    if result is None:
        return None
    else:
        return ud.UUID(result[0])

def get_user_name_by_uuid(uuid : ud.UUID) -> str:
    conn = sql.connect(user_data_file)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM users WHERE uuid = ?", (str(uuid),))
    result = cursor.fetchone()
    if result is None:
        return None
    else:
        return result[0]

def get_user_by_cookie(cookie : ud.UUID) -> ud.UUID:
    conn = sql.connect(cookie_file)
    cursor = conn.cursor()
    cursor.execute("SELECT uuid, expire_time FROM cookies WHERE cookie = ?", (str(cookie),))
    result = cursor.fetchone()
    if result is None:
        return None
    else:
        expire_time = datetime.strptime(result[1], "%Y-%m-%d %H:%M:%S")
        current_time = get_current_time().replace(tzinfo=None)
        if expire_time < current_time:
            clean_cookie_by_cookie(cookie)
            return None
        return ud.UUID(result[0])
    
def get_cookie_by_user(uuid : ud.UUID) -> ud.UUID:
    conn = sql.connect(cookie_file)
    cursor = conn.cursor()
    cursor.execute("SELECT cookie, expire_time FROM cookies WHERE uuid = ?", (str(uuid),))
    result = cursor.fetchone()
    if result is None:
        return None
    else:
        expire_time = datetime.strptime(result[1], "%Y-%m-%d %H:%M:%S")
        current_time = get_current_time().replace(tzinfo=None)
        if expire_time < current_time:
            clean_cookie_by_user(uuid)
            return None
        return ud.UUID(result[0])
    
def generate_cookie(uuid : ud.UUID, persist_time : int=120) -> ud.UUID:
    cookie = ud.uuid4()
    set_cookie(uuid, cookie, persist_time)
    return cookie

def resign_cookie(cookie : ud.UUID, persist_time: int):
    conn = sql.connect(cookie_file)
    cursor = conn.cursor()
    cursor.execute("UPDATE cookies SET expire_time = datetime('now', '+{} seconds') WHERE cookie = ?".format(persist_time), (str(cookie),))
    conn.commit()
    conn.close()

def set_cookie(uuid : ud.UUID, cookie : ud.UUID, persist_time : int):
    conn = sql.connect(cookie_file)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO cookies VALUES (?, ?, datetime('now', '+{} seconds'))".format(persist_time), (str(cookie), str(uuid)))
    conn.commit()
    conn.close()

def clean_cookie():
    conn = sql.connect(cookie_file)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cookies WHERE expire_time < datetime('now')")
    conn.commit()
    conn.close()

def clean_cookie_by_user(uuid : ud.UUID):
    conn = sql.connect(cookie_file)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cookies WHERE uuid = ?", (str(uuid),))
    conn.commit()
    conn.close()

def clean_cookie_by_cookie(cookie : ud.UUID):
    conn = sql.connect(cookie_file)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cookies WHERE cookie = ?", (str(cookie),))
    conn.commit()
    conn.close()

login_template = None

def login_html():
    global login_template
    if login_template is None:
        with open("index.html", "r", encoding="utf-8") as template_file:
            template_content = template_file.read()
        login_template = Template(template_content)
    rendered_html = login_template.render()
    return rendered_html


file_explore_template = None

def file_explore_html(dir : str, user_name : str, abs_dir : str, uuid : ud.UUID=None, sustech_http : bool=False) -> str:
    global file_explore_template
    abs_files = os.listdir(abs_dir)

    if sustech_http:
        files = []
        for file in abs_files:
            file_name = os.path.basename(file)
            if os.path.isdir(file):
                files.append(file_name + "/")
            else:
                files.append(file_name)
        return str(files)
    if file_explore_template is None:
        with open("view_files.html", "r", encoding="utf-8") as template_file:
            template_content = template_file.read()
        file_explore_template = Template(template_content)
    files = []

    if dir.lower() != user_name:
        files = [("../", "../", True)]

    for file in abs_files:
        file_name = os.path.basename(file)
        if os.path.isdir(os.path.join(abs_dir, file)):
            files.append(("/" + dir + "/" + file_name + "/", file_name + "/", True))
        else:
            files.append(("/" + dir + "/" + file_name, file_name, False))
    
    files.sort(key=lambda x: (not x[2], x[1]))

    
    rendered_html = file_explore_template.render(files=files, user_name=user_name, current_path=dir)

    return rendered_html

def filter_path(path : str) -> str:
    path = path.replace("//", "/")

def normalize_and_validate_path(base_path : str, request_uri : str) -> str:
    request_uri = request_uri.replace("/", os.path.sep)
    if request_uri.startswith(os.path.sep):
        request_uri = request_uri[len(os.path.sep):]
    base_path = os.path.normpath(base_path)
    request_uri = os.path.normpath(request_uri)
    normalized_path = os.path.normpath(os.path.join(base_path, request_uri))
    if os.path.commonprefix([normalized_path, base_path]) != base_path:
        return None
    
    return normalized_path

def unquote_uri(s):
    decoded_bytes = bytes()
    i = 0
    while i < len(s):
        if s[i] == '%':
            decoded_bytes += int(s[i + 1:i + 3], 16).to_bytes(1, 'big')
            i += 3
        else:
            decoded_bytes += s[i].encode('utf-8')
            i += 1

    return decoded_bytes.decode('utf-8')

def parse_ranges(ranges : str, file_size : int) -> list[tuple]:
    ranges = ranges[len("bytes="):]
    ranges = ranges.split(",")
    result = []
    for _range in ranges:
        if "-" not in _range:
            start = end = int(_range)
        elif _range.endswith("-"):
            start = int(_range[:-1])
            if start < 0:
                start = start + file_size
            end = file_size - 1
        elif _range.startswith("-"):
            parts = _range.split("-")
            start = file_size - int(parts[1])
            if len(parts) == 2:
                end = file_size - 1
            else:
                if len(parts[2]) == 0:
                    end = file_size - int(parts[3])
                else:
                    end = int(parts[2])
        else:
            parts = _range.split("-")
            start = int(parts[0])
            if len(parts[1]) == 0:
                end = file_size - int(parts[2])
            else:
                end = int(parts[1])
        if start > end:
            return None
        if start >= file_size:
            return None
        if end >= file_size:
            return None
        result.append((start, end))
    return result