"""
Upload automat pe YouTube folosind YouTube Data API v3.
Autentificarea se face cu un refresh_token generat O SINGURA DATA
(vezi scripts/get_youtube_token.py), asa ca scriptul principal nu
mai necesita interactiune manuala la fiecare rulare.
"""
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from src.config import YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN

_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _client_youtube():
    if not (YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET and YOUTUBE_REFRESH_TOKEN):
        raise RuntimeError(
            "Variabilele YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN "
            "nu sunt setate. Vezi Pasul 4 din README si ruleaza scripts/get_youtube_token.py."
        )
    credentiale = Credentials(
        token=None,
        refresh_token=YOUTUBE_REFRESH_TOKEN,
        client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=_SCOPES,
    )
    return build("youtube", "v3", credentials=credentiale)


def uploadeaza_video(cale_video: str, titlu: str, descriere: str, hashtags: list[str], tip_video: str) -> str:
    """
    Incarca fisierul video pe YouTube ca PUBLIC si returneaza ID-ul video-ului.
    Pentru shorts adaugam '#Shorts' in descriere, ca YouTube sa-l recunoasca ca Short.
    """
    youtube = _client_youtube()

    descriere_completa = descriere + "\n\n" + " ".join(hashtags)
    if tip_video == "short":
        descriere_completa += " #Shorts"

    corp_cerere = {
        "snippet": {
            "title": titlu,
            "description": descriere_completa,
            "tags": [h.lstrip("#") for h in hashtags],
            "categoryId": "24",  # Entertainment
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(cale_video, mimetype="video/mp4", resumable=True, chunksize=-1)
    cerere = youtube.videos().insert(part="snippet,status", body=corp_cerere, media_body=media)
    raspuns = cerere.execute()
    return raspuns["id"]


def seteaza_thumbnail(youtube_video_id: str, cale_imagine: str) -> None:
    """Seteaza un thumbnail custom pentru un video deja incarcat (folosit pentru video-urile lungi)."""
    youtube = _client_youtube()
    youtube.thumbnails().set(videoId=youtube_video_id, media_body=MediaFileUpload(cale_imagine)).execute()
