"""
Trimite un reminder pe Telegram ca YOUTUBE_REFRESH_TOKEN trebuie reinnoit
manual (proiectul Google Cloud e in modul "Testing", unde token-urile
expira automat la 7 zile). Ruleaza de 2 ori/saptamana (vezi
.github/workflows/reauth_reminder.yml), ca sa nu treaca 7 zile neobservat.
"""
from src.telegram_bot import trimite_mesaj


def main():
    trimite_mesaj(
        "🔑 Reminder: YOUTUBE_REFRESH_TOKEN expira la 7 zile de la ultima generare "
        "(proiectul Google e in modul Testing).\n\n"
        "Ca sa nu pice upload-urile automate, ruleaza local:\n"
        "python scripts/get_youtube_token.py\n\n"
        "Apoi actualizeaza secretul pe GitHub:\n"
        "gh secret set YOUTUBE_REFRESH_TOKEN -R MihaiCR2003/youtube-automation-mihaicr23"
    )


if __name__ == "__main__":
    main()
