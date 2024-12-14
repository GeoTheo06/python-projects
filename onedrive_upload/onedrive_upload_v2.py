import os
import json
import requests
import msal
import sqlite3
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from dotenv import load_dotenv
from msal import PublicClientApplication
from threading import Lock

# -----------------------------
# Configuration & Constants
# -----------------------------
load_dotenv(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'creds.env'))
CLIENT_ID = os.getenv('CLIENT_ID')
AUTHORITY = 'https://login.microsoftonline.com/consumers'
SCOPES = ['Files.ReadWrite.All']
LOCAL_ROOT_FOLDER = 'C:\\GEO'  # Update this to your local folder path
DATABASE_FILE = 'file_metadata.db'
GEO_FOLDER = 'GEO'

CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB chunks for large file uploads
SMALL_FILE_SIZE = 4 * 1024 * 1024  # Use simple upload if file < 4 MB
SKIP_METADATA_THRESHOLD = 1 * 1024 * 1024  # Skip metadata patch for files < 1 MB

MAX_RETRIES = 3         # Maximum number of retry attempts
INITIAL_BACKOFF = 2.0   # Initial backoff seconds (exponential growth)

# Global variables
result = None
lock = Lock()

# -----------------------------
# MSAL Initialization
# -----------------------------
app = PublicClientApplication(CLIENT_ID, authority=AUTHORITY)
if not result:
    result = app.acquire_token_interactive(SCOPES)
    print("Access token acquired successfully.")

# Test OneDrive connection
headers = {
    'Authorization': f'Bearer {result["access_token"]}',
    'Content-Type': 'application/json'
}
response = requests.get('https://graph.microsoft.com/v1.0/me/drive/root', headers=headers)
if response.status_code == 200:
    print("Connected to OneDrive successfully.")
    access_token = result['access_token']
else:
    print("Failed to connect to OneDrive:", response.status_code, response.text)
    exit()

# -----------------------------
# Database Initialization
# -----------------------------
conn = sqlite3.connect(DATABASE_FILE)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS files (
        relative_path TEXT PRIMARY KEY,
        mtime REAL,
        size INTEGER,
        onedrive_id TEXT
    )
''')
conn.commit()

# -----------------------------
# Token Management
# -----------------------------
def get_access_token():
    global result
    # Refresh token if near expiry
    if result is None or 'expires_at' not in result or time.time() > result['expires_at'] - 300:
        accounts = app.get_accounts()
        result = app.acquire_token_silent(SCOPES, account=accounts[0] if accounts else None)
        if not result:
            result = app.acquire_token_interactive(SCOPES)
            print("Access token acquired successfully.")
    return result['access_token']

# -----------------------------
# Generic Retry Wrapper
# -----------------------------
def make_request_with_retry(method, url, headers=None, data=None, json_data=None, stream=False):
    """
    A generic requests wrapper that retries transient errors with exponential backoff.
    method: 'GET', 'POST', 'PUT', 'PATCH', 'DELETE'...
    """
    attempt = 1
    backoff = INITIAL_BACKOFF
    while attempt <= MAX_RETRIES:
        try:
            if method == 'GET':
                resp = requests.get(url, headers=headers, stream=stream)
            elif method == 'POST':
                resp = requests.post(url, headers=headers, data=data, json=json_data)
            elif method == 'PUT':
                resp = requests.put(url, headers=headers, data=data)
            elif method == 'PATCH':
                resp = requests.patch(url, headers=headers, json=json_data)
            elif method == 'DELETE':
                resp = requests.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            # Check if transient error or success
            if resp.status_code < 500 and resp.status_code != 429:
                # For 2xx or 4xx (non-transient) errors, break out
                return resp
            else:
                print(f"Transient HTTP error {resp.status_code} on attempt {attempt}. Retrying...")
        except requests.ConnectionError as e:
            print(f"Connection error on attempt {attempt}: {e}")
        except requests.Timeout as e:
            print(f"Timeout on attempt {attempt}: {e}")

        # Exponential backoff before next attempt
        time.sleep(backoff)
        backoff *= 2
        attempt += 1

    print(f"All {MAX_RETRIES} retry attempts failed for {url}.")
    return None

# -----------------------------
# OneDrive Folder Caching
# -----------------------------
def build_onedrive_folder_cache(folder_paths):
    """
    Pre-creates folder structure on OneDrive in a single pass.
    """
    print("Building folder structure cache in OneDrive...")
    sorted_folders = sorted(folder_paths, key=lambda p: p.count('/'))
    existing_folders = set()

    for folder_path in sorted_folders:
        if not folder_path or folder_path in existing_folders:
            continue
        access_token = get_access_token()
        headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
        url = f'https://graph.microsoft.com/v1.0/me/drive/root:/{folder_path}'
        resp = make_request_with_retry('GET', url, headers=headers)
        if resp is None:
            continue  # Gave up on retries
        if resp.status_code == 200:
            existing_folders.add(folder_path)
        else:
            parent = os.path.dirname(folder_path) or '/'
            create_url = f'https://graph.microsoft.com/v1.0/me/drive/root:/{parent}:/children'
            data = {'name': os.path.basename(folder_path), 'folder': {}, '@microsoft.graph.conflictBehavior': 'replace'}
            resp2 = make_request_with_retry('POST', create_url, headers=headers, json_data=data)
            if resp2 and resp2.status_code < 400:
                existing_folders.add(folder_path)
            else:
                print(f"Failed to create folder '{folder_path}': {resp2.status_code if resp2 else 'No Response'}")

def gather_all_subfolders(file_map):
    """
    Gathers all unique parent folders from the list of file paths.
    E.g., "GEO/subfolder/another" => we store 'GEO/subfolder/another'
    """
    folder_set = set()
    for relative_path in file_map:
        onedrive_path = os.path.join(GEO_FOLDER, relative_path).replace('\\', '/')
        folder = os.path.dirname(onedrive_path).strip('/')
        if folder:
            folder_set.add(folder)
    return folder_set

# -----------------------------
# Local Folder & DB Utilities
# -----------------------------
def scan_local_folder(root_folder):
    files = {}
    for dirpath, _, filenames in os.walk(root_folder):
        for filename in filenames:
            local_path = os.path.join(dirpath, filename)
            relative_path = os.path.relpath(local_path, root_folder).replace('\\', '/')
            try:
                stat = os.stat(local_path)
                mtime, size = stat.st_mtime, stat.st_size
                files[relative_path] = {
                    'local_path': local_path,
                    'mtime': mtime,
                    'size': size
                }
            except (PermissionError, FileNotFoundError, OSError) as e:
                print(f"Error accessing file {local_path}: {e}")
    return files

def delete_onedrive_item(item_id):
    access_token = get_access_token()
    headers = {'Authorization': f'Bearer {access_token}'}
    url = f'https://graph.microsoft.com/v1.0/me/drive/items/{item_id}'
    resp = make_request_with_retry('DELETE', url, headers=headers)
    if resp is None or resp.status_code >= 400:
        print(f"Failed to delete item: {resp.status_code if resp else 'No Response'}")
    else:
        print(f"Deleted item with ID {item_id} from OneDrive.")

# -----------------------------
# Chunked Upload
# -----------------------------
def create_upload_session(onedrive_path):
    access_token = get_access_token()
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    endpoint = f"https://graph.microsoft.com/v1.0/me/drive/root:/{onedrive_path}:/createUploadSession"
    data = {"@microsoft.graph.conflictBehavior": "replace", "fileSystemInfo": {}}
    resp = make_request_with_retry('POST', endpoint, headers=headers, json_data=data)
    if resp and resp.status_code < 400:
        return resp.json()
    print(f"Failed to create upload session for {onedrive_path}")
    return None

def update_onedrive_metadata(item_id, creation_time, modification_time):
    access_token = get_access_token()
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    metadata_url = f'https://graph.microsoft.com/v1.0/me/drive/items/{item_id}'
    file_system_info = {
        "createdDateTime": datetime.fromtimestamp(creation_time, tz=timezone.utc).isoformat(),
        "lastModifiedDateTime": datetime.fromtimestamp(modification_time, tz=timezone.utc).isoformat()
    }
    resp = make_request_with_retry('PATCH', metadata_url, headers=headers, json_data={"fileSystemInfo": file_system_info})
    if resp is None or resp.status_code >= 400:
        code = resp.status_code if resp else 'No Resp'
        print(f"Failed to update file metadata: {code}, {resp.text if resp else ''}")

def upload_file_in_chunks(local_file_path, onedrive_path, creation_time, modification_time):
    session_info = create_upload_session(onedrive_path)
    if not session_info or "uploadUrl" not in session_info:
        return None
    upload_url = session_info["uploadUrl"]

    file_size = os.path.getsize(local_file_path)
    chunk_count = math.ceil(file_size / CHUNK_SIZE)
    print(f"Uploading '{local_file_path}' in {chunk_count} chunk(s)...")

    start = 0
    chunk_index = 1
    with open(local_file_path, 'rb') as f:
        while start < file_size:
            end = min(start + CHUNK_SIZE - 1, file_size - 1)
            chunk_size = end - start + 1
            chunk_data = f.read(chunk_size)

            access_token = get_access_token()
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Length': str(chunk_size),
                'Content-Range': f'bytes {start}-{end}/{file_size}'
            }
            resp = make_request_with_retry('PUT', upload_url, headers=headers, data=chunk_data)
            if resp is None:
                return None

            if resp.status_code in (200, 201):
                file_info = resp.json()
                print(f"File upload finished for '{local_file_path}'.")
                update_onedrive_metadata(file_info['id'], creation_time, modification_time)
                return file_info
            elif resp.status_code == 308:
                print(f"Uploaded chunk {chunk_index}/{chunk_count} for '{local_file_path}'. Continuing...")
                start = end + 1
                chunk_index += 1
            else:
                print(f"Error uploading chunk. Status: {resp.status_code}, Response: {resp.text}")
                return None
    return None

# -----------------------------
# Simple Upload Logic
# -----------------------------
def simple_upload_file(local_file_path, onedrive_path, mtime):
    access_token = get_access_token()
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        with open(local_file_path, 'rb') as f:
            file_content = f.read()
    except (PermissionError, FileNotFoundError, OSError) as e:
        print(f"Error reading file {local_file_path}: {e}")
        return None

    upload_url = f'https://graph.microsoft.com/v1.0/me/drive/root:/{onedrive_path}:/content'
    resp = make_request_with_retry('PUT', upload_url, headers=headers, data=file_content)
    if resp is None or resp.status_code >= 400:
        code = resp.status_code if resp else 'No Resp'
        print(f"Failed to upload file: {local_file_path} => {code}, {resp.text if resp else ''}")
        return None

    file_info = resp.json()
    item_id = file_info['id']
    # Skip metadata patch for tiny files
    if os.path.getsize(local_file_path) > SKIP_METADATA_THRESHOLD:
        update_onedrive_metadata(item_id, mtime, mtime)
    return file_info

def upload_file_to_onedrive(local_file_path, onedrive_path, mtime):
    file_size = os.path.getsize(local_file_path)
    if file_size < SMALL_FILE_SIZE:
        return simple_upload_file(local_file_path, onedrive_path, mtime)
    else:
        return upload_file_in_chunks(local_file_path, onedrive_path, mtime, mtime)

# -----------------------------
# Parallel Upload Worker
# -----------------------------
stored_files = {}  # We'll fill this in main()

def upload_worker(relative_path, file_info):
    onedrive_path = os.path.join(GEO_FOLDER, relative_path).replace('\\', '/')
    with lock:
        stored_info = stored_files.get(relative_path)

    if stored_info:
        # Check if file changed
        if file_info['mtime'] != stored_info['mtime'] or file_info['size'] != stored_info['size']:
            file_resp = upload_file_to_onedrive(file_info['local_path'], onedrive_path, file_info['mtime'])
            if file_resp:
                with lock:
                    cursor.execute('''
                        UPDATE files SET mtime = ?, size = ? WHERE relative_path = ?
                    ''', (file_info['mtime'], file_info['size'], relative_path))
                    conn.commit()
                    print(f"Updated file on OneDrive: {onedrive_path}")
        with lock:
            if relative_path in stored_files:
                del stored_files[relative_path]
    else:
        # New file
        file_resp = upload_file_to_onedrive(file_info['local_path'], onedrive_path, file_info['mtime'])
        if file_resp:
            with lock:
                cursor.execute('''
                    INSERT INTO files (relative_path, mtime, size, onedrive_id)
                    VALUES (?, ?, ?, ?)
                ''', (relative_path, file_info['mtime'], file_info['size'], file_resp['id']))
                conn.commit()
                print(f"Uploaded new file to OneDrive: {onedrive_path}")

# -----------------------------
# Main Function
# -----------------------------
def main():
    global result, stored_files
    result = app.acquire_token_silent(SCOPES, account=None)
    if not result:
        result = app.acquire_token_interactive(SCOPES)
        print("Access token acquired successfully.")

    # 1. Scan local folder
    current_files = scan_local_folder(LOCAL_ROOT_FOLDER)

    # 2. Load stored records
    cursor.execute('SELECT relative_path, mtime, size, onedrive_id FROM files')
    for row in cursor.fetchall():
        stored_files[row[0]] = {'mtime': row[1], 'size': row[2], 'onedrive_id': row[3]}

    # 3. Pre-create folder structure
    folder_paths = gather_all_subfolders(current_files)
    build_onedrive_folder_cache(folder_paths)

    # 4. Parallel upload files
    from concurrent.futures import ThreadPoolExecutor, as_completed
    file_info_list = [(rp, info) for rp, info in current_files.items()]
    max_workers = 5  # Adjust for your bandwidth/CPU
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(upload_worker, rp, info) for rp, info in file_info_list]
        for future in as_completed(futures):
            exc = future.exception()
            if exc:
                print(f"Error in parallel upload thread: {exc}")

    # 5. Handle locally deleted files
    for relative_path, stored_info in stored_files.items():
        onedrive_id = stored_info['onedrive_id']
        delete_onedrive_item(onedrive_id)
        cursor.execute('DELETE FROM files WHERE relative_path = ?', (relative_path,))
        conn.commit()
        print(f"Deleted file from OneDrive: {relative_path}")

if __name__ == "__main__":
    main()
    conn.close()
