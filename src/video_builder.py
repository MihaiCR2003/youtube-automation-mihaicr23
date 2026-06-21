"""
Asambleaza video-ul final: imagini AI generate pe baza scenelor din script,
voiceover-ul deja generat (Etapa 2) si subtitrari sincronizate pe cuvinte.
"""
import os
import random
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

# Stock footage real e folosit DOAR pentru aceste categorii - subiectele de
# istorie/mister/povesti vechi au nevoie de scene specifice unei epoci, pe
# care filmari reale moderne nu le pot reda (risc de anacronisme vizuale,
# ex: o cladire moderna intr-o poveste din 1587). Pentru acelea folosim
# exclusiv imagini generate AI.
CATEGORII_PERMISE_STOCK = {"world_event", "curiosity"}

# Rezolutia finala a video-ului, in functie de tip
REZOLUTII = {
    "short": (1080, 1920),  # vertical, pentru YouTube Shorts
    "long": (1920, 1080),   # orizontal, pentru video-uri normale (16:9)
}

# Cate cuvinte afisam simultan pe ecran intr-un grup de subtitrare
CUVINTE_PER_SUBTITRARE = 4


def _alege_numar_scene(tip_video: str, durata_audio: float) -> int:
    """Decide in cate scene/imagini diferite impartim video-ul."""
    if tip_video == "short":
        return max(4, min(8, round(durata_audio / 6)))
    # Pentru video-uri lungi: o imagine noua aproximativ la fiecare 14 secunde
    return max(10, round(durata_audio / 14))


def _grupeaza_scene(scene_brute: list[dict], numar_scene: int) -> list[dict]:
    """
    Grupeaza scenele "brute" primite de la Gemini (una per propozitie, fiecare
    cu propriile cuvinte-cheie vizuale) in 'numar_scene' grupuri afisate, cat
    mai egale ca lungime de text. Cuvintele-cheie vizuale ale grupului sunt
    cele ale primei propozitii din grup (de obicei cea care introduce scena).
    """
    if numar_scene >= len(scene_brute):
        return scene_brute

    grupuri = []
    propozitii_per_grup = len(scene_brute) / numar_scene
    index = 0.0
    while round(index) < len(scene_brute):
        bucata = scene_brute[round(index): round(index + propozitii_per_grup)]
        if bucata:
            grupuri.append(
                {
                    "text": " ".join(s["text"] for s in bucata),
                    "cuvinte_cheie_vizuale": bucata[0]["cuvinte_cheie_vizuale"],
                }
            )
        index += propozitii_per_grup
    return grupuri


def _calculeaza_durate_scene(scene: list[dict], durata_audio: float) -> list[float]:
    """
    Imparte durata totala a audio-ului intre scene, proportional cu lungimea
    textului fiecarei scene. Ultima scena absoarbe diferenta de rotunjire,
    ca suma duratelor sa fie EXACT egala cu durata audio-ului.
    """
    lungime_totala = sum(len(s["text"]) for s in scene) or 1
    durate = [max(durata_audio * (len(s["text"]) / lungime_totala), 1.5) for s in scene]

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


def _incarca_clip_scena(scena: dict, durata: float, latime: int, inaltime: int, cale_temp: str, permite_stock: bool):
    """
    Daca 'permite_stock' e True, incearca mai intai un clip video real
    (Pexels), cu o sansa de 50%, cautat pe baza cuvintelor-cheie vizuale
    (NU pe textul narat, care e prea abstract pentru o cautare buna). Daca
    nu gaseste nimic relevant (sau PEXELS_API_KEY nu e setata), cade pe o
    imagine generata AI (Pollinations.ai), folosind textul complet al scenei
    ca prompt descriptiv.

    Returneaza (clip, clip_video_brut_sau_None). 'clip_video_brut' e clipul
    VideoFileClip original (NU cel decupat/redimensionat) - trebuie inchis
    explicit cu .close() dupa randare, altfel pe Windows fisierul .mp4 ramane
    blocat de procesul ffmpeg si TemporaryDirectory pica la cleanup.
    """
    if permite_stock and random.random() < PROBABILITATE_STOCK_FOOTAGE:
        cale_video = cale_temp + ".mp4"
        if cauta_video_stock(scena["cuvinte_cheie_vizuale"], cale_video, latime, inaltime):
            clip_brut = VideoFileClip(cale_video).without_audio()
            clip = _adapteaza_la_rezolutie(clip_brut, latime, inaltime)
            clip = _ajusteaza_durata_clip(clip, durata)
            return clip, clip_brut

    cale_imagine = cale_temp + ".png"
    genereaza_imagine(scena["text"], cale_imagine, latime=latime, inaltime=inaltime)
    clip = ImageClip(cale_imagine)
    clip = _adapteaza_la_rezolutie(clip, latime, inaltime)
    return clip.set_duration(durata), None


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
    scene_brute: list[dict],
    cale_audio: str,
    cuvinte: list[dict],
    tip_video: str,
    cale_output: str,
    categorie: str = "",
) -> None:
    """
    Functia principala: primeste scenele brute (lista de {"text",
    "cuvinte_cheie_vizuale"} din src.script_generator), fisierul audio deja
    generat, lista de cuvinte cu timestamp (din src.tts.genereaza_voiceover),
    tipul de video si categoria, si scrie fisierul video final (.mp4) la
    'cale_output'. 'categorie' decide daca scenele pot folosi stock footage
    real (vezi CATEGORII_PERMISE_STOCK) sau doar imagini AI.
    """
    latime, inaltime = REZOLUTII[tip_video]
    permite_stock = categorie in CATEGORII_PERMISE_STOCK
    audio = AudioFileClip(cale_audio)
    durata_audio = audio.duration

    numar_scene = _alege_numar_scene(tip_video, durata_audio)
    scene = _grupeaza_scene(scene_brute, numar_scene)
    durate_scene = _calculeaza_durate_scene(scene, durata_audio)

    with tempfile.TemporaryDirectory() as folder_temp:
        # 1. Pentru fiecare scena, incearca un clip stock video real, altfel genereaza o imagine AI
        clipuri_imagine = []
        clipuri_video_brute = []
        for i, (scena, durata) in enumerate(zip(scene, durate_scene)):
            cale_temp = os.path.join(folder_temp, f"scena_{i}")
            clip, clip_brut = _incarca_clip_scena(scena, durata, latime, inaltime, cale_temp, permite_stock)
            clipuri_imagine.append(clip)
            if clip_brut is not None:
                clipuri_video_brute.append(clip_brut)

        video_imagini = concatenate_videoclips(clipuri_imagine, method="compose")

        # 2. Genereaza clipurile de subtitrare, sincronizate pe cuvinte
        clipuri_subtitrare = _genereaza_clipuri_subtitrare(cuvinte, latime, inaltime, folder_temp)

        # 3. Combina imaginile + subtitrarile + audio-ul (voce + muzica de fundal)
        audio_final = adauga_muzica_fundal(audio)
        video_final = CompositeVideoClip([video_imagini, *clipuri_subtitrare])
        video_final = video_final.set_audio(audio_final).set_duration(durata_audio)

        try:
            video_final.write_videofile(
                cale_output,
                fps=24,
                codec="libx264",
                audio_codec="aac",
                threads=4,
                logger=None,
            )
        finally:
            # Pe Windows, fisierele .mp4 din folder_temp raman blocate de procesul
            # ffmpeg al fiecarui VideoFileClip pana il inchidem explicit - altfel
            # TemporaryDirectory pica la cleanup cu PermissionError.
            for clip_brut in clipuri_video_brute:
                clip_brut.close()
