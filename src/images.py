"""
Genereaza imagini AI 100% gratuit folosind Pollinations.ai (nu necesita API key).
"""
import random
import time
import urllib.parse
import requests
from PIL import Image

_BASE_URL = "https://image.pollinations.ai/prompt"

# Cate incercari facem la generarea unei imagini inainte sa renuntam.
# Pollinations da des erori tranzitorii (conexiune inchisa, 5xx) - o singura
# imagine esuata NU trebuie sa dărâme tot video-ul (un long are ~25 imagini).
_INCERCARI = 4


def _imagine_fallback(cale_fisier: str, latime: int, inaltime: int) -> None:
    """Daca generarea AI esueaza complet, salvam un fundal simplu (gradient inchis),
    ca scena sa existe si video-ul sa nu pice din cauza unei singure imagini."""
    imagine = Image.new("RGB", (latime, inaltime))
    pixeli = imagine.load()
    for y in range(inaltime):
        t = y / max(inaltime - 1, 1)
        culoare = (int(15 + 25 * t), int(20 + 30 * t), int(35 + 45 * t))
        for x in range(latime):
            pixeli[x, y] = culoare
    imagine.save(cale_fisier)


def genereaza_imagine(prompt: str, cale_fisier: str, latime: int = 1024, inaltime: int = 1024) -> None:
    """
    Descarca o imagine generata AI pe baza unui 'prompt' (text descriptiv in engleza)
    si o salveaza la 'cale_fisier'. Reincearca de cateva ori la erori tranzitorii;
    daca toate incercarile esueaza, salveaza un fundal simplu (fallback) ca video-ul
    sa nu pice din cauza unei singure imagini.

    Folosim un 'seed' aleator pentru ca doua prompt-uri identice sa nu produca
    mereu exact aceeasi imagine.
    """
    prompt_encodat = urllib.parse.quote(prompt)

    for incercare in range(_INCERCARI):
        seed = random.randint(0, 999_999)
        url = f"{_BASE_URL}/{prompt_encodat}?width={latime}&height={inaltime}&seed={seed}&nologo=true"
        try:
            raspuns = requests.get(url, timeout=120)
            raspuns.raise_for_status()
            with open(cale_fisier, "wb") as fisier:
                fisier.write(raspuns.content)
            return
        except requests.RequestException:
            if incercare < _INCERCARI - 1:
                time.sleep(3 * (incercare + 1))  # backoff progresiv: 3s, 6s, 9s

    _imagine_fallback(cale_fisier, latime, inaltime)
