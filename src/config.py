"""
Citește toate cheile/secretele necesare din variabilele de mediu.
Local: acestea vin din fișierul .env (vezi .env.example).
Pe GitHub Actions: acestea vin din "Secrets" (configurate în Pasul 4).
"""
import os
from dotenv import load_dotenv

# Încarcă fișierul .env doar dacă există (local). Pe GitHub Actions nu există
# fișier .env, dar variabilele sunt deja setate în mediul de execuție.
load_dotenv()


def _get_required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Variabila de mediu '{name}' nu este setată. "
            f"Verifică fișierul .env (local) sau Secrets-urile din GitHub (producție)."
        )
    return value


SUPABASE_URL = _get_required("SUPABASE_URL")
SUPABASE_KEY = _get_required("SUPABASE_KEY")

GEMINI_API_KEY = _get_required("GEMINI_API_KEY")

TELEGRAM_BOT_TOKEN = _get_required("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = _get_required("TELEGRAM_CHAT_ID")

# Aceste 3 variabile sunt necesare doar de la Etapa 4 (upload pe YouTube) incolo,
# de aceea aici sunt opționale - validarea lor strictă se face în youtube_upload.py.
YOUTUBE_CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

# Câte zile trebuie să treacă înainte de a permite o idee din aceeași categorie
ZILE_MINIME_INTRE_SUBIECTE_SIMILARE = 7

# Orele fixe de postare (format 24h, ora UTC va fi calculată separat în workflow)
ORE_POSTARE = ["08:00", "12:00", "16:00", "21:00"]
