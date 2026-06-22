"""
Orchestratorul principal: genereaza un video complet (idee + script + voce +
imagini + subtitrari) si il incarca pe YouTube.

Este apelat fie de cron-ul programat la cele 4 ore fixe (vezi
.github/workflows/main.yml), fie manual prin comanda /video din Telegram
(vezi check_telegram.py).
"""
import argparse
import os
import tempfile

from src.db import (
    idee_deja_folosita,
    marcheaza_postat,
    salveaza_video,
    ultimele_idei,
)
from src.script_generator import genereaza_idee_si_script
from src.telegram_bot import trimite_mesaj
from src.thumbnail import genereaza_thumbnail
from src.tts import genereaza_voiceover
from src.video_builder import construieste_video
from src.youtube_upload import seteaza_thumbnail, uploadeaza_video


def _genereaza_idee_valida(tip_video: str, idee_manuala: str | None) -> dict:
    """
    Daca 'idee_manuala' e specificata (comanda /video), scriptul se genereaza
    direct pe baza acelei idei, ignorand anti-repetarea.
    Altfel, generam o idee noua: Gemini primeste lista ultimelor idei deja
    folosite (in prompt) ca sa evite sa le repete, iar 'idee_deja_folosita'
    e doar o plasa de siguranta pentru cazul (rar) in care genereaza totusi
    exact aceeasi idee. NU blocam categoria intreaga (mystery/history/etc.) -
    cu doar 5 categorii posibile si 4 video-uri/zi, un cooldown de 7 zile pe
    categorie ar bloca aproape mereu totul, fortand retry-uri care epuizeaza
    rapid cota gratuita Gemini (20 cereri/zi).
    """
    if idee_manuala:
        return genereaza_idee_si_script(tip_video, [], idee_fortata=idee_manuala)

    idei_de_evitat = ultimele_idei()
    for _ in range(3):
        date = genereaza_idee_si_script(tip_video, idei_de_evitat)
        if not idee_deja_folosita(date["idee_subiect"]):
            return date

    raise RuntimeError("Nu am putut genera o idee noua, originala, dupa 3 incercari.")


def genereaza_si_posteaza(tip_video: str, ora_postarii: str = "", idee_manuala: str | None = None) -> None:
    """Genereaza video-ul complet si il incarca PUBLIC pe YouTube."""
    trimite_mesaj("⚡ Generarea videoclipului a început...")

    date = _genereaza_idee_valida(tip_video, idee_manuala)

    with tempfile.TemporaryDirectory() as folder_temp:
        cale_audio = os.path.join(folder_temp, "voce.mp3")
        cale_video = os.path.join(folder_temp, "video.mp4")

        cuvinte = genereaza_voiceover(date["script_text"], cale_audio)
        construieste_video(
            date["scene"], cale_audio, cuvinte, tip_video, cale_video, categorie=date["categorie"]
        )

        rand_db = salveaza_video(
            titlu=date["titlu"],
            idee_subiect=date["idee_subiect"],
            categorie=date["categorie"],
            script_text=date["script_text"],
            tip_video=tip_video,
            ora_postarii=ora_postarii,
            generat_manual=idee_manuala is not None,
        )

        video_id = uploadeaza_video(cale_video, date["titlu"], date["descriere"], date["hashtags"], tip_video)

        if tip_video == "long":
            cale_thumbnail = os.path.join(folder_temp, "thumbnail.png")
            genereaza_thumbnail(date["titlu"], date["script_text"][:200], cale_thumbnail)
            seteaza_thumbnail(video_id, cale_thumbnail)

        marcheaza_postat(rand_db["id"], video_id)

    trimite_mesaj(
        f"✅ Videoclipul „{date['titlu']}” a fost creat cu succes și încărcat pe YouTube!\n"
        f"https://youtu.be/{video_id}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tip", choices=["short", "long"], required=True)
    parser.add_argument("--ora", default="")
    argumente = parser.parse_args()

    try:
        genereaza_si_posteaza(argumente.tip, ora_postarii=argumente.ora)
    except Exception as eroare:
        trimite_mesaj(f"❌ Generarea video-ului programat ({argumente.ora}) a picat: {eroare}")
        raise
