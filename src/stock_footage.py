"""
Cauta si descarca un clip video scurt si gratuit din mai multe surse stock
(Pexels + Pixabay), ca alternativa la imaginile generate AI - pentru mai
multa variatie vizuala intre scene.

Cele doua surse sunt incercate in ordine ALEATORIE; prima care gaseste un
clip relevant castiga. Daca niciuna nu are cheie API setata sau niciuna nu
gaseste nimic, scena cade inapoi pe o imagine generata AI (vezi video_builder.py).

Licenta: atat Pexels cat si Pixabay sunt royalty-free (folosire gratuita,
comerciala, fara atribuire). Eliminam oricum audio-ul clipurilor (vezi
video_builder.py), deci nu exista risc de Content ID pe muzica incorporata.
"""
import random
import requests

from src.config import PEXELS_API_KEY, PIXABAY_API_KEY

_URL_PEXELS = "https://api.pexels.com/videos/search"
_URL_PIXABAY = "https://pixabay.com/api/videos/"

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


def _descarca(url: str, cale_fisier: str) -> bool:
    """Descarca un fisier video la 'cale_fisier'. Returneaza True la succes."""
    raspuns = requests.get(url, timeout=60)
    raspuns.raise_for_status()
    with open(cale_fisier, "wb") as fisier:
        fisier.write(raspuns.content)
    return True


def _cauta_pexels(termen: str, cale_fisier: str, latime: int, inaltime: int) -> bool:
    if not PEXELS_API_KEY:
        return False
    orientare = "portrait" if inaltime > latime else "landscape"
    raspuns = requests.get(
        _URL_PEXELS,
        headers={"Authorization": PEXELS_API_KEY},
        params={"query": termen, "orientation": orientare, "per_page": 5},
        timeout=20,
    )
    raspuns.raise_for_status()
    rezultate = raspuns.json().get("videos", [])
    if not rezultate:
        return False

    video_ales = random.choice(rezultate)
    # Alegem fisierul video cu latimea cea mai apropiata de rezolutia ceruta
    fisiere = sorted(video_ales["video_files"], key=lambda f: abs(f["width"] - latime))
    return _descarca(fisiere[0]["link"], cale_fisier)


def _cauta_pixabay(termen: str, cale_fisier: str, latime: int, inaltime: int) -> bool:
    if not PIXABAY_API_KEY:
        return False
    raspuns = requests.get(
        _URL_PIXABAY,
        params={"key": PIXABAY_API_KEY, "q": termen, "per_page": 5},
        timeout=20,
    )
    raspuns.raise_for_status()
    rezultate = raspuns.json().get("hits", [])
    if not rezultate:
        return False

    video_ales = random.choice(rezultate)
    # Pixabay ofera mai multe dimensiuni in dict-ul "videos" (large/medium/small/tiny).
    # Alegem prima varianta cu latime >= rezolutia ceruta, altfel cea mai mare.
    variante = [v for v in video_ales["videos"].values() if v.get("url")]
    variante.sort(key=lambda v: v.get("width", 0))
    potrivite = [v for v in variante if v.get("width", 0) >= latime]
    aleasa = potrivite[0] if potrivite else variante[-1]
    return _descarca(aleasa["url"], cale_fisier)


def cauta_video_stock(prompt: str, cale_fisier: str, latime: int, inaltime: int) -> bool:
    """
    Cauta un videoclip relevant pentru 'prompt' din sursele disponibile
    (Pexels + Pixabay, in ordine aleatorie) si il descarca la 'cale_fisier'.
    Returneaza True daca o sursa a gasit si descarcat un clip, False altfel.
    """
    termen = _extrage_termen_cautare(prompt)
    if not termen:
        return False

    surse = [_cauta_pexels, _cauta_pixabay]
    random.shuffle(surse)
    for sursa in surse:
        try:
            if sursa(termen, cale_fisier, latime, inaltime):
                return True
        except requests.RequestException:
            # O sursa care da eroare de retea nu trebuie sa blocheze cealalta sursa
            continue
    return False
