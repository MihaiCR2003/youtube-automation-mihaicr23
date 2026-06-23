"""
Trimite notificari pe Telegram si citeste comenzile manuale primite.

Comenzi suportate (fiecare optional cu o idee dupa: '/short idee aici'):
  /short  -> video scurt vertical (YouTube Shorts)
  /top5   -> video TOP 5 (5-6 min, orizontal)
  /long   -> video lung 15-20 min (orizontal)
  /video  -> alias pentru /short (compatibilitate)
Daca nu dai o idee dupa comanda, subiectul e ales automat (cu anti-repetare).

Folosim cereri HTTP simple catre Telegram Bot API, fara polling continuu:
scriptul ruleaza periodic prin GitHub Actions (vezi .github/workflows/telegram.yml),
nu ca un proces permanent.
"""
import requests

from src.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from src.db import get_stare, seteaza_stare

_URL_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
_CHEIE_STARE = "ultim_update_id_telegram"

# Comanda Telegram -> tip de video. /video ramane alias pentru /short.
_COMENZI = {
    "/short": "short",
    "/video": "short",
    "/top5": "top5",
    "/long": "long",
}


def trimite_mesaj(text: str) -> None:
    """Trimite un mesaj text catre chat-ul configurat (TELEGRAM_CHAT_ID)."""
    requests.post(f"{_URL_API}/sendMessage", data={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=15)


def citeste_comenzi_noi() -> list[tuple[str, str | None]]:
    """
    Verifica mesajele noi primite de bot de la ultima verificare si extrage
    comenzile cunoscute. Returneaza o lista de tuple (tip_video, idee),
    unde 'idee' e None daca utilizatorul nu a dat un subiect dupa comanda.
    """
    ultim_id_procesat = int(get_stare(_CHEIE_STARE, "0"))

    raspuns = requests.get(
        f"{_URL_API}/getUpdates",
        params={"offset": ultim_id_procesat + 1, "timeout": 0},
        timeout=15,
    )
    raspuns.raise_for_status()
    actualizari = raspuns.json()["result"]

    comenzi = []
    cel_mai_mare_id = ultim_id_procesat
    for actualizare in actualizari:
        cel_mai_mare_id = max(cel_mai_mare_id, actualizare["update_id"])
        text_mesaj = actualizare.get("message", {}).get("text", "").strip()
        if not text_mesaj:
            continue

        parti = text_mesaj.split(maxsplit=1)
        # In grupuri comanda poate avea sufix '@numebot' - il eliminam
        comanda = parti[0].split("@")[0].lower()
        tip = _COMENZI.get(comanda)
        if tip:
            idee = parti[1].strip() if len(parti) > 1 else None
            comenzi.append((tip, idee))

    if cel_mai_mare_id != ultim_id_procesat:
        seteaza_stare(_CHEIE_STARE, str(cel_mai_mare_id))

    return comenzi
