"""
Orchestratorul principal: genereaza un video complet (idee + script + voce +
imagini + subtitrari) si il incarca pe YouTube.

Este apelat fie de workflow-urile programate per tip (short.yml / top5.yml /
long.yml), fie manual prin comenzile /short, /top5, /long din Telegram
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


def _obtine_context_trend() -> dict | None:
    """
    Preia semnalul de la YouTube (ce e in trend + ce a performat pe canalul
    nostru) pentru a inspira alegerea subiectului. E rezilient: daca API-ul de
    trend pica din orice motiv, returnam None si generarea continua normal,
    fara semnal (nu blocam producerea unui video pentru asta).
    """
    try:
        from src.trends import videouri_in_trend, propriile_video_de_top
        return {"trending": videouri_in_trend(), "proprii": propriile_video_de_top()}
    except Exception:
        return None


def _genereaza_idee_valida(tip_video: str, idee_manuala: str | None) -> dict:
    """
    Daca 'idee_manuala' e specificata (comanda manuala din Telegram), scriptul se
    genereaza direct pe baza acelei idei, ignorand anti-repetarea si trend-ul.
    Altfel, generam o idee noua: Gemini primeste semnalul de trend (ce e popular +
    ce a mers pe canalul nostru) ca inspiratie, plus lista ultimelor idei folosite
    ca sa nu le repete. 'idee_deja_folosita' e plasa de siguranta pentru cazul
    (rar) in care genereaza totusi exact aceeasi idee.
    """
    if idee_manuala:
        return genereaza_idee_si_script(tip_video, [], idee_fortata=idee_manuala)

    idei_de_evitat = ultimele_idei()
    context_trend = _obtine_context_trend()
    for _ in range(3):
        date = genereaza_idee_si_script(tip_video, idei_de_evitat, context_trend=context_trend)
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

        # 'short' e singurul format vertical; 'long' si 'top5' sunt lungi (orizontale,
        # cu intro de canal si thumbnail custom). In Supabase pastram doar 'short'/'long'
        # (coloana tip_video accepta doar aceste valori), dar titlul TOP 5 le distinge clar.
        este_lung = tip_video != "short"

        cuvinte = genereaza_voiceover(date["script_text"], cale_audio)
        construieste_video(
            date["scene"], cale_audio, cuvinte, tip_video, cale_video,
            categorie=date["categorie"], cu_intro=este_lung,
        )

        rand_db = salveaza_video(
            titlu=date["titlu"],
            idee_subiect=date["idee_subiect"],
            categorie=date["categorie"],
            script_text=date["script_text"],
            tip_video="long" if este_lung else "short",
            ora_postarii=ora_postarii,
            generat_manual=idee_manuala is not None,
        )

        video_id = uploadeaza_video(cale_video, date["titlu"], date["descriere"], date["hashtags"], tip_video)

        if este_lung:
            cale_thumbnail = os.path.join(folder_temp, "thumbnail.png")
            # Fundalul thumbnail-ului foloseste cuvintele-cheie vizuale ale primei
            # scene (prompt vizual concret), nu textul narat - imagine mai relevanta.
            prompt_fundal = date["scene"][0]["cuvinte_cheie_vizuale"]
            genereaza_thumbnail(date["titlu"], prompt_fundal, cale_thumbnail)
            seteaza_thumbnail(video_id, cale_thumbnail)

        marcheaza_postat(rand_db["id"], video_id)

    trimite_mesaj(
        f"✅ Videoclipul „{date['titlu']}” a fost creat cu succes și încărcat pe YouTube!\n"
        f"https://youtu.be/{video_id}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tip", choices=["short", "long", "top5"], required=True)
    parser.add_argument("--ora", default="")
    argumente = parser.parse_args()

    try:
        genereaza_si_posteaza(argumente.tip, ora_postarii=argumente.ora)
    except Exception as eroare:
        trimite_mesaj(f"❌ Generarea video-ului programat ({argumente.ora}) a picat: {eroare}")
        raise
