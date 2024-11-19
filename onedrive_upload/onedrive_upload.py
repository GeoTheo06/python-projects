import os
import hashlib
import json
import requests
import msal
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv

# List of folder paths to monitor and sync
folders_to_monitor = [
	r'C:\GEO\projects\Python Projects\onedrive_upload\test1',
	r'C:\GEO\projects\Python Projects\onedrive_upload\test2'
]

metadata_file = 'file_metadata.json'

	load_dotenv(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'creds.env'))
	CLIENT_ID = os.getenv('CLIENT_ID')
	AUTHORITY_URL = f'https://login.microsoftonline.com/consumers'
SCOPES = ['User.Read', 'Files.ReadWrite']

# Helper to calculate a file's hash (e.g., SHA-256)
def calculate_file_hash(file_path):
	sha256_hash = hashlib.sha256()
	with open(file_path, "rb") as f:
		for byte_block in iter(lambda: f.read(4096), b""):
			sha256_hash.update(byte_block)
	return sha256_hash.hexdigest()

# Load metadata from previous sync
def load_metadata():
	if os.path.exists(metadata_file):
		with open(metadata_file, 'r') as f:
			return json.load(f)
	return {}

# Save metadata after sync
def save_metadata(metadata):
	with open(metadata_file, 'w') as f:
		json.dump(metadata, f, indent=4)

# Get file metadata (hash, last modified time)
def get_file_metadata(file_path):
	return {
		'hash': calculate_file_hash(file_path),
		'last_modified': os.path.getmtime(file_path)
	}


def get_access_token():
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY_URL)
    
    # Try to acquire token silently from cache
    accounts = app.get_accounts()
    if accounts:
        token_response = app.acquire_token_silent(SCOPES, account=accounts[0])
        if token_response:
            return token_response['access_token']
    
    # If no token is found or silent acquisition fails, prompt interactive login
    token_response = app.acquire_token_interactive(SCOPES)
    if 'access_token' in token_response:
        return token_response['access_token']
    
    raise Exception(f"Could not obtain access token: {token_response}")

# Compare current state with previous metadata for all folders
# Compare current state with previous metadata for all folders
def initial_sync():
    access_token = get_access_token()
    current_metadata = {}

    # Load the last known state
    previous_metadata = load_metadata()

    # Iterate over all folders to monitor
    for folder_to_monitor in folders_to_monitor:
        folder_name = os.path.basename(folder_to_monitor)  # Get the folder name (e.g., 'test1', 'test2')

        # Walk through the current directory
        for root, dirs, files in os.walk(folder_to_monitor):
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, folder_to_monitor).replace('\\', '/')

                # Construct the OneDrive path with the folder name
                onedrive_relative_path = f"{folder_name}/{relative_path}"

                # Calculate current file hash and last modified time
                current_file_data = get_file_metadata(file_path)

                # Check if the file is in previous metadata (possible rename or new file)
                found_match = False
                for prev_path, prev_data in previous_metadata.items():
                    if current_file_data['hash'] == prev_data['hash']:
                        # File with same hash found but different path -> Renamed or moved
                        if prev_path != relative_path:
                            print(f"File moved or renamed from {prev_path} to {relative_path}")
                            # Try renaming the file on OneDrive
                            if not rename_file_on_onedrive(prev_data['item_id'], relative_path, access_token):
                                # If renaming fails (invalid item ID), re-upload the file
                                upload_path = f"{folder_name}/{relative_path}"
                                upload_file_to_onedrive(file_path, upload_path, access_token)
                            # Update the path in current metadata
                            current_metadata[relative_path] = prev_data
                        found_match = True
                        break

                if not found_match:
                    # New file detected (no matching hash found)
                    print(f"New file detected: {relative_path}")
                    # Upload the new file to the corresponding folder on OneDrive
                    upload_path = f"{folder_name}/{relative_path}"
                    upload_file_to_onedrive(file_path, upload_path, access_token)
                    current_metadata[relative_path] = {
                        'item_id': 'new_onedrive_item_id',  # Replace with actual OneDrive item ID
                        'hash': current_file_data['hash'],
                        'last_modified': current_file_data['last_modified']
                    }

    # Detect deleted files
    for prev_path, prev_data in previous_metadata.items():
        if prev_path not in current_metadata:
            print(f"File deleted: {prev_path}")
            # Attempt to delete the file using the stored item ID, skip if invalid
            delete_file_from_onedrive(prev_data['item_id'], prev_path, access_token)

    # Save the updated metadata
    save_metadata(current_metadata)

	
# OneDrive helper functions to upload, delete, and rename files

# Function to create folder structure on OneDrive for the specified relative path
def create_onedrive_folder_structure(relative_path, access_token):
    folder_names = relative_path.split('/')
    current_path = ""
    
    for folder in folder_names[:-1]:  # Skip the last element, which is the file name
        current_path = f"{current_path}/{folder}" if current_path else folder
        create_folder_url = f"https://graph.microsoft.com/v1.0/me/drive/root:/backup/{current_path}:/children"
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        # Check if the folder exists using GET request
        response = requests.get(f"https://graph.microsoft.com/v1.0/me/drive/root:/backup/{current_path}", headers=headers)

        if response.status_code == 404:  # Folder does not exist
            # Create the folder since it doesn't exist
            folder_create_url = f"https://graph.microsoft.com/v1.0/me/drive/root:/backup/{current_path}:/children"
            data = {
                "name": folder,
                "folder": {},
                "@microsoft.graph.conflictBehavior": "replace"
            }
            create_response = requests.post(folder_create_url, headers=headers, json=data)
            if create_response.status_code == 201:
                print(f"Folder '{folder}' created successfully in OneDrive at path '{current_path}'.")
            else:
                print(f"Failed to create folder '{folder}' in OneDrive: {create_response.status_code} - {create_response.text}")
        elif response.status_code != 200:
            print(f"Error checking folder '{folder}' in OneDrive: {response.status_code} - {response.text}")

# Upload file with folder structure creation
def upload_file_to_onedrive(file_path, upload_path, access_token):
    # Ensure the folder structure exists in OneDrive before uploading
    create_onedrive_folder_structure(upload_path, access_token)

    # Now upload the file
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/octet-stream'
    }

    with open(file_path, 'rb') as file_data:
        response = requests.put(f"https://graph.microsoft.com/v1.0/me/drive/root:/backup/{upload_path}:/content", headers=headers, data=file_data)

    if response.status_code == 201:
        print(f"File '{file_path}' uploaded successfully to OneDrive.")
    else:
        print(f"Failed to upload file '{file_path}': {response.status_code} - {response.text}")

def delete_file_from_onedrive(item_id, relative_path, access_token):
    # Check if the item ID is valid before attempting to delete
    if not item_id or item_id == 'new_onedrive_item_id':
        print(f"Invalid item ID for deleting: {item_id}. Skipping deletion for '{relative_path}'.")
        return False  # Skip deletion
    
    delete_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{item_id}"

    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    response = requests.delete(delete_url, headers=headers)

    if response.status_code == 204:
        print(f"File '{relative_path}' deleted successfully from OneDrive.")
        return True
    else:
        print(f"Failed to delete file '{relative_path}' from OneDrive: {response.status_code} - {response.text}")
        return False

def rename_file_on_onedrive(item_id, new_name, access_token):
    # Check if the item ID is valid
    if not item_id or item_id == 'new_onedrive_item_id':  # Handle invalid or placeholder item IDs
        print(f"Invalid item ID for renaming: {item_id}. Re-uploading file instead.")
        return False  # Signal that the rename failed, so you can upload instead

    rename_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{item_id}"

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    data = {
        "name": new_name
    }

    response = requests.patch(rename_url, headers=headers, json=data)

    if response.status_code == 200:
        print(f"File renamed to '{new_name}' successfully on OneDrive.")
        return True
    else:
        print(f"Failed to rename file on OneDrive: {response.status_code} - {response.text}")
        return False  # Signal that the rename failed
		
if __name__ == "__main__":
	# Initial sync to detect renames, deletions, or new files across multiple folders
	initial_sync()