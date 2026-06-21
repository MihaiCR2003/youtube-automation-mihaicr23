"""
Deseneaza subtitrari ca imagini PNG transparente, folosind Pillow.
Evitam TextClip din moviepy ca sa nu fim dependenti de ImageMagick
(care nu e instalat implicit pe Windows si complica testarea locala).
"""
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

_CALE_FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "Anton-Regular.ttf"


def deseneaza_subtitlu(text: str, latime_video: int, inaltime_video: int, cale_fisier: str) -> None:
    """
    Creeaza o imagine PNG transparenta de marimea video-ului, cu 'text' scris
    mare, alb cu contur negru, centrat orizontal, in partea de jos a ecranului.
    """
    marime_font = int(latime_video * 0.07)
    font = ImageFont.truetype(str(_CALE_FONT), marime_font)

    imagine = Image.new("RGBA", (latime_video, inaltime_video), (0, 0, 0, 0))
    desen = ImageDraw.Draw(imagine)

    # Impachetam textul pe maxim ~18 caractere pe linie, ca sa nu treaca de marginile ecranului
    linii = textwrap.wrap(text.upper(), width=18) or [""]

    inaltime_linie = marime_font + 14
    inaltime_totala_text = inaltime_linie * len(linii)
    y = inaltime_video - inaltime_totala_text - int(inaltime_video * 0.12)

    for linie in linii:
        bbox = desen.textbbox((0, 0), linie, font=font, stroke_width=6)
        latime_linie = bbox[2] - bbox[0]
        x = (latime_video - latime_linie) / 2
        desen.text((x, y), linie, font=font, fill="white", stroke_width=6, stroke_fill="black")
        y += inaltime_linie

    imagine.save(cale_fisier)
