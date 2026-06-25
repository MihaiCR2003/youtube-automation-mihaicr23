"""
Genereaza un thumbnail unic pentru video-urile lungi: o imagine de fundal
generata AI (Pollinations.ai) cu aspect cinematic, peste care randam titlul
mare si lizibil, cu un degrade intunecat in partea de jos pentru contrast.
"""
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from src.images import genereaza_imagine

_CALE_FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "SAN ANDREAS.otf"
LATIME_THUMBNAIL = 1280
INALTIME_THUMBNAIL = 720

# Stil adaugat la promptul de fundal, ca thumbnail-ul sa arate ca un afis de film.
_STIL_FUNDAL = ", cinematic dramatic movie poster, high detail, moody atmospheric lighting"


def _degrade_jos(latime: int, inaltime: int) -> Image.Image:
    """Strat RGBA cu degrade de la transparent (sus) la negru (jos) - contrast pentru text."""
    strat = Image.new("RGBA", (latime, inaltime), (0, 0, 0, 0))
    pixeli = strat.load()
    start = int(inaltime * 0.45)  # degradeul incepe de la ~45% in jos
    for y in range(start, inaltime):
        alfa = int(230 * (y - start) / max(inaltime - start, 1))
        for x in range(latime):
            pixeli[x, y] = (0, 0, 0, alfa)
    return strat


def genereaza_thumbnail(titlu: str, prompt_fundal: str, cale_fisier: str) -> None:
    """Descarca o imagine de fundal cinematica si suprapune titlul video-ului."""
    genereaza_imagine(prompt_fundal + _STIL_FUNDAL, cale_fisier, latime=LATIME_THUMBNAIL, inaltime=INALTIME_THUMBNAIL)

    with Image.open(cale_fisier) as imagine_originala:
        imagine = imagine_originala.convert("RGBA").resize(
            (LATIME_THUMBNAIL, INALTIME_THUMBNAIL), Image.LANCZOS
        )

    imagine = Image.alpha_composite(imagine, _degrade_jos(LATIME_THUMBNAIL, INALTIME_THUMBNAIL)).convert("RGB")

    desen = ImageDraw.Draw(imagine)
    linii = textwrap.wrap(titlu.upper(), width=18)

    # Marime de font care se adapteaza la numarul de linii (titluri scurte = text mai mare)
    marime_font = 92 if len(linii) <= 2 else 74
    font = ImageFont.truetype(str(_CALE_FONT), marime_font)
    grosime_contur = 8

    inaltime_linie = marime_font + 18
    y = INALTIME_THUMBNAIL - (inaltime_linie * len(linii)) - 45

    for linie in linii:
        bbox = desen.textbbox((0, 0), linie, font=font, stroke_width=grosime_contur)
        x = (LATIME_THUMBNAIL - (bbox[2] - bbox[0])) / 2
        desen.text(
            (x, y), linie, font=font, fill="white",
            stroke_width=grosime_contur, stroke_fill="black",
        )
        y += inaltime_linie

    imagine.save(cale_fisier)
