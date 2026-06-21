"""
Cauta si descarca un clip video scurt si gratuit din Pexels Video API, ca
alternativa la imaginile generate AI - pentru mai multa variatie vizuala
intre scene (reduce aspectul de "slideshow AI generic" intre video-uri).

Daca PEXELS_API_KEY nu e setata, sau Pexels nu gaseste niciun rezultat
relevant, scenele cad inapoi pe imagini generate AI (vezi video_builder.py).
"""
import random
import requests

from src.config import PEXELS_API_KEY

_URL_CAUTARE = "https://api.pexels.com/videos/search"

# Cuvinte fara valoare vizuala, eliminate de la inceputul textului scenei
# inainte de a construi termenul de cautare - altfel cautarea pe "But what
# happened next" gaseste orice clip generic, fara legatura cu subiectul.
_CUVINTE_DE_IGNORAT = {
    "the", "a", "an", "but", "and", "or", "so", "then", "now", "here", "there",
    "this", "that", "these", "those", "it", "its", "what", "when", "where",
    "imagine", "think", "picture", "consider", "yet", "still", "just", "even",
}


def _extrage_termen_cautare(text: str) -> str:
    """Elimina cuvintele de umplutura de la inceput, ca sa ajungem mai rapid la cuvinte concrete."""
    cuvinte = [c.strip(".,!?\"'") for c in text.split()]
    while cuvinte and cuvinte[0].lower() in _CUVINTE_DE_IGNORAT:
        cuvinte.pop(0)
    return " ".join(cuvinte[:6])


def cauta_video_stock(prompt: str, cale_fisier: str, latime: int, inaltime: int) -> bool:
    """
    Cauta un videoclip Pexels relevant pentru 'prompt' si il descarca la
    'cale_fisier'. Returneaza True daca a gasit si descarcat un clip,
    False daca nu exista niciun rezultat (sau cheia API nu e configurata).
    """
    if not PEXELS_API_KEY:
        return False

    termen_cautare = _extrage_termen_cautare(prompt)
    if not termen_cautare:
        return False
    orientare = "portrait" if inaltime > latime else "landscape"

    raspuns = requests.get(
        _URL_CAUTARE,
        headers={"Authorization": PEXELS_API_KEY},
        params={"query": termen_cautare, "orientation": orientare, "per_page": 5},
        timeout=20,
    )
    raspuns.raise_for_status()
    rezultate = raspuns.json().get("videos", [])
    if not rezultate:
        return False

    video_ales = random.choice(rezultate)
    # Alegem fisierul video cu latimea cea mai apropiata de rezolutia ceruta
    fisiere_video = sorted(video_ales["video_files"], key=lambda f: abs(f["width"] - latime))
    url_descarcare = fisiere_video[0]["link"]

    raspuns_fisier = requests.get(url_descarcare, timeout=60)
    raspuns_fisier.raise_for_status()
    with open(cale_fisier, "wb") as fisier:
        fisier.write(raspuns_fisier.content)

    return True
