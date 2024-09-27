import os
import msal
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'creds.env'))

CLIENT_ID = os.getenv('CLIENT_ID')
AUTHORITY_URL = f'https://login.microsoftonline.com/consumers'
SCOPES = ['User.Read', 'Files.ReadWrite']


# MSAL client app configuration for delegated flow
def get_access_token():
	app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY_URL)
	
	# First, try to load an existing token from cache
	accounts = app.get_accounts()
	if accounts:
		token_response = app.acquire_token_silent(SCOPES, account=accounts[0])
	else:
		# If no token exists, prompt user to log in interactively
		token_response = app.acquire_token_interactive(SCOPES)
	
	if 'access_token' in token_response:
		return token_response['access_token']
	else:
		raise Exception(f"Could not obtain access token: {token_response}")

def upload_file_to_onedrive(file_path, upload_path, access_token):
	headers = {
		'Authorization': f'Bearer {access_token}',
		'Content-Type': 'application/octet-stream'
	}

	with open(file_path, 'rb') as file_data:
		response = requests.put(upload_path, headers=headers, data=file_data)

	if response.status_code == 201:
		print(f"File '{file_path}' uploaded successfully to OneDrive.")
	else:
		print(f"Failed to upload file '{file_path}': {response.status_code} - {response.text}")

# Upload directory and subfolders to OneDrive
def upload_folder_to_onedrive():
	access_token = get_access_token(folder_path)

	for root, dirs, files in os.walk(folder_path):
		for file in files:
			file_path = os.path.join(root, file)
			# Construct the OneDrive upload URL for each file, preserving folder structure
			relative_path = os.path.relpath(file_path, folder_path).replace('\\', '/')
			upload_path = f"https://graph.microsoft.com/v1.0/me/drive/root:/backup/{relative_path}:/content"
			
			upload_file_to_onedrive(file_path, upload_path, access_token)

if __name__ == "__main__":
	
	upload_folder_to_onedrive(r'C:\GEO\projects\Python Projects\onedrive_upload\GEO')
	upload_folder_to_onedrive(r'C:\GEO\projects\Python Projects\onedrive_upload\testing')
