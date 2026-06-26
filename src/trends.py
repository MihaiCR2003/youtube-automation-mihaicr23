"""
Surse de "semnal" pentru alegerea subiectelor, prin YouTube Data API (deja
configurat, scope readonly). Doua surse:
  1. Subiecte "hot" in nisa noastra: ce mistere/povesti fac MULTE vizualizari
     pe YouTube ACUM (cautare in nisa, ultimele ~30 zile). Spre deosebire de
     trending-ul general (muzica/gaming), asta e on-brand si relevant.
  2. Propriile video-uri cu cele mai multe vizualizari - ce a mers deja pe
     canalul tau (cel mai puternic semnal: dublam ce a functionat).

Aceste titluri sunt date lui Gemini ca INSPIRATIE pentru a genera o idee
originala (un unghi nou), nu pentru a copia.
"""
import random
from datetime import datetime, timedelta, timezone

from src.youtube_upload import client_youtube

# Regiunea/limba: continutul e in engleza, piata US (cea mai mare anglofona).
_REGIUNE = "US"

# Interogari de nisa (formula dark/mister care a performat). Alegem cateva
# aleator la fiecare rulare, ca sa variem semnalul si sa limitam quota
# (search costa 100 unitati/cerere; cateva/zi raman mult sub 10.000/zi).
# Interogari factuale (cuvinte ca "explained"/"documentary"/"real" inclina
# rezultatele spre continut factual, nu fictiune/fantasy in alte limbi).
_INTEROGARI_NISA = [
    "unsolved mystery explained",
    "unexplained disappearance documentary",
    "real creepy history",
    "mysterious discovery explained",
    "terrifying historical event",
    "famous unsolved case",
    "dark history true story",
]


def _curata_titlu(titlu: str) -> str | None:
    """
    Curata si filtreaza un titlu de YouTube. Returneaza titlul fara coada de
    hashtaguri, sau None daca pare irelevant (alta limba, spam de hashtaguri,
    prea scurt) - ca sa nu dam lui Gemini zgomot drept inspiratie.
    """
    curat = titlu.split("#")[0].strip()
    if len(curat) < 12:
        return None
    # Cere ca textul sa fie preponderent litere ASCII (engleza) - elimina titlurile
    # in scripturi non-latine (alte limbi) care nu ne folosesc.
    litere_ascii = sum(c.isascii() and c.isalpha() for c in curat)
    if litere_ascii < 0.6 * len(curat):
        return None
    return curat


def subiecte_hot_nisa(nr_interogari: int = 2, per_interogare: int = 10) -> list[str]:
    """
    Cauta pe YouTube ce subiecte de mister/poveste fac multe vizualizari recent
    (ultimele ~30 zile), sortate dupa numar de vizualizari. Returneaza titlurile
    curatate/filtrate - semnal "ce merge ACUM in nisa noastra". Lista poate fi
    goala daca API-ul nu raspunde (apelantul trateaza asta).
    """
    youtube = client_youtube()
    publicat_dupa = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    interogari = random.sample(_INTEROGARI_NISA, k=min(nr_interogari, len(_INTEROGARI_NISA)))

    titluri = []
    for interogare in interogari:
        raspuns = (
            youtube.search()
            .list(
                part="snippet", q=interogare, type="video", order="viewCount",
                publishedAfter=publicat_dupa, maxResults=per_interogare,
                relevanceLanguage="en", regionCode=_REGIUNE,
            )
            .execute()
        )
        for item in raspuns.get("items", []):
            curat = _curata_titlu(item["snippet"]["title"])
            if curat:
                titluri.append(curat)
    return titluri


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
