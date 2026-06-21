"""
Trimite notificari pe Telegram si citeste comenzi noi (/video [idee]) primite.

Folosim cereri HTTP simple catre Telegram Bot API, fara polling continuu:
scriptul ruleaza periodic prin GitHub Actions (vezi .github/workflows/telegram.yml),
nu ca un proces permanent.
"""
import requests

from src.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from src.db import get_stare, seteaza_stare

_URL_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
_CHEIE_STARE = "ultim_update_id_telegram"


def trimite_mesaj(text: str) -> None:
    """Trimite un mesaj text catre chat-ul configurat (TELEGRAM_CHAT_ID)."""
    requests.post(f"{_URL_API}/sendMessage", data={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=15)


def citeste_comenzi_noi() -> list[str]:
    """
    Verifica mesajele noi primite de bot de la ultima verificare si extrage
    ideile din comenzile de forma '/video idea text here'.
    Returneaza o lista de idei (text), una per comanda noua gasita.
    """
    ultim_id_procesat = int(get_stare(_CHEIE_STARE, "0"))

    raspuns = requests.get(
        f"{_URL_API}/getUpdates",
        params={"offset": ultim_id_procesat + 1, "timeout": 0},
        timeout=15,
    )
    raspuns.raise_for_status()
    actualizari = raspuns.json()["result"]

    idei = []
    cel_mai_mare_id = ultim_id_procesat
    for actualizare in actualizari:
        cel_mai_mare_id = max(cel_mai_mare_id, actualizare["update_id"])
        text_mesaj = actualizare.get("message", {}).get("text", "")
        if text_mesaj.startswith("/video"):
            idee = text_mesaj[len("/video"):].strip()
            if idee:
                idei.append(idee)

    if cel_mai_mare_id != ultim_id_procesat:
        seteaza_stare(_CHEIE_STARE, str(cel_mai_mare_id))

    return idei
