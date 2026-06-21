"""
Trimite pe Telegram statisticile curente ale canalului (vizualizari, abonati).
Ruleaza periodic prin cron (vezi .github/workflows/stats.yml).
"""
from src.telegram_bot import trimite_mesaj
from src.youtube_stats import obtine_statistici_canal


def main():
    stats = obtine_statistici_canal()
    mesaj = (
        "📊 Statisticile canalului:\n"
        f"👁 Vizualizări totale: {stats.get('viewCount', '?')}\n"
        f"👤 Abonați: {stats.get('subscriberCount', '?')}\n"
        f"🎬 Videoclipuri: {stats.get('videoCount', '?')}"
    )
    trimite_mesaj(mesaj)


if __name__ == "__main__":
    main()
