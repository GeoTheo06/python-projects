import os
import msal
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'creds.env'))

CLIENT_ID = os.getenv('CLIENT_ID')
# Replace with your Azure AD app registration information
AUTHORITY_URL = f'https://login.microsoftonline.com/consumers'
SCOPES = ['User.Read', 'Files.ReadWrite']

# File to upload
file_path = r'C:\GEO\projects\Python Projects\onedrive_upload\test.txt'
file_name = os.path.basename(file_path)

# OneDrive upload URL
UPLOAD_URL = f"https://graph.microsoft.com/v1.0/me/drive/root:/Documents/{file_name}:/content"

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

# Upload file to OneDrive
def upload_file_to_onedrive():
    access_token = get_access_token()
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/octet-stream'
    }

    with open(file_path, 'rb') as file_data:
        response = requests.put(UPLOAD_URL, headers=headers, data=file_data)

    if response.status_code == 201:
        print(f"File '{file_name}' uploaded successfully to OneDrive.")
    else:
        print(f"Failed to upload file: {response.status_code} - {response.text}")

if __name__ == "__main__":
    upload_file_to_onedrive()
