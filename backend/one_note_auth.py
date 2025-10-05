import os
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("ONENOTE_CLIENT_ID")
CLIENT_SECRET = os.getenv("ONENOTE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("ONENOTE_REDIRECT_URI")
TOKEN_URL = r"https://login.microsoftonline.com/common/oauth2/v2.0/token"

def get_access_token(auth_code: str) -> str:
    """
    使用 OAuth2 授权码换取 Access Token
    """
    data = {
        "client_id": CLIENT_ID,
        "scope": "Notes.Create Notes.ReadWrite.All",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
        "client_secret": CLIENT_SECRET
    }
    r = requests.post(TOKEN_URL, data=data)
    r.raise_for_status()
    return r.json()["access_token"]


if __name__=="__main__":
    scopes = [
        "https://graph.microsoft.com/Notes.ReadWrite",
        "https://graph.microsoft.com/User.Read",
        "offline_access"
    ]
    """
    #ONENOTE_CLIENT_ID=3WY8Q~QkIbLPv3SsPXSOlOaoTUOUsnEU61tcGdq6
    ONENOTE_CLIENT_ID=fbb89725-6792-470e-8b99-187351a6c42b
ONENOTE_CLIENT_SECRET=3WY8Q~QkIbLPv3SsPXSOlOaoTUOUsnEU61tcGdq6
c11bc5ef-3b70-4794-af19-59fe4d0c3909
ONENOTE_REDIRECT_URI=http://localhost:8000/callback
    """
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(scopes),
        "response_mode": "query"
    }
    print(f"redirect_uri:{params["redirect_uri"]}")
    print(f"scope:{params["scope"]}")

    auth_url = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?" + urlencode(params)
    print("请在浏览器打开：", auth_url)