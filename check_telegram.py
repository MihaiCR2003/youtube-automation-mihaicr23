"""
Verifica daca au venit comenzi manuale pe Telegram (/short, /top5, /long, /video)
si, daca da, genereaza si posteaza imediat acel video, ignorand programul fix.

Ruleaza periodic prin cron (vezi .github/workflows/telegram.yml, la fiecare 5 minute).
"""
from main import genereaza_si_posteaza
from src.telegram_bot import citeste_comenzi_noi, trimite_mesaj


def main():
    for tip_video, idee in citeste_comenzi_noi():
        try:
            genereaza_si_posteaza(tip_video, ora_postarii="manual", idee_manuala=idee)
        except Exception as eroare:
            descriere = f"„{idee}”" if idee else "(subiect automat)"
            trimite_mesaj(f"❌ Eroare la /{tip_video} {descriere}: {eroare}")


if __name__ == "__main__":
    main()
