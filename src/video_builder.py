"""
Asambleaza video-ul final: imagini AI generate pe baza scenelor din script,
voiceover-ul deja generat (Etapa 2) si subtitrari sincronizate pe cuvinte.
"""
import os
import random
import shutil
import subprocess
import tempfile
from pathlib import Path
import imageio_ffmpeg
import numpy as np
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
from src.subtitles import deseneaza_subtitlu_karaoke

# moviepy 1.0.3 foloseste Image.ANTIALIAS, eliminat in Pillow >= 10.
# Fara acest shim, .resize() pe clipuri (imagine SAU video) pica cu AttributeError.
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

# Sansa ca o scena sa incerce mai intai un clip video real (Pexels/Pixabay)
# inainte de a cadea pe o imagine generata AI - adauga variatie vizuala si
# secvente in miscare. ~50% da un amestec echilibrat imagini AI + footage real.
# Cautarea se face pe cuvintele-cheie vizuale ale scenei (atmosferice: ceata,
# ruine, lumanari, furtuni...), iar daca nu se gaseste nimic relevant scena cade
# automat pe imagine AI - deci footage doar "cand se gaseste ceva potrivit".
PROBABILITATE_STOCK_FOOTAGE = 0.5

# Durata tranzitiei fade intre scene consecutive (secunde)
DURATA_TRANZITIE = 0.5

# Cat de mult se schimba zoom-ul (Ken Burns) pe durata unei imagini statice
ZOOM_KEN_BURNS = 1.15

# Rezolutia finala a video-ului, in functie de tip
REZOLUTII = {
    "short": (1080, 1920),  # vertical, pentru YouTube Shorts
    "long": (1920, 1080),   # orizontal, pentru video-uri normale (16:9)
    "top5": (1920, 1080),   # orizontal, pentru video-urile TOP 5 (~10 min)
}

# Folderul cu intro-ul de canal (un singur fisier video) - prepended pe
# video-urile lungi. Daca folderul e gol/lipseste, video-ul se face fara intro.
_FOLDER_INTRO = Path(__file__).resolve().parent.parent / "assets" / "video"
_EXTENSII_VIDEO = (".mp4", ".mov", ".webm", ".mkv")

# Cate cuvinte afisam simultan pe ecran intr-un grup de subtitrare.
# La shorts (karaoke) folosim grupuri mici (efect snappy, un clip per cuvant).
# La video-urile lungi folosim grupuri mai mari, tinute static mai mult timp:
# mult mai putine clipuri de compus => randare semnificativ mai rapida.
CUVINTE_PER_SUBTITRARE = 4
CUVINTE_PER_SUBTITRARE_LUNG = 7


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


def _aplica_efect_ken_burns(clip, zoom_final: float = ZOOM_KEN_BURNS):
    """
    Aplica un zoom lent si continuu pe un clip static (imagine), de la 1.0x
    la 'zoom_final' (sau invers, ales aleator) - imaginile AI nu mai stau
    complet nemiscate pe ecran, ca intr-un slideshow.
    """
    durata = clip.duration
    latime_originala, inaltime_originala = clip.size
    zoom_invers = random.random() < 0.5  # variatie: jumatate din scene fac zoom-out

    def transforma_cadru(get_frame, t):
        progres = t / durata if durata > 0 else 0
        factor = 1 + (zoom_final - 1) * (1 - progres if zoom_invers else progres)

        imagine = Image.fromarray(get_frame(t))
        latime_noua = max(latime_originala, int(latime_originala * factor))
        inaltime_noua = max(inaltime_originala, int(inaltime_originala * factor))
        imagine = imagine.resize((latime_noua, inaltime_noua), Image.LANCZOS)

        x = (latime_noua - latime_originala) // 2
        y = (inaltime_noua - inaltime_originala) // 2
        imagine = imagine.crop((x, y, x + latime_originala, y + inaltime_originala))
        return np.array(imagine)

    return clip.fl(transforma_cadru)


def _ajusteaza_durata_clip(clip, durata: float):
    """Bucleaza clipul video daca e mai scurt decat durata ceruta, sau il taie daca e mai lung."""
    if clip.duration < durata:
        clip = loop(clip, duration=durata)
    else:
        clip = clip.subclip(0, durata)
    return clip.set_duration(durata)


def _incarca_clip_scena(
    scena: dict, durata: float, latime: int, inaltime: int, cale_temp: str,
    permite_stock: bool, ken_burns: bool,
):
    """
    Daca 'permite_stock' e True, incearca mai intai un clip video real
    (Pexels), cu o sansa de 50%, cautat pe baza cuvintelor-cheie vizuale
    (NU pe textul narat, care e prea abstract pentru o cautare buna). Daca
    nu gaseste nimic relevant (sau PEXELS_API_KEY nu e setata), cade pe o
    imagine generata AI (Pollinations.ai), folosind textul complet al scenei
    ca prompt descriptiv.

    'durata' primita aici include deja bufferul pentru tranzitia fade
    (vezi DURATA_TRANZITIE in construieste_video). 'ken_burns' aplica zoom
    lent pe imaginile statice (doar la shorts - pe video-urile lungi e prea
    lent: transforma fiecare cadru cu PIL, ar dura zeci de minute pe 10+ min).

    Returneaza (clip, clip_video_brut_sau_None). 'clip_video_brut' e clipul
    VideoFileClip original (NU cel decupat/redimensionat) - trebuie inchis
    explicit cu .close() dupa randare, altfel pe Windows fisierul .mp4 ramane
    blocat de procesul ffmpeg si TemporaryDirectory pica la cleanup.
    """
    if permite_stock and random.random() < PROBABILITATE_STOCK_FOOTAGE:
        cale_video = cale_temp + ".mp4"
        if cauta_video_stock(scena["cuvinte_cheie_vizuale"], cale_video, latime, inaltime):
            # audio=False de la construire (nu .without_audio() dupa) - altfel
            # readerul audio intern ramane deschis si blocheaza fisierul pe Windows.
            clip_brut = VideoFileClip(cale_video, audio=False)
            clip = _adapteaza_la_rezolutie(clip_brut, latime, inaltime)
            clip = _ajusteaza_durata_clip(clip, durata)
            return clip, clip_brut

    cale_imagine = cale_temp + ".png"
    genereaza_imagine(scena["text"], cale_imagine, latime=latime, inaltime=inaltime)
    clip = ImageClip(cale_imagine)
    clip = _adapteaza_la_rezolutie(clip, latime, inaltime)
    clip = clip.set_duration(durata)
    if ken_burns:
        # Imaginile AI sunt statice; zoom-ul lent le da viata (filmarile stock au deja miscare).
        clip = _aplica_efect_ken_burns(clip)
    return clip, None


def _normalizeaza_loudness(cale_intrare: str, cale_iesire: str) -> None:
    """
    Normalizeaza loudness-ul audio (EBU R128, tinta -14 LUFS ca pe YouTube) cu un
    pas ffmpeg separat: re-encodam doar audio-ul, video-ul se copiaza (rapid).
    Daca ffmpeg da eroare din orice motiv, copiem fisierul nemodificat (fallback),
    ca un video sa nu pice doar din cauza normalizarii.
    """
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    comanda = [
        ffmpeg, "-y", "-i", cale_intrare,
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        cale_iesire,
    ]
    try:
        subprocess.run(comanda, check=True, capture_output=True)
    except (subprocess.CalledProcessError, OSError):
        shutil.copyfile(cale_intrare, cale_iesire)


def _incarca_intro(latime: int, inaltime: int):
    """
    Cauta primul fisier video din assets/video/ si il pregateste ca intro,
    redimensionat la rezolutia video-ului (pastrandu-i audio-ul propriu).
    Returneaza (clip, clip_brut) sau (None, None) daca nu exista niciun intro.
    """
    if not _FOLDER_INTRO.exists():
        return None, None
    fisiere = [f for f in sorted(_FOLDER_INTRO.iterdir()) if f.suffix.lower() in _EXTENSII_VIDEO]
    if not fisiere:
        return None, None

    clip_brut = VideoFileClip(str(fisiere[0]))
    clip = _adapteaza_la_rezolutie(clip_brut, latime, inaltime)
    return clip, clip_brut


def _genereaza_clipuri_subtitrare(
    cuvinte: list[dict], latime: int, inaltime: int, folder_temp: str, karaoke: bool
) -> list:
    """
    Construieste subtitrarile, afisate in grupuri de cate CUVINTE_PER_SUBTITRARE.

    Daca 'karaoke' e True (shorts): pentru fiecare cuvant generam un clip in care
    DOAR cuvantul vorbit acum e evidentiat (galben) - efect dinamic, dar costa un
    clip per cuvant.

    Daca 'karaoke' e False (video-uri lungi): un singur clip STATIC per grup (fara
    evidentiere) - de ~4 ori mai putine clipuri, esential ca randarea unui video de
    10+ minute sa nu dureze o vesnicie / sa nu depaseasca limita CI.
    """
    cuvinte_per_grup = CUVINTE_PER_SUBTITRARE if karaoke else CUVINTE_PER_SUBTITRARE_LUNG
    clipuri = []
    for index_grup, start_grup in enumerate(range(0, len(cuvinte), cuvinte_per_grup)):
        grup = cuvinte[start_grup: start_grup + cuvinte_per_grup]
        texte_grup = [c["text"] for c in grup]

        if not karaoke:
            cale_png = os.path.join(folder_temp, f"subtitlu_{index_grup}.png")
            deseneaza_subtitlu_karaoke(texte_grup, -1, latime, inaltime, cale_png)
            start = grup[0]["start"]
            sfarsit = grup[-1]["end"]
            clipuri.append(
                ImageClip(cale_png).set_start(start).set_duration(max(sfarsit - start, 0.3))
            )
            continue

        for index_in_grup, cuvant in enumerate(grup):
            cale_png = os.path.join(folder_temp, f"subtitlu_{index_grup}_{index_in_grup}.png")
            deseneaza_subtitlu_karaoke(texte_grup, index_in_grup, latime, inaltime, cale_png)

            start = cuvant["start"]
            # Cuvantul ramane evidentiat pana incepe urmatorul (sau pana la finalul lui, daca e ultimul)
            if index_in_grup + 1 < len(grup):
                sfarsit = grup[index_in_grup + 1]["start"]
            else:
                sfarsit = cuvant["end"]

            clip = ImageClip(cale_png).set_start(start).set_duration(max(sfarsit - start, 0.15))
            clipuri.append(clip)
    return clipuri


def construieste_video(
    scene_brute: list[dict],
    cale_audio: str,
    cuvinte: list[dict],
    tip_video: str,
    cale_output: str,
    cu_intro: bool = False,
) -> None:
    """
    Functia principala: primeste scenele brute (lista de {"text",
    "cuvinte_cheie_vizuale"} din src.script_generator), fisierul audio deja
    generat, lista de cuvinte cu timestamp (din src.tts.genereaza_voiceover),
    tipul de video, si scrie fisierul video final (.mp4) la 'cale_output'.
    Fiecare scena poate folosi un clip video real (stock) sau o imagine AI -
    vezi PROBABILITATE_STOCK_FOOTAGE. Daca 'cu_intro' e True si exista un intro
    in assets/video/, acesta e adaugat la inceput.

    Efectele "bogate" (subtitrari karaoke per-cuvant + zoom Ken Burns) se aplica
    DOAR la shorts, unde scriptul e scurt (~150 cuvinte) si randarea e rapida. La
    video-urile lungi (top5/long, ~1500 cuvinte) acestea ar genera mii de clipuri
    si transformari per-cadru, depasind limita de timp - acolo folosim subtitrari
    grupate statice si imagini fara zoom (dar pastram tranzitiile + stock footage).
    """
    latime, inaltime = REZOLUTII[tip_video]
    # Footage real DOAR la video-urile lungi (long/top5). Shorts-urile folosesc
    # exclusiv imagini AI - asa erau facute video-urile care au prins (100-981
    # views); footage-ul stoc in shorts-urile de mister (uneori clipuri nepotrivite,
    # ex: strazi moderne) parea sa strice retentia/distributia.
    permite_stock = tip_video != "short"
    efecte_bogate = tip_video == "short"
    audio = AudioFileClip(cale_audio)
    durata_audio = audio.duration

    numar_scene = _alege_numar_scene(tip_video, durata_audio)
    scene = _grupeaza_scene(scene_brute, numar_scene)
    durate_scene = _calculeaza_durate_scene(scene, durata_audio)

    with tempfile.TemporaryDirectory() as folder_temp:
        # 1. Pentru fiecare scena, incearca un clip stock video real, altfel genereaza o imagine AI.
        #    Crossfade-ul (compose) e SCUMP la randare (~2.6x mai lent) - il folosim doar la shorts
        #    (scurte, randare rapida). La video-urile lungi folosim taieturi simple (chain), altfel
        #    un video de 5-6 min ar dura ~1h de randat. Bufferul DURATA_TRANZITIE e necesar doar
        #    pentru crossfade (suprapunere), deci doar la shorts.
        buffer = DURATA_TRANZITIE if efecte_bogate else 0
        clipuri_imagine = []
        clipuri_video_brute = []
        for i, (scena, durata) in enumerate(zip(scene, durate_scene)):
            cale_temp = os.path.join(folder_temp, f"scena_{i}")
            clip, clip_brut = _incarca_clip_scena(
                scena, durata + buffer, latime, inaltime, cale_temp,
                permite_stock, ken_burns=efecte_bogate,
            )
            clipuri_imagine.append(clip)
            if clip_brut is not None:
                clipuri_video_brute.append(clip_brut)

        if efecte_bogate:
            # Tranzitii fade intre scene consecutive (prima scena nu are fade la intrare)
            clipuri_cu_tranzitie = [clipuri_imagine[0]] + [
                clip.crossfadein(DURATA_TRANZITIE) for clip in clipuri_imagine[1:]
            ]
            video_imagini = concatenate_videoclips(
                clipuri_cu_tranzitie, method="compose", padding=-DURATA_TRANZITIE
            )
        else:
            video_imagini = concatenate_videoclips(clipuri_imagine, method="chain")

        # 2. Genereaza clipurile de subtitrare, sincronizate pe cuvinte
        clipuri_subtitrare = _genereaza_clipuri_subtitrare(
            cuvinte, latime, inaltime, folder_temp, karaoke=efecte_bogate
        )

        # 3. Combina imaginile + subtitrarile + audio-ul (voce + muzica de fundal)
        audio_final = adauga_muzica_fundal(audio)
        video_final = CompositeVideoClip([video_imagini, *clipuri_subtitrare])
        video_final = video_final.set_audio(audio_final).set_duration(durata_audio)

        # 4. Optional: adauga intro-ul de canal la inceput (doar pe video-urile lungi)
        intro_brut = None
        if cu_intro:
            intro_clip, intro_brut = _incarca_intro(latime, inaltime)
            if intro_clip is not None:
                video_final = concatenate_videoclips([intro_clip, video_final], method="compose")

        # Shorts (scurte) - encoding de calitate; video-urile lungi - preset rapid,
        # ca encoding-ul sa nu adauge timp inutil la cele cateva minute de material.
        preset = "medium" if efecte_bogate else "veryfast"

        cale_render = os.path.join(folder_temp, "render.mp4")
        try:
            video_final.write_videofile(
                cale_render,
                fps=24,
                codec="libx264",
                audio_codec="aac",
                threads=4,
                preset=preset,
                logger=None,
            )
        finally:
            # Pe Windows, fisierele .mp4 din folder_temp raman blocate de procesul
            # ffmpeg al fiecarui VideoFileClip pana il inchidem explicit - altfel
            # TemporaryDirectory pica la cleanup cu PermissionError.
            for clip_brut in clipuri_video_brute:
                clip_brut.close()
            if intro_brut is not None:
                intro_brut.close()

        # Pas separat: normalizare de loudness (EBU R128, ~-14 LUFS ca pe YouTube),
        # pentru volum consistent intre video-uri. Re-encodam DOAR audio-ul, video-ul
        # se copiaza (rapid). Nu se poate face in write_videofile fiindca moviepy
        # copiaza stream-ul audio (conflict cu filtrul -af).
        _normalizeaza_loudness(cale_render, cale_output)
