import os
import json
import requests
import msal
import sqlite3
import math
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
from msal import PublicClientApplication

# Configuration
load_dotenv(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'creds.env'))
CLIENT_ID = os.getenv('CLIENT_ID')
AUTHORITY = 'https://login.microsoftonline.com/consumers'
SCOPES = ['Files.ReadWrite.All']
LOCAL_ROOT_FOLDER = 'C:\\GEO'  # Update this to your local folder path
DATABASE_FILE = 'file_metadata.db'
GEO_FOLDER = 'GEO'
CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB chunks

# Initialize MSAL client
app = PublicClientApplication(CLIENT_ID, authority=AUTHORITY)

# Global variable to store the authentication result
result = None

# If needed, you can attempt silent acquisition first (commented out):
# accounts = app.get_accounts()
# result = app.acquire_token_silent(SCOPES, account=accounts[0] if accounts else None)

if not result:
    # Interactive login if no token is available
    result = app.acquire_token_interactive(SCOPES)
    print("Access token acquired successfully.")

# Test connection to OneDrive
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

# Initialize SQLite database
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

def get_access_token():
    """
    Refreshes or acquires a valid access token if the existing one is expired or about to expire.
    """
    global result
    if result is None or 'expires_at' not in result or time.time() > result['expires_at'] - 300:
        accounts = app.get_accounts()
        result = app.acquire_token_silent(SCOPES, account=accounts[0] if accounts else None)
        if not result:
            result = app.acquire_token_interactive(SCOPES)
            print("Access token acquired successfully.")
    return result['access_token']

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
                # Log the error and continue
                print(f"Error accessing file {local_path}: {e}")
    return files

def get_stored_metadata(relative_path):
    cursor.execute('SELECT mtime, size, onedrive_id FROM files WHERE relative_path = ?', (relative_path,))
    return cursor.fetchone()

def create_onedrive_folder_structure(folder_path):
    """
    Recursively creates folder structure in OneDrive under 'root:/'.
    """
    access_token = get_access_token()
    if folder_path == '':
        return
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    folders = folder_path.strip('/').split('/')
    current_path = ''
    for folder in folders:
        current_path += f'/{folder}'
        url = f'https://graph.microsoft.com/v1.0/me/drive/root:/{current_path}'
        response = requests.get(url, headers=headers)
        if response.status_code == 404:
            # Folder doesn't exist; create it
            parent_path = os.path.dirname(current_path)
            if parent_path == '':
                parent_path = '/'
            create_url = f'https://graph.microsoft.com/v1.0/me/drive/root:/{parent_path}:/children'
            data = {'name': folder, 'folder': {}, '@microsoft.graph.conflictBehavior': 'rename'}
            resp = requests.post(create_url, headers=headers, json=data)
            if resp.status_code >= 400:
                print(f"Failed to create folder {folder}: {resp.status_code}, {resp.text}")
                return

def delete_onedrive_item(item_id):
    access_token = get_access_token()
    delete_url = f'https://graph.microsoft.com/v1.0/me/drive/items/{item_id}'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.delete(delete_url, headers=headers)
    if response.status_code >= 400:
        print(f"Failed to delete item: {response.status_code}, {response.text}")
    else:
        print(f"Deleted item with ID {item_id} from OneDrive.")

def move_or_rename_onedrive_item(item_id, new_parent_id=None, new_name=None):
    access_token = get_access_token()
    metadata_url = f'https://graph.microsoft.com/v1.0/me/drive/items/{item_id}'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    json_data = {}
    if new_parent_id:
        json_data['parentReference'] = {'id': new_parent_id}
    if new_name:
        json_data['name'] = new_name
    response = requests.patch(metadata_url, headers=headers, json=json_data)
    if response.status_code >= 400:
        print(f"Failed to move/rename item: {response.status_code}, {response.text}")
        return None
    else:
        print(f"Moved/Renamed item with ID {item_id}.")
    return response.json()

def get_onedrive_item_id_by_path(item_path):
    access_token = get_access_token()
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    url = f'https://graph.microsoft.com/v1.0/me/drive/root:/{item_path}'
    response = requests.get(url, headers=headers)
    if response.status_code >= 400:
        print(f"Failed to get item ID for path {item_path}: {response.status_code}, {response.text}")
        return None
    return response.json()['id']

#########################
# Chunked Upload Methods#
#########################
def create_upload_session(onedrive_path):
    """
    Creates a resumable upload session for the specified OneDrive path.
    """
    access_token = get_access_token()
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    endpoint = f"https://graph.microsoft.com/v1.0/me/drive/root:/{onedrive_path}:/createUploadSession"
    data = {
        "@microsoft.graph.conflictBehavior": "replace",
        "fileSystemInfo": {}  # optional metadata
    }
    response = requests.post(endpoint, headers=headers, json=data)
    if response.status_code >= 400:
        print(f"Failed to create upload session: {response.status_code}, {response.text}")
        return None
    return response.json()

def upload_file_in_chunks(local_file_path, onedrive_path, creation_time, modification_time):
    """
    Uploads the file in chunks using the Graph API upload session.
    """
    session_info = create_upload_session(onedrive_path)
    if not session_info or "uploadUrl" not in session_info:
        return None
    upload_url = session_info["uploadUrl"]

    file_size = os.path.getsize(local_file_path)
    chunk_count = math.ceil(file_size / CHUNK_SIZE)
    print(f"Uploading '{local_file_path}' in {chunk_count} chunk(s)...")

    with open(local_file_path, 'rb') as f:
        start = 0
        chunk_index = 1
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
            r = requests.put(upload_url, headers=headers, data=chunk_data)

            if r.status_code in (200, 201):  # Upload completed
                print(f"File upload finished for '{local_file_path}'.")
                file_info = r.json()
                # Update metadata if needed
                update_onedrive_metadata(file_info['id'], creation_time, modification_time)
                return file_info
            elif r.status_code == 308:  # Partial (resume)
                print(f"Chunk {chunk_index}/{chunk_count} uploaded. Continuing...")
                start = end + 1
                chunk_index += 1
            else:
                print(f"Error uploading chunk. Status: {r.status_code}, Response: {r.text}")
                return None
    return None

def update_onedrive_metadata(item_id, creation_time, modification_time):
    """
    Update the file's creation/modified timestamps on OneDrive.
    """
    access_token = get_access_token()
    metadata_url = f'https://graph.microsoft.com/v1.0/me/drive/items/{item_id}'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    file_system_info = {
        "createdDateTime": datetime.fromtimestamp(creation_time, tz=timezone.utc).isoformat(),
        "lastModifiedDateTime": datetime.fromtimestamp(modification_time, tz=timezone.utc).isoformat()
    }
    json_data = {"fileSystemInfo": file_system_info}
    response = requests.patch(metadata_url, headers=headers, json=json_data)
    if response.status_code >= 400:
        print(f"Failed to update file metadata: {response.status_code}, {response.text}")

##############################
# Main Upload Decision Method#
##############################
def upload_file_to_onedrive(local_file_path, onedrive_path, mtime):
    """
    Decide whether to use simple upload or chunked upload based on file size.
    """
    file_size = os.path.getsize(local_file_path)
    # If file is smaller than 4 MB, use simple PUT upload; otherwise chunked
    if file_size < 4 * 1024 * 1024:
        return simple_upload_file(local_file_path, onedrive_path, mtime)
    else:
        return upload_file_in_chunks(local_file_path, onedrive_path, mtime, mtime)

def simple_upload_file(local_file_path, onedrive_path, mtime):
    """
    Simple upload for smaller files (less than ~4MB).
    """
    access_token = get_access_token()
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    parent_path = os.path.dirname(onedrive_path)
    create_onedrive_folder_structure(parent_path)

    try:
        with open(local_file_path, 'rb') as f:
            file_content = f.read()
    except (PermissionError, FileNotFoundError, OSError) as e:
        print(f"Error reading file {local_file_path}: {e}")
        return None

    upload_url = f'https://graph.microsoft.com/v1.0/me/drive/root:/{onedrive_path}:/content'
    response = requests.put(upload_url, headers=headers, data=file_content)
    if response.status_code >= 400:
        print(f"Failed to upload file: {response.status_code}, {response.text}")
        return None

    file_info = response.json()
    # Update file's fileSystemInfo
    item_id = file_info['id']
    metadata_url = f'https://graph.microsoft.com/v1.0/me/drive/items/{item_id}'
    file_system_info = {
        "createdDateTime": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
        "lastModifiedDateTime": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    }
    json_data = {"fileSystemInfo": file_system_info}
    metadata_headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    meta_resp = requests.patch(metadata_url, headers=metadata_headers, json=json_data)
    if meta_resp.status_code >= 400:
        print(f"Failed to update file metadata: {meta_resp.status_code}, {meta_resp.text}")
        return None

    return file_info

#################
# Main Function #
#################
def main():
    global result
    # Attempt silent token renewal again if needed
    result = app.acquire_token_silent(SCOPES, account=None)
    if not result:
        result = app.acquire_token_interactive(SCOPES)
        print("Access token acquired successfully.")

    current_files = scan_local_folder(LOCAL_ROOT_FOLDER)
    stored_files = {}
    cursor.execute('SELECT relative_path, mtime, size, onedrive_id FROM files')
    for row in cursor.fetchall():
        stored_files[row[0]] = {'mtime': row[1], 'size': row[2], 'onedrive_id': row[3]}

    # Identify files to upload/update or delete
    for relative_path, file_info in current_files.items():
        stored_info = stored_files.get(relative_path)
        onedrive_path = os.path.join(GEO_FOLDER, relative_path).replace('\\', '/')

        if stored_info:
            # Check if file has changed
            if file_info['mtime'] != stored_info['mtime'] or file_info['size'] != stored_info['size']:
                uploaded_file_info = upload_file_to_onedrive(
                    file_info['local_path'], onedrive_path, file_info['mtime']
                )
                if uploaded_file_info:
                    cursor.execute('''
                        UPDATE files SET mtime = ?, size = ? WHERE relative_path = ?
                    ''', (file_info['mtime'], file_info['size'], relative_path))
                    conn.commit()
                    print(f"Updated file on OneDrive: {onedrive_path}")
            else:
                # No changes; do nothing
                pass
            del stored_files[relative_path]
        else:
            # New file
            uploaded_file_info = upload_file_to_onedrive(
                file_info['local_path'], onedrive_path, file_info['mtime']
            )
            if uploaded_file_info:
                cursor.execute('''
                    INSERT INTO files (relative_path, mtime, size, onedrive_id)
                    VALUES (?, ?, ?, ?)
                ''', (relative_path, file_info['mtime'], file_info['size'], uploaded_file_info['id']))
                conn.commit()
                print(f"Uploaded new file to OneDrive: {onedrive_path}")

    # Files remaining in stored_files have been deleted locally
    for relative_path, stored_info in stored_files.items():
        onedrive_id = stored_info['onedrive_id']
        delete_onedrive_item(onedrive_id)
        cursor.execute('DELETE FROM files WHERE relative_path = ?', (relative_path,))
        conn.commit()
        print(f"Deleted file from OneDrive: {relative_path}")

if __name__ == "__main__":
    main()
    conn.close()
