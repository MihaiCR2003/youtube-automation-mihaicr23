# YouTube Automation (Buget 0€)

Sistem automat de generare și postare video pe YouTube (Shorts + long-form),
folosind GitHub Actions (cron), Supabase (bază de date) și Telegram (control/notificări).

## Status

Construim sistemul pe etape. Etapele bifate sunt deja funcționale în acest repo.

- [x] **Etapa 1** — Schema Supabase + structura repo
- [ ] Etapa 2 — Generare text (Gemini) + voce (edge-tts) + imagini (Pollinations.ai)
- [ ] Etapa 3 — Asamblare video (moviepy) + subtitrări sincronizate
- [ ] Etapa 4 — Upload automat pe YouTube (OAuth) + thumbnail
- [ ] Etapa 5 — Bot Telegram (`/video [idee]`, notificări) + cron GitHub Actions
- [ ] Etapa 6 — Configurare secrete pe GitHub + test end-to-end

---

## Pasul 1 — Configurare Supabase

1. Mergi pe [supabase.com](https://supabase.com) și creează un cont gratuit.
2. Creează un proiect nou (alege o regiune apropiată, ex. Europe).
3. În meniul din stânga deschide **SQL Editor** → **New query**.
4. Copiază tot conținutul fișierului [`supabase/schema.sql`](supabase/schema.sql) din acest repo, lipește-l și apasă **Run**.
   - Acest script creează tabela `videos` cu toate coloanele necesare (titlu, idee_subiect, categorie, status_postat, tip_video, etc).
5. Mergi în **Project Settings → API** și notează:
   - `Project URL` → va fi `SUPABASE_URL`
   - `anon public` key → va fi `SUPABASE_KEY`

Aceste două valori le vei pune mai târziu fie în fișierul `.env` (testare locală), fie ca Secret pe GitHub (Pasul 4, etapa 6).

## Pasul 2 — Structura repo-ului

```
.
├── .env.example          # Model pentru variabilele de mediu (NU conține valori reale)
├── .gitignore
├── requirements.txt       # Toate librăriile Python necesare
├── supabase/
│   └── schema.sql         # Schema bazei de date (Pasul 1)
├── src/
│   ├── config.py          # Citește toate secretele din variabilele de mediu
│   ├── db.py               # Funcții Supabase: salvare video, anti-repetare, etc.
│   ├── script_generator.py # (Etapa 2) Generare idee + script cu Gemini
│   ├── tts.py               # (Etapa 2) Voiceover cu edge-tts
│   ├── images.py            # (Etapa 2) Imagini cu Pollinations.ai
│   ├── video_builder.py    # (Etapa 3) Asamblare video + subtitrări
│   ├── thumbnail.py         # (Etapa 4) Generare thumbnail pentru video lung
│   ├── youtube_upload.py   # (Etapa 4) Upload pe YouTube
│   └── telegram_bot.py      # (Etapa 5) Bot Telegram
├── main.py                  # (Etapa 5) Orchestratorul principal
└── .github/
    └── workflows/
        └── main.yml         # (Etapa 5) Cron job-ul care rulează main.py
```

### Cum testezi local (opțional, dar recomandat)

```bash
python -m venv .venv
.venv\Scripts\activate        # pe Windows
pip install -r requirements.txt
copy .env.example .env         # apoi completează valorile reale în .env
```

---

*Pașii 3-6 (cod complet, upload YouTube, bot Telegram, secrete GitHub) vor fi adăugați în etapele următoare ale acestui README, pe măsură ce le implementăm.*
