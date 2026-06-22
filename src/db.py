"""
Tot ce ține de citirea/scrierea în Supabase, inclusiv regula anti-repetare.
"""
from supabase import create_client, Client

from src.config import SUPABASE_URL, SUPABASE_KEY

_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def idee_deja_folosita(idee_subiect: str) -> bool:
    """
    Verifică dacă exact aceeași idee de subiect a mai fost folosită vreodată
    (interzicem repetarea EXACTĂ a unei idei, indiferent de dată).
    """
    rezultat = (
        _client.table("videos")
        .select("id")
        .eq("idee_subiect", idee_subiect)
        .execute()
    )
    return len(rezultat.data) > 0


def salveaza_video(
    titlu: str,
    idee_subiect: str,
    categorie: str,
    script_text: str,
    tip_video: str,
    ora_postarii: str,
    generat_manual: bool = False,
) -> dict:
    """Inserează un rând nou în tabela 'videos' și îl returnează."""
    rezultat = (
        _client.table("videos")
        .insert(
            {
                "titlu": titlu,
                "idee_subiect": idee_subiect,
                "categorie": categorie,
                "script_text": script_text,
                "tip_video": tip_video,
                "ora_postarii": ora_postarii,
                "generat_manual": generat_manual,
                "status_postat": False,
            }
        )
        .execute()
    )
    return rezultat.data[0]


def marcheaza_postat(video_id: str, youtube_video_id: str) -> None:
    """După un upload cu succes pe YouTube, actualizează rândul corespunzător."""
    _client.table("videos").update(
        {"status_postat": True, "youtube_video_id": youtube_video_id}
    ).eq("id", video_id).execute()


def get_stare(cheie: str, valoare_implicita: str) -> str:
    """Citeste o valoare din tabela bot_state (folosita de botul de Telegram)."""
    rezultat = _client.table("bot_state").select("valoare").eq("cheie", cheie).execute()
    if rezultat.data:
        return rezultat.data[0]["valoare"]
    return valoare_implicita


def seteaza_stare(cheie: str, valoare: str) -> None:
    """Scrie/actualizeaza o valoare in tabela bot_state."""
    _client.table("bot_state").upsert({"cheie": cheie, "valoare": valoare}).execute()


def ultimele_idei(limita: int = 20) -> list[str]:
    """Returnează ultimele idei de subiecte folosite, ca să le evităm la generare."""
    rezultat = (
        _client.table("videos")
        .select("idee_subiect")
        .order("data_crearii", desc=True)
        .limit(limita)
        .execute()
    )
    return [r["idee_subiect"] for r in rezultat.data]
