"""
Asambleaza video-ul final: imagini AI generate pe baza scenelor din script,
voiceover-ul deja generat (Etapa 2) si subtitrari sincronizate pe cuvinte.
"""
import os
import re
import tempfile
from PIL import Image
from moviepy.editor import (
    ImageClip,
    AudioFileClip,
    CompositeVideoClip,
    concatenate_videoclips,
)

from src.images import genereaza_imagine
from src.music import adauga_muzica_fundal
from src.subtitles import deseneaza_subtitlu

# Rezolutia finala a video-ului, in functie de tip
REZOLUTII = {
    "short": (1080, 1920),  # vertical, pentru YouTube Shorts
    "long": (1920, 1080),   # orizontal, pentru video-uri normale (16:9)
}

# Cate cuvinte afisam simultan pe ecran intr-un grup de subtitrare
CUVINTE_PER_SUBTITRARE = 4


def _imparte_in_propozitii(text: str) -> list[str]:
    """Sparge scriptul in propozitii, pe baza semnelor de punctuatie . ! ?"""
    propozitii = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in propozitii if p.strip()]


def _alege_numar_scene(tip_video: str, durata_audio: float) -> int:
    """Decide in cate scene/imagini diferite impartim video-ul."""
    if tip_video == "short":
        return max(4, min(8, round(durata_audio / 6)))
    # Pentru video-uri lungi: o imagine noua aproximativ la fiecare 14 secunde
    return max(10, round(durata_audio / 14))


def _grupeaza_propozitii_in_scene(propozitii: list[str], numar_scene: int) -> list[str]:
    """Grupeaza propozitiile in 'numar_scene' bucati, cat mai egale ca lungime de text."""
    if numar_scene >= len(propozitii):
        return propozitii

    scene = []
    propozitii_per_scena = len(propozitii) / numar_scene
    index = 0.0
    while round(index) < len(propozitii):
        bucata = propozitii[round(index): round(index + propozitii_per_scena)]
        if bucata:
            scene.append(" ".join(bucata))
        index += propozitii_per_scena
    return scene


def _calculeaza_durate_scene(scene: list[str], durata_audio: float) -> list[float]:
    """
    Imparte durata totala a audio-ului intre scene, proportional cu lungimea
    textului fiecarei scene. Ultima scena absoarbe diferenta de rotunjire,
    ca suma duratelor sa fie EXACT egala cu durata audio-ului.
    """
    lungime_totala = sum(len(s) for s in scene) or 1
    durate = [max(durata_audio * (len(s) / lungime_totala), 1.5) for s in scene]

    diferenta = durata_audio - sum(durate)
    durate[-1] = max(durate[-1] + diferenta, 0.5)
    return durate


def _genereaza_clipuri_subtitrare(cuvinte: list[dict], latime: int, inaltime: int, folder_temp: str) -> list:
    """Construieste lista de ImageClip-uri cu textul subtitrarii, sincronizate pe cuvinte."""
    clipuri = []
    for index in range(0, len(cuvinte), CUVINTE_PER_SUBTITRARE):
        grup = cuvinte[index: index + CUVINTE_PER_SUBTITRARE]
        text_grup = " ".join(c["text"] for c in grup)
        start = grup[0]["start"]
        sfarsit = grup[-1]["end"]

        cale_png = os.path.join(folder_temp, f"subtitlu_{index}.png")
        deseneaza_subtitlu(text_grup, latime, inaltime, cale_png)

        clip = ImageClip(cale_png).set_start(start).set_duration(max(sfarsit - start, 0.3))
        clipuri.append(clip)
    return clipuri


def construieste_video(
    script_text: str,
    cale_audio: str,
    cuvinte: list[dict],
    tip_video: str,
    cale_output: str,
) -> None:
    """
    Functia principala: primeste scriptul, fisierul audio deja generat, lista
    de cuvinte cu timestamp (din src.tts.genereaza_voiceover) si tipul de
    video, si scrie fisierul video final (.mp4) la 'cale_output'.
    """
    latime, inaltime = REZOLUTII[tip_video]
    audio = AudioFileClip(cale_audio)
    durata_audio = audio.duration

    propozitii = _imparte_in_propozitii(script_text)
    numar_scene = _alege_numar_scene(tip_video, durata_audio)
    scene = _grupeaza_propozitii_in_scene(propozitii, numar_scene)
    durate_scene = _calculeaza_durate_scene(scene, durata_audio)

    with tempfile.TemporaryDirectory() as folder_temp:
        # 1. Genereaza o imagine AI pentru fiecare scena si construieste clipurile video
        clipuri_imagine = []
        for i, (scena_text, durata) in enumerate(zip(scene, durate_scene)):
            cale_imagine = os.path.join(folder_temp, f"scena_{i}.png")
            genereaza_imagine(scena_text, cale_imagine, latime=latime, inaltime=inaltime)
            # Pollinations.ai poate returna imaginea la o dimensiune mai mica decat cea
            # ceruta (desi respecta proportia) - o redimensionam explicit cu Pillow
            # (NU cu .resize() din moviepy, care e incompatibil cu Pillow >= 10).
            with Image.open(cale_imagine) as imagine:
                imagine.convert("RGB").resize((latime, inaltime), Image.LANCZOS).save(cale_imagine)

            clipuri_imagine.append(ImageClip(cale_imagine).set_duration(durata))

        video_imagini = concatenate_videoclips(clipuri_imagine, method="compose")

        # 2. Genereaza clipurile de subtitrare, sincronizate pe cuvinte
        clipuri_subtitrare = _genereaza_clipuri_subtitrare(cuvinte, latime, inaltime, folder_temp)

        # 3. Combina imaginile + subtitrarile + audio-ul (voce + muzica de fundal)
        audio_final = adauga_muzica_fundal(audio)
        video_final = CompositeVideoClip([video_imagini, *clipuri_subtitrare])
        video_final = video_final.set_audio(audio_final).set_duration(durata_audio)

        video_final.write_videofile(
            cale_output,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            logger=None,
        )
