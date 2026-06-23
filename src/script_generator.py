"""
Genereaza ideea, titlul, descrierea si scriptul complet al unui video, folosind Gemini.
"""
import json
import google.generativeai as genai

from src.config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)

_MODEL_NAME = "gemini-3.5-flash"

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

_LUNGIME_DUPA_TIP = {
    "short": "between 130 and 160 words (for a video under 60 seconds)",
    "long": "between 2200 and 2800 words (for a 15-20 minute video)",
}


def _construieste_prompt(tip_video: str, idei_de_evitat: list[str], idee_fortata: str | None) -> str:
    """Construieste textul (promptul) trimis catre Gemini, cu toate regulile noastre."""
    lungime = _LUNGIME_DUPA_TIP[tip_video]

    if idee_fortata:
        regula_subiect = f'- The video MUST be about this exact topic, given by the channel owner: "{idee_fortata}"'
    else:
        idei_text = "\n".join(f"- {idee}" for idee in idei_de_evitat) or "(none yet)"
        regula_subiect = (
            "- The topic must NOT be the same as, or a close variation of, any topic in "
            f"this list of already-used topics:\n{idei_text}"
        )

    return f"""
You are a viral YouTube content writer for a channel about {_NICHE_DESCRIERE}.
Write everything in ENGLISH only.
{_PERSONA}
STRICT RULES:
- Never write about weather forecasts or mundane daily-life topics.
{regula_subiect}
- The script length must be {lungime}.
- The script must be written for voice narration (natural spoken English, no stage directions, no markdown).
- The title must be curiosity-driven and clickable, but NOT misleading or false.

- Break the full narration into "scene" entries in the JSON below - each entry is
  one sentence or short narrative beat, covering the ENTIRE script in order, with
  no gaps and no overlaps between entries.
- For each scene entry, "cuvinte_cheie_vizuale" must describe a LITERAL, CONCRETE,
  photographable real-world visual (objects/places/actions actually visible in
  frame, e.g. "old ship deck stormy ocean", "ancient ruins overgrown jungle",
  "waterfall aerial view") - NEVER abstract/narrative words like "mystery",
  "secret", "imagine", character names, or specific historical event names that
  can't literally be filmed today.

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
    tip_video: str, idei_de_evitat: list[str], idee_fortata: str | None = None
) -> dict:
    """
    Cere modelului Gemini sa genereze o idee + scriptul complet.
    'tip_video' trebuie sa fie 'short' sau 'long'.
    'idei_de_evitat' este lista ultimelor subiecte folosite (pentru anti-repetare).
    'idee_fortata' - daca e specificata (comanda /video din Telegram), scriptul
    va fi generat exact pe baza acestei idei, ignorand anti-repetarea.
    """
    prompt = _construieste_prompt(tip_video, idei_de_evitat, idee_fortata)

    model = genai.GenerativeModel(_MODEL_NAME)
    raspuns = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(response_mime_type="application/json"),
    )

    date = json.loads(raspuns.text)

    # Validare minimala a campurilor obligatorii, ca sa prindem erori devreme si clar
    campuri_necesare = ["idee_subiect", "categorie", "titlu", "descriere", "hashtags", "scene"]
    for camp in campuri_necesare:
        if camp not in date:
            raise ValueError(f"Gemini nu a returnat campul obligatoriu '{camp}'. Raspuns primit: {date}")
    for scena in date["scene"]:
        if "text" not in scena or "cuvinte_cheie_vizuale" not in scena:
            raise ValueError(f"O scena nu are 'text'/'cuvinte_cheie_vizuale'. Raspuns primit: {date}")

    # script_text (textul complet, folosit pentru voiceover si salvare in Supabase)
    # se construieste din scenele individuale, ca sa nu existe doua surse de adevar.
    date["script_text"] = " ".join(scena["text"] for scena in date["scene"])

    return date
