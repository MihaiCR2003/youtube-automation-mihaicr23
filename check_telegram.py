"""
Verifica daca a venit o comanda noua /video pe Telegram si, daca da, genereaza
si posteaza imediat acel video, ignorand programul fix de 4 ori/zi.

Ruleaza periodic prin cron (vezi .github/workflows/telegram.yml, la fiecare 5 minute).
"""
from main import genereaza_si_posteaza
from src.telegram_bot import citeste_comenzi_noi, trimite_mesaj


def main():
    for idee in citeste_comenzi_noi():
        try:
            genereaza_si_posteaza("short", idee_manuala=idee)
        except Exception as eroare:
            trimite_mesaj(f"❌ Eroare la generarea video-ului pentru ideea „{idee}”: {eroare}")


if __name__ == "__main__":
    main()
