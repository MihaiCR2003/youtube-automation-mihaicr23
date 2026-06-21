# YouTube Automation (Buget 0€)

Sistem automat de generare și postare video pe YouTube (Shorts + long-form),
folosind GitHub Actions (cron), Supabase (bază de date) și Telegram (control/notificări).

## Status

Construim sistemul pe etape. Etapele bifate sunt deja funcționale în acest repo.

- [x] **Etapa 1** — Schema Supabase + structura repo
- [x] **Etapa 2** — Generare text (Gemini) + voce (edge-tts) + imagini (Pollinations.ai)
- [x] **Etapa 3** — Asamblare video (moviepy) + subtitrări sincronizate
- [x] **Etapa 4** — Upload automat pe YouTube (OAuth) + thumbnail
- [x] **Etapa 5** — Bot Telegram (`/video [idee]`, notificări) + cron GitHub Actions
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

## Pasul 4 — Configurare YouTube Data API v3 (upload automat)

1. Mergi pe [console.cloud.google.com](https://console.cloud.google.com/) și autentifică-te cu **contul Google asociat canalului tău de YouTube**.
2. Creează un proiect nou (ex: `youtube-automation`).
3. În meniu: **APIs & Services → Library** → caută `YouTube Data API v3` → **Enable**.
4. **APIs & Services → OAuth consent screen**:
   - User type: **External**
   - Completează numele aplicației și email-ul de contact (orice valori, sunt doar pentru tine)
   - La secțiunea **Test users**, adaugă adresa ta de Gmail (a canalului) — **obligatoriu**, altfel autorizarea va fi blocată
   - Poți lăsa aplicația în modul **Testing** — e suficient pentru uz personal
5. **APIs & Services → Credentials → Create Credentials → OAuth client ID**:
   - Application type: **Desktop app**
   - Apasă **Create** → vei vedea `Client ID` și `Client Secret` → pune-le în `.env` ca `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET`
6. Local, în terminal, rulează:
   ```bash
   python scripts/get_youtube_token.py
   ```
   - Se deschide browserul → loghează-te cu contul canalului → confirmă accesul.
   - Vei vedea un avertisment **"Google hasn't verified this app"** — e normal pentru aplicații proprii în modul Testing. Apasă **Advanced → Go to [app] (unsafe)** și continuă.
   - În terminal va apărea linia `YOUTUBE_REFRESH_TOKEN=...` → copiaz-o în `.env`.

Module de cod adăugate la această etapă:
- [`src/youtube_upload.py`](src/youtube_upload.py) — `uploadeaza_video()` (upload public) și `seteaza_thumbnail()`
- [`src/thumbnail.py`](src/thumbnail.py) — generează coperta pentru video-urile lungi (imagine AI + titlu suprapus)
- [`scripts/get_youtube_token.py`](scripts/get_youtube_token.py) — rulează-l o singură dată ca să obții refresh token-ul

---

## Pasul 5 — Bot Telegram + automatizare completă (GitHub Actions)

Module de cod adăugate la această etapă:
- [`main.py`](main.py) — orchestratorul: generează idee+script+voce+imagini+video și îl încarcă pe YouTube
- [`src/telegram_bot.py`](src/telegram_bot.py) — trimite notificări și citește comenzile `/video [idee]`
- [`check_telegram.py`](check_telegram.py) — verifică periodic comenzi noi pe Telegram (rulat de `telegram.yml`)
- [`src/youtube_stats.py`](src/youtube_stats.py) + [`stats.py`](stats.py) — trimite zilnic statisticile canalului
- [`.github/workflows/main.yml`](.github/workflows/main.yml) — cron la 08:00 / 12:00 / 16:00 (shorts) și 21:00 (long), ora României
- [`.github/workflows/telegram.yml`](.github/workflows/telegram.yml) — verifică comenzi noi la fiecare 5 minute
- [`.github/workflows/stats.yml`](.github/workflows/stats.yml) — trimite statisticile o dată pe zi

**Notă despre ora de vară/iarnă:** cron-ul GitHub Actions rulează fix în UTC și nu se ajustează automat. Orele din `main.yml` sunt calculate pentru ora de vară a României (UTC+3); iarna, postările vor fi cu o oră mai târziu decât cele dorite (09:00/13:00/17:00/22:00 în loc de 08:00/12:00/16:00/21:00). E o limitare cunoscută, acceptabilă pentru acest proiect.

**Notă despre scope YouTube:** am extins permisiunile OAuth cu `youtube.readonly` (necesar pentru statistici). Dacă ai generat `YOUTUBE_REFRESH_TOKEN` înainte de această etapă, trebuie să rulezi din nou `python scripts/get_youtube_token.py`.

---

*Pasul 6 (configurare Secrets pe GitHub, activare workflow-uri) va fi adăugat în etapa următoare.*
