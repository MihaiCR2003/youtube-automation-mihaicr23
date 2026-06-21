"""
Genereaza imagini AI 100% gratuit folosind Pollinations.ai (nu necesita API key).
"""
import random
import urllib.parse
import requests

_BASE_URL = "https://image.pollinations.ai/prompt"


def genereaza_imagine(prompt: str, cale_fisier: str, latime: int = 1024, inaltime: int = 1024) -> None:
    """
    Descarca o imagine generata AI pe baza unui 'prompt' (text descriptiv in engleza)
    si o salveaza la 'cale_fisier'.

    Folosim un 'seed' aleator pentru ca doua prompt-uri identice sa nu produca
    mereu exact aceeasi imagine.
    """
    prompt_encodat = urllib.parse.quote(prompt)
    seed = random.randint(0, 999_999)
    url = f"{_BASE_URL}/{prompt_encodat}?width={latime}&height={inaltime}&seed={seed}&nologo=true"

    raspuns = requests.get(url, timeout=120)
    raspuns.raise_for_status()

    with open(cale_fisier, "wb") as fisier:
        fisier.write(raspuns.content)
