"""
Surse de "semnal" pentru alegerea subiectelor, prin YouTube Data API (deja
configurat, scope readonly). Doua surse:
  1. Trending general pe YouTube (chart mostPopular) - ce e popular ACUM.
  2. Propriile video-uri cu cele mai multe vizualizari - ce a mers deja pe
     canalul tau (cel mai puternic semnal: dublam ce a functionat).

Aceste titluri sunt date lui Gemini ca INSPIRATIE pentru a genera o idee
originala in nisa noastra - nu pentru a copia.
"""
from src.youtube_upload import client_youtube

# Regiunea pentru trending. Continutul e in engleza, deci piata US (cea mai mare
# piata anglofona) e un proxy bun pentru ce e in trend la publicul nostru.
_REGIUNE = "US"


def videouri_in_trend(limita: int = 15) -> list[str]:
    """Returneaza titlurile video-urilor in trending general pe YouTube (regiunea _REGIUNE)."""
    youtube = client_youtube()
    raspuns = (
        youtube.videos()
        .list(part="snippet", chart="mostPopular", regionCode=_REGIUNE, maxResults=limita)
        .execute()
    )
    return [item["snippet"]["title"] for item in raspuns.get("items", [])]


def propriile_video_de_top(limita: int = 5) -> list[str]:
    """
    Returneaza titlurile celor mai vizionate video-uri create de SISTEMUL nostru.
    Filtram strict la video-urile inregistrate in Supabase, ca sa excludem orice
    continut vechi/legacy de pe canal (ex: tutoriale de joc) care ar trimite
    Gemini intr-o directie gresita. Lista e goala daca inca nu avem video-uri.
    """
    from src.db import youtube_id_uri_postate

    id_uri_proprii = youtube_id_uri_postate()
    if not id_uri_proprii:
        return []

    # videos().list accepta maxim 50 ID-uri intr-o singura cerere
    youtube = client_youtube()
    detalii = youtube.videos().list(part="snippet,statistics", id=",".join(id_uri_proprii[:50])).execute()
    cu_vizualizari = [
        (int(v["statistics"].get("viewCount", 0)), v["snippet"]["title"])
        for v in detalii.get("items", [])
    ]
    cu_vizualizari.sort(reverse=True)
    return [titlu for _, titlu in cu_vizualizari[:limita]]
