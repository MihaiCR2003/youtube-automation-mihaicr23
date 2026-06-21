"""
Asambleaza video-ul final: imagini AI generate pe baza scenelor din script,
voiceover-ul deja generat (Etapa 2) si subtitrari sincronizate pe cuvinte.
"""
import os
import random
import re
import tempfile
from PIL import Image
from moviepy.editor import (
    ImageClip,
    AudioFileClip,
    CompositeVideoClip,
    VideoFileClip,
    concatenate_videoclips,
)
from moviepy.video.fx.all import crop, loop

from src.images import genereaza_imagine
from src.music import adauga_muzica_fundal
from src.stock_footage import cauta_video_stock
from src.subtitles import deseneaza_subtitlu

# moviepy 1.0.3 foloseste Image.ANTIALIAS, eliminat in Pillow >= 10.
# Fara acest shim, .resize() pe clipuri (imagine SAU video) pica cu AttributeError.
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

# Sansa ca o scena sa incerce mai intai un clip video real (Pexels) inainte
# de a cadea pe o imagine generata AI - adauga variatie vizuala intre scene.
PROBABILITATE_STOCK_FOOTAGE = 0.5

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


def _adapteaza_la_rezolutie(clip, latime: int, inaltime: int):
    """Redimensioneaza si decupeaza centrat clipul (imagine sau video) ca sa umple exact (latime, inaltime), fara sa deformeze proportiile."""
    raport_tinta = latime / inaltime
    raport_clip = clip.w / clip.h
    if raport_clip > raport_tinta:
        clip = clip.resize(height=inaltime)
    else:
        clip = clip.resize(width=latime)
    return crop(clip, width=latime, height=inaltime, x_center=clip.w / 2, y_center=clip.h / 2)


def _ajusteaza_durata_clip(clip, durata: float):
    """Bucleaza clipul video daca e mai scurt decat durata ceruta, sau il taie daca e mai lung."""
    if clip.duration < durata:
        clip = loop(clip, duration=durata)
    else:
        clip = clip.subclip(0, durata)
    return clip.set_duration(durata)


def _incarca_clip_scena(scena_text: str, durata: float, latime: int, inaltime: int, cale_temp: str):
    """
    Incearca mai intai un clip video real (Pexels), cu o sansa de 50%; daca
    nu gaseste nimic relevant (sau PEXELS_API_KEY nu e setata), cade pe o
    imagine generata AI (Pollinations.ai). Returneaza un clip cu durata exacta.
    """
    if random.random() < PROBABILITATE_STOCK_FOOTAGE:
        cale_video = cale_temp + ".mp4"
        if cauta_video_stock(scena_text, cale_video, latime, inaltime):
            clip = VideoFileClip(cale_video).without_audio()
            clip = _adapteaza_la_rezolutie(clip, latime, inaltime)
            return _ajusteaza_durata_clip(clip, durata)

    cale_imagine = cale_temp + ".png"
    genereaza_imagine(scena_text, cale_imagine, latime=latime, inaltime=inaltime)
    clip = ImageClip(cale_imagine)
    clip = _adapteaza_la_rezolutie(clip, latime, inaltime)
    return clip.set_duration(durata)


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
        # 1. Pentru fiecare scena, incearca un clip stock video real, altfel genereaza o imagine AI
        clipuri_imagine = []
        for i, (scena_text, durata) in enumerate(zip(scene, durate_scene)):
            cale_temp = os.path.join(folder_temp, f"scena_{i}")
            clip = _incarca_clip_scena(scena_text, durata, latime, inaltime, cale_temp)
            clipuri_imagine.append(clip)

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
