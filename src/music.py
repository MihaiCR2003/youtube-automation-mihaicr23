"""
Adauga muzica de fundal peste voce, cu volumul redus automat (ducking),
folosind track-uri .mp3 puse manual in assets/music/ (descarcate din
YouTube Audio Library, ca sa nu existe risc de Content ID/copyright pe
canal). Daca folderul e gol, video-ul se face fara muzica (fallback sigur).
"""
import random
from pathlib import Path
from moviepy.editor import AudioFileClip, CompositeAudioClip
from moviepy.audio.fx.all import audio_loop, volumex

_FOLDER_MUZICA = Path(__file__).resolve().parent.parent / "assets" / "music"

# Cat de tare e muzica fata de voce - doar fundal subtil, vocea trebuie sa domine
VOLUM_MUZICA = 0.06

# Vocea e amplificata usor, ca sa fie clar dominanta peste muzica de fundal
VOLUM_VOCE = 1.15


def adauga_muzica_fundal(audio_voce: AudioFileClip) -> AudioFileClip:
    """
    Alege un track aleator din assets/music/, il bucleaza la durata vocii
    si il mixeaza dedesubt, cu volumul redus. Daca nu exista nicio piesa,
    returneaza vocea neschimbata.
    """
    fisiere_muzica = list(_FOLDER_MUZICA.glob("*.mp3"))
    if not fisiere_muzica:
        return audio_voce

    cale_muzica = random.choice(fisiere_muzica)
    muzica = AudioFileClip(str(cale_muzica))
    muzica = audio_loop(muzica, duration=audio_voce.duration)
    muzica = volumex(muzica, VOLUM_MUZICA)

    voce = volumex(audio_voce, VOLUM_VOCE)

    return CompositeAudioClip([muzica, voce])
