"""
Genereaza un thumbnail unic pentru video-urile lungi: o imagine de fundal
generata AI (Pollinations.ai), peste care randam titlul video-ului ca text
mare si lizibil, cu un strat semi-transparent pentru contrast.
"""
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from src.images import genereaza_imagine

_CALE_FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "Anton-Regular.ttf"
LATIME_THUMBNAIL = 1280
INALTIME_THUMBNAIL = 720


def genereaza_thumbnail(titlu: str, prompt_fundal: str, cale_fisier: str) -> None:
    """Descarca o imagine de fundal relevanta si suprapune titlul video-ului."""
    genereaza_imagine(prompt_fundal, cale_fisier, latime=LATIME_THUMBNAIL, inaltime=INALTIME_THUMBNAIL)

    with Image.open(cale_fisier) as imagine_originala:
        imagine = imagine_originala.convert("RGBA").resize(
            (LATIME_THUMBNAIL, INALTIME_THUMBNAIL), Image.LANCZOS
        )

    # Strat semi-transparent negru in partea de jos, ca textul sa fie lizibil pe orice fundal
    strat_intunecat = Image.new("RGBA", imagine.size, (0, 0, 0, 0))
    desen_strat = ImageDraw.Draw(strat_intunecat)
    desen_strat.rectangle(
        [0, int(INALTIME_THUMBNAIL * 0.55), LATIME_THUMBNAIL, INALTIME_THUMBNAIL],
        fill=(0, 0, 0, 160),
    )
    imagine = Image.alpha_composite(imagine, strat_intunecat).convert("RGB")

    desen = ImageDraw.Draw(imagine)
    marime_font = 64
    font = ImageFont.truetype(str(_CALE_FONT), marime_font)
    linii = textwrap.wrap(titlu.upper(), width=22)

    inaltime_linie = marime_font + 16
    y = INALTIME_THUMBNAIL - (inaltime_linie * len(linii)) - 30

    for linie in linii:
        bbox = desen.textbbox((0, 0), linie, font=font, stroke_width=4)
        x = (LATIME_THUMBNAIL - (bbox[2] - bbox[0])) / 2
        desen.text((x, y), linie, font=font, fill="white", stroke_width=4, stroke_fill="black")
        y += inaltime_linie

    imagine.save(cale_fisier)
