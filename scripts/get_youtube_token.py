"""
Script de rulat O SINGURA DATA, LOCAL, ca sa obtii YOUTUBE_REFRESH_TOKEN.

Inainte sa rulezi acest script:
1. YOUTUBE_CLIENT_ID si YOUTUBE_CLIENT_SECRET trebuie sa fie deja in .env
   (le obtii din Google Cloud Console, vezi Pasul 4 din README).

Cum rulezi: python scripts/get_youtube_token.py

Ce se intampla:
- Se deschide o pagina in browser unde te loghezi cu contul Google
  asociat canalului tau de YouTube si confirmi accesul.
- La final, scriptul afiseaza in terminal valoarea YOUTUBE_REFRESH_TOKEN
  - copiaz-o in .env (local) si in Secrets-urile GitHub (productie).
"""
import os
import sys
from pathlib import Path

# Permite rularea scriptului direct, fara sa fie nevoie sa instalezi proiectul ca pachet
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def main():
    client_id = os.environ["YOUTUBE_CLIENT_ID"]
    client_secret = os.environ["YOUTUBE_CLIENT_SECRET"]

    config_client = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(config_client, SCOPES)
    credentiale = flow.run_local_server(port=0)

    print("\n=== Copiaza aceasta linie in .env si in Secrets-urile GitHub ===")
    print(f"YOUTUBE_REFRESH_TOKEN={credentiale.refresh_token}")


if __name__ == "__main__":
    main()
