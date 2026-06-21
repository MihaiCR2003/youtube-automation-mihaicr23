"""
Citeste statisticile publice ale canalului (vizualizari, abonati, nr. video-uri)
folosind YouTube Data API v3, pentru notificarile periodice pe Telegram.
"""
from src.youtube_upload import client_youtube


def obtine_statistici_canal() -> dict:
    """Returneaza un dict cu 'subscriberCount', 'viewCount', 'videoCount' (ca string-uri)."""
    youtube = client_youtube()
    raspuns = youtube.channels().list(part="statistics", mine=True).execute()
    return raspuns["items"][0]["statistics"]
