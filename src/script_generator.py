"""
Genereaza ideea, titlul, descrierea si scriptul complet al unui video, folosind Gemini.
"""
import json
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

from src.config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)

# gemini-3.1-flash-lite are o limita gratuita zilnica mare (~1000 cereri/zi),
# fata de doar 20/zi cat are gemini-2.5-flash - asa evitam eroarea 429 "quota exceeded"
# pentru shorts-urile frecvente (3/zi) + comenzile manuale /video.
_MODEL_IMPLICIT = "gemini-3.1-flash-lite"

# Formatul TOP 5 (10 min) ruleaza o singura data pe zi, deci isi permite un model
# mai puternic: gemini-3.1-flash-lite se opreste prea devreme (~900 cuvinte) la
# scripturile lungi, pe cand gemini-2.5-flash atinge fiabil ~1500 cuvinte. Limita
# lui de 20/zi e irelevanta la 1 video/zi.
_MODEL_DUPA_TIP = {
    "top5": "gemini-2.5-flash",
}

_NICHE_DESCRIERE = (
    "unsolved mysteries, untold stories, fascinating history, "
    "amazing curiosities and incredible real-world events"
)

# Persoana/tonul naratorului - aceeasi "voce" de canal in fiecare video, ca sa nu
# sune ca fapte seci narate generic (risc de "mass-produced content" pe YouTube).
_PERSONA = """
NARRATOR VOICE AND PERSONALITY (apply this to EVERY script):
- The narrator is mysterious and dramatic, like a storyteller revealing forbidden secrets.
- Use suspenseful pacing: build tension before reveals, use rhetorical questions
  ("But what happened next would change everything.").
- Add the narrator's own reactions/commentary woven naturally into the facts
  (e.g. "Think about that for a second.", "And here is where it gets disturbing.").
- Do NOT just list facts neutrally like an encyclopedia entry - frame the story
  through this narrator's dramatic point of view from the first sentence (the hook)
  to the last (a memorable closing line, not just trailing off).
- Never break character with stage directions, labels, or meta-commentary.
"""

# Directia de continut, calibrata pe ce a performat real pe canal: video-ul de
# top a fost un mister intunecat/ocult ("The Terrifying Secret of the Devil's
# Bible"), impins de algoritm in Shorts feed. Inclinam spre acel registru -
# DOAR la shorts (acolo a functionat formula); long/top5 raman pe tonul general.
_DIRECTIE_CONTINUT = """
CONTENT DIRECTION (what THIS channel's audience responds to most - based on REAL view data):
- The biggest hits were SPECIFIC, real, well-documented mysteries and historical events that
  actually happened, with real names/places/dates (e.g. Operation Mincemeat - "The Corpse That
  Fooled Hitler", the Eilean Mor lighthouse vanishing, the U-65 submarine, the Codex Gigas).
  STRONGLY prefer these over generic, invented-sounding "a cursed object" stories (a cursed
  painting, a cursed clock, a weeping statue) - those consistently flopped here.
- Keep the DARK, eerie, ominous mood (disappearances, sinister history, things that should not
  exist), but anchor it in a concrete REAL case the viewer could look up, never vague fiction.
- Title craft (this matters a lot): a visceral, concrete noun + a famous or relatable anchor +
  intrigue. Great: "The Corpse That Fooled Hitler", "The Ghost Lighthouse Where 3 Men Vanished".
  Weak (avoid): "The Cursed Painting", "The Forbidden Mechanism" - too vague and invented-sounding.
- Never clickbait that lies - the real story must deliver what the title promises.
"""

# Regula primei imagini (thumbnail-ul de oprire a scroll-ului) - tot doar la shorts.
_REGULA_PRIMA_IMAGINE = """- The FIRST scene's "cuvinte_cheie_vizuale" is the thumbnail the viewer sees in the
  very first second - make it an especially STRIKING, ominous, scroll-stopping image,
  ideally a dramatic face or figure (e.g. "menacing demon face close up dark",
  "shadowy hooded figure fog", "ancient skull candlelight") that matches the dark mood."""

_LUNGIME_DUPA_TIP = {
    "short": "between 130 and 160 words (for a video under 60 seconds)",
    "long": "between 2200 and 2800 words (for a 15-20 minute video)",
    "top5": "between 900 and 1100 words (for a 5-6 minute video)",
}

# Instructiuni de structura specifice formatului TOP 5 (countdown)
_REGULI_TOP5 = """
TOP 5 FORMAT (this video MUST be a countdown list):
- The "titlu" MUST start with "TOP 5 " (e.g. "TOP 5 Most Mysterious Things Found in the Ocean").
- Structure the narration as: a short gripping intro that teases the list, then a
  countdown from number 5 down to number 1, then a brief closing line.
- Clearly announce each entry in the narration ("Number 5...", "Number 4...", etc.),
  with number 1 being the most shocking/impressive of the list.
- Each entry gets several sentences: what it is, why it is mysterious/amazing, a
  vivid concrete detail. Keep the dramatic narrator voice throughout.
"""


def _construieste_semnal_trend(context_trend: dict | None) -> str:
    """Construieste sectiunea de prompt cu semnalul: ce merge ACUM in nisa + ce a mers pe canal."""
    if not context_trend:
        return ""
    hot_nisa = context_trend.get("hot_nisa") or []
    proprii = context_trend.get("proprii") or []
    if not hot_nisa and not proprii:
        return ""

    sectiuni = ["TREND & PERFORMANCE SIGNAL (use to pick a topic with proven current demand; NEVER copy a title):"]
    if proprii:
        lista = "\n".join(f"  - {t}" for t in proprii)
        sectiuni.append(
            "- Best-performing videos on THIS channel so far - lean HARD into the same kind of "
            f"subject/style, this is what already earns views here:\n{lista}"
        )
    if hot_nisa:
        lista = "\n".join(f"  - {t}" for t in hot_nisa)
        sectiuni.append(
            "- Mystery/story topics getting LOTS of views on YouTube RIGHT NOW (last ~30 days). "
            "Pick a SPECIFIC real subject in this spirit that has proven current demand, and give "
            f"it a fresh original angle (do not copy any title):\n{lista}"
        )
    return "\n".join(sectiuni) + "\n"


def _construieste_prompt(
    tip_video: str, idei_de_evitat: list[str], idee_fortata: str | None, context_trend: dict | None = None
) -> str:
    """Construieste textul (promptul) trimis catre Gemini, cu toate regulile noastre."""
    lungime = _LUNGIME_DUPA_TIP[tip_video]

    if idee_fortata:
        regula_subiect = f'- The video MUST be about this exact topic, given by the channel owner: "{idee_fortata}"'
        semnal_trend = ""  # ideea e fixata manual, nu mai folosim semnalul de trend
    else:
        idei_text = "\n".join(f"- {idee}" for idee in idei_de_evitat) or "(none yet)"
        regula_subiect = (
            "- The topic must NOT be the same as, or a close variation of, any topic in "
            f"this list of already-used topics:\n{idei_text}"
        )
        semnal_trend = _construieste_semnal_trend(context_trend)

    reguli_format = _REGULI_TOP5 if tip_video == "top5" else ""

    # Calibrarea spre intunecat/macabru + prima imagine socanta se aplica DOAR la
    # shorts (acolo a performat formula); long si top5 raman pe tonul general.
    directie_continut = _DIRECTIE_CONTINUT if tip_video == "short" else ""
    regula_prima_imagine = _REGULA_PRIMA_IMAGINE if tip_video == "short" else ""

    return f"""
You are a viral YouTube content writer for a channel about {_NICHE_DESCRIERE}.
Write everything in ENGLISH only.
{_PERSONA}
{directie_continut}
{reguli_format}
{semnal_trend}
STRICT RULES:
- Never write about weather forecasts or mundane daily-life topics.
{regula_subiect}
- The script length must be {lungime}. This is a HARD REQUIREMENT: keep writing
  enough scene entries to reach this word count. Do NOT stop early or summarize -
  expand each point with vivid detail until the total narration hits the target.
- The script must be written for voice narration (natural spoken English, no stage directions, no markdown).
- The title must be curiosity-driven and clickable, but NOT misleading or false.

CRITICAL - THE HOOK (first sentence of the script):
- The FIRST sentence is the single most important line - it decides if the viewer
  keeps watching or scrolls away in the first 3 seconds.
- It must INSTANTLY create an open curiosity loop: drop the viewer into the most
  shocking, strange or unresolved part of the story, with a concrete vivid detail.
- Start mid-action or with a jarring fact/claim - NEVER with slow throat-clearing
  like "Imagine...", "Have you ever wondered...", "Let me tell you about...",
  "In the world of...", or generic scene-setting.
- Good hook examples (style, not topic): "In 1518, hundreds of people danced
  themselves to death - and no one knows why.", "This photo was taken seconds
  before everyone in it vanished without a trace."
- Do NOT resolve the mystery in the hook - make them NEED the rest of the video.

- Break the full narration into "scene" entries in the JSON below - each entry is
  one sentence or short narrative beat, covering the ENTIRE script in order, with
  no gaps and no overlaps between entries.
- For each scene entry, "cuvinte_cheie_vizuale" must describe a LITERAL, CONCRETE,
  photographable real-world visual (objects/places/actions actually visible in
  frame, e.g. "old ship deck stormy ocean", "ancient ruins overgrown jungle",
  "waterfall aerial view") - NEVER abstract/narrative words like "mystery",
  "secret", "imagine", character names, or specific historical event names that
  can't literally be filmed today.
{regula_prima_imagine}

Respond ONLY with a valid JSON object, no markdown formatting, with this exact structure:
{{
  "idee_subiect": "short unique slug-like description of the specific topic, in English",
  "categorie": "one of: mystery, untold_story, history, curiosity, world_event",
  "titlu": "the clickable video title",
  "descriere": "a 2-3 sentence YouTube description, SEO-optimized",
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"],
  "scene": [
    {{"text": "one sentence or short beat of the narration", "cuvinte_cheie_vizuale": "2-5 literal visual keywords"}}
  ]
}}
"""


def genereaza_idee_si_script(
    tip_video: str,
    idei_de_evitat: list[str],
    idee_fortata: str | None = None,
    context_trend: dict | None = None,
) -> dict:
    """
    Cere modelului Gemini sa genereze o idee + scriptul complet.
    'tip_video' trebuie sa fie 'short', 'long' sau 'top5'.
    'idei_de_evitat' este lista ultimelor subiecte folosite (pentru anti-repetare).
    'idee_fortata' - daca e specificata (comanda manuala din Telegram), scriptul
    va fi generat exact pe baza acestei idei, ignorand anti-repetarea si trend-ul.
    'context_trend' - dict optional {"trending": [...], "proprii": [...]} cu semnal
    de la YouTube (ce e in trend + ce a performat pe canalul nostru), folosit ca
    inspiratie la alegerea subiectului (doar cand ideea NU e fixata manual).
    """
    prompt = _construieste_prompt(tip_video, idei_de_evitat, idee_fortata, context_trend)

    # Modelele "cu gandire" (gemini-2.5-flash) consuma o parte din bugetul de
    # tokeni inainte de output - ridicam plafonul ca JSON-ul lung (top5/long) sa
    # nu fie taiat la mijloc. Daca totusi vine trunchiat, reincercam o data.
    config = genai.GenerationConfig(response_mime_type="application/json", max_output_tokens=32768)

    # Lista de modele de incercat, in ordine: modelul preferat pentru acest tip,
    # apoi modelul implicit (lite) ca fallback. Daca modelul preferat e epuizat
    # (eroare 429 quota), cadem pe lite - video-ul se face oricum, doar putin mai
    # scurt. Eliminam duplicatele pastrand ordinea.
    modele = [_MODEL_DUPA_TIP.get(tip_video, _MODEL_IMPLICIT), _MODEL_IMPLICIT]
    modele = list(dict.fromkeys(modele))

    ultima_eroare = None
    for nume_model in modele:
        model = genai.GenerativeModel(nume_model)
        for _ in range(2):
            try:
                raspuns = model.generate_content(prompt, generation_config=config)
            except ResourceExhausted as eroare:
                ultima_eroare = eroare  # quota epuizata pe acest model - trecem la urmatorul
                break
            try:
                date = json.loads(raspuns.text)
            except json.JSONDecodeError as eroare:
                ultima_eroare = eroare  # raspuns trunchiat/malformat - reincercam
                continue

            # Validare minimala a campurilor obligatorii, ca sa prindem erori devreme si clar
            campuri_necesare = ["idee_subiect", "categorie", "titlu", "descriere", "hashtags", "scene"]
            if any(camp not in date for camp in campuri_necesare):
                ultima_eroare = ValueError(f"Lipsesc campuri obligatorii. Raspuns: {date}")
                continue
            if any("text" not in s or "cuvinte_cheie_vizuale" not in s for s in date["scene"]):
                ultima_eroare = ValueError(f"O scena nu are 'text'/'cuvinte_cheie_vizuale'. Raspuns: {date}")
                continue

            # script_text (textul complet, folosit pentru voiceover si salvare in Supabase)
            # se construieste din scenele individuale, ca sa nu existe doua surse de adevar.
            date["script_text"] = " ".join(scena["text"] for scena in date["scene"])
            return date

    raise RuntimeError(f"Gemini nu a returnat un JSON valid: {ultima_eroare}")
