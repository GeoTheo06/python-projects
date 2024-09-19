import os
import requests
from dotenv import load_dotenv
import msal


def auth():
	# Load environment variables from creds.env
	load_dotenv(r'C:\GEO\projects\Python Projects\onedrive_upload\creds.env')

	client_id = os.getenv('CLIENT_ID')
	tenant_id = os.getenv('DIR_ID')
	client_secret = os.getenv('SECRET_SECRET_ID')
	scopes = ['Files.ReadWrite.All']

	# Confidential client application for server-side applications
	app = ConfidentialClientApplication(
		client_id,
		authority=f'https://login.microsoftonline.com/{tenant_id}',
		client_credential=client_secret
	)

	# Acquire token
	result = app.acquire_token_for_client(scopes=scopes)

	if 'access_token' in result:
		access_token = result['access_token']
		print("Access token obtained!")
		return access_token
	else:
		print(f"Error acquiring token: {result.get('error_description')}")
		return None



def upload_to_onedrive(access_token, folder_path, file_path, one_drive_path):
	# Create the upload URL (OneDrive path)
	upload_url = f'https://graph.microsoft.com/v1.0/me/drive/root:/{one_drive_path}:/content'

	headers = {
		'Authorization': f'Bearer {access_token}',
		'Content-Type': 'application/octet-stream'
	}

	# Read file contents and upload
	with open(file_path, 'rb') as file:
		file_content = file.read()

	response = requests.put(upload_url, headers=headers, data=file_content)

	if response.status_code == 201:
		print(f"Successfully uploaded: {one_drive_path}")
	else:
		print(access_token)
		print(f"Failed to upload {one_drive_path}. Error: {response.text}")


def traverse_and_upload(access_token, local_folder, one_drive_folder):
	for root, dirs, files in os.walk(local_folder):
		for file_name in files:
			# Local file path
			file_path = os.path.join(root, file_name)
			
			# OneDrive path (mirrors local folder structure)
			relative_path = os.path.relpath(file_path, local_folder)
			one_drive_path = os.path.join(one_drive_folder, relative_path).replace("\\", "/")
			
			# Upload file
			upload_to_onedrive(access_token, local_folder, file_path, one_drive_path)
			print(f'Uploaded {file_name} to {one_drive_path}')




def main():
	access_token = auth()

	# Define the local folder and target OneDrive folder
	local_folder = "C:/GEO/Uni"
	one_drive_folder = "OneDrive_Folder"

	print(access_token)
	# Traverse the directory structure and upload files
	traverse_and_upload(access_token, local_folder, one_drive_folder)

main()