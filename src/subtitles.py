"""
Deseneaza subtitrari ca imagini PNG transparente, folosind Pillow.
Evitam TextClip din moviepy ca sa nu fim dependenti de ImageMagick
(care nu e instalat implicit pe Windows si complica testarea locala).

Stil "karaoke": afisam un grup de cuvinte, iar cuvantul vorbit in acel
moment e evidentiat (galben, putin mai mare) - tine privirea pe ecran,
stil specific shorts-urilor virale.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

_CALE_FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "Anton-Regular.ttf"

_CULOARE_NORMALA = "white"
_CULOARE_ACTIVA = "#FFE000"  # galben, pentru cuvantul vorbit acum


def _aseaza_pe_linii(cuvinte: list[str], font, desen, latime_maxima: int) -> list[list[str]]:
    """Imparte cuvintele pe linii, fara sa depaseasca 'latime_maxima' in pixeli."""
    linii = []
    linie_curenta = []
    for cuvant in cuvinte:
        proba = " ".join(linie_curenta + [cuvant])
        bbox = desen.textbbox((0, 0), proba, font=font, stroke_width=6)
        if (bbox[2] - bbox[0]) > latime_maxima and linie_curenta:
            linii.append(linie_curenta)
            linie_curenta = [cuvant]
        else:
            linie_curenta.append(cuvant)
    if linie_curenta:
        linii.append(linie_curenta)
    return linii


def deseneaza_subtitlu_karaoke(
    cuvinte: list[str],
    index_activ: int,
    latime_video: int,
    inaltime_video: int,
    cale_fisier: str,
) -> None:
    """
    Deseneaza grupul de cuvinte cu cuvantul de la pozitia 'index_activ'
    evidentiat (galben). Daca 'index_activ' e -1, niciun cuvant nu e evidentiat.
    """
    marime_font = int(latime_video * 0.075)
    font = ImageFont.truetype(str(_CALE_FONT), marime_font)

    imagine = Image.new("RGBA", (latime_video, inaltime_video), (0, 0, 0, 0))
    desen = ImageDraw.Draw(imagine)

    cuvinte = [c.upper() for c in cuvinte]
    latime_maxima = int(latime_video * 0.88)
    linii = _aseaza_pe_linii(cuvinte, font, desen, latime_maxima) or [[""]]

    latime_spatiu = desen.textbbox((0, 0), " ", font=font, stroke_width=6)[2]
    inaltime_linie = marime_font + 16
    y = inaltime_video - inaltime_linie * len(linii) - int(inaltime_video * 0.12)

    index_global = 0
    for linie in linii:
        # Latimea totala a liniei, ca sa o centram orizontal
        latimi_cuvinte = [
            desen.textbbox((0, 0), cuvant, font=font, stroke_width=6)[2] for cuvant in linie
        ]
        latime_linie = sum(latimi_cuvinte) + latime_spatiu * (len(linie) - 1)
        x = (latime_video - latime_linie) / 2

        for cuvant, latime_cuvant in zip(linie, latimi_cuvinte):
            culoare = _CULOARE_ACTIVA if index_global == index_activ else _CULOARE_NORMALA
            desen.text((x, y), cuvant, font=font, fill=culoare, stroke_width=6, stroke_fill="black")
            x += latime_cuvant + latime_spatiu
            index_global += 1
        y += inaltime_linie

    imagine.save(cale_fisier)
