"""
Genereaza fisierul audio (voiceover) folosind edge-tts (Microsoft Edge TTS, gratuit)
si extrage timestamp-ul fiecarui cuvant, necesar pentru sincronizarea subtitrarilor
in Etapa 3 (asamblarea video-ului).
"""
import asyncio
import edge_tts

# Voce masculina engleza (SUA), grava si autoritara - se potriveste tonului
# intunecat/mister al canalului. Lista completa: "edge-tts --list-voices".
VOCE = "en-US-ChristopherNeural"

# Ritm putin mai lent, pentru gravitate/suspans la naratiunea dramatica.
RITM = "-5%"


async def _genereaza_async(text: str, cale_audio: str) -> list[dict]:
    """Varianta asincrona (edge-tts functioneaza nativ async)."""
    # 'boundary' trebuie setat explicit pe WordBoundary, altfel edge-tts (v7+)
    # trimite doar evenimente la nivel de propozitie, nu de cuvant.
    comunicare = edge_tts.Communicate(text, VOCE, rate=RITM, boundary="WordBoundary")
    cuvinte = []

    with open(cale_audio, "wb") as fisier_audio:
        async for fragment in comunicare.stream():
            if fragment["type"] == "audio":
                fisier_audio.write(fragment["data"])
            elif fragment["type"] == "WordBoundary":
                # 'offset' si 'duration' vin in unitati de 100 nanosecunde.
                # Impartim la 10_000_000 ca sa obtinem secunde (float).
                cuvinte.append(
                    {
                        "text": fragment["text"],
                        "start": fragment["offset"] / 10_000_000,
                        "end": (fragment["offset"] + fragment["duration"]) / 10_000_000,
                    }
                )

    return cuvinte


def genereaza_voiceover(text: str, cale_audio: str) -> list[dict]:
    """
    Creeaza fisierul audio (mp3) la 'cale_audio' si returneaza lista de cuvinte
    cu timpii lor exacti (start/end in secunde) - folosita mai tarziu pentru subtitrari.
    """
    return asyncio.run(_genereaza_async(text, cale_audio))
