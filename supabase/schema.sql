-- ============================================================
-- PASUL 1: Schema bazei de date Supabase
-- ============================================================
-- Cum o folosești:
-- 1. Mergi pe https://supabase.com și creează un proiect nou (gratuit).
-- 2. În meniul din stânga, deschide "SQL Editor".
-- 3. Apasă "New query", lipește tot acest fișier, apasă "Run".
-- 4. Tabela "videos" va fi creată automat cu toate coloanele necesare.
-- ============================================================

create table if not exists videos (
    id uuid primary key default gen_random_uuid(),

    -- Titlul final al videoclipului (cel încărcat pe YouTube)
    titlu text not null,

    -- Subiectul/ideea din care a fost generat scriptul (folosit pentru anti-repetare)
    idee_subiect text not null,

    -- Categoria/tema mare a ideii (mister, istorie, curiozitate, eveniment) - ajută anti-repetarea
    categorie text,

    -- Scriptul complet generat (textul narat în video) - util pentru audit/debug
    script_text text,

    -- Tip video: 'short' (sub 60s) sau 'long' (15-20 min)
    tip_video text not null check (tip_video in ('short', 'long')),

    -- Data la care a fost creat rândul în baza de date
    data_crearii timestamptz not null default now(),

    -- Ora la care VA FI / A FOST postat pe YouTube (ex: 08:00, 12:00, 16:00, 21:00)
    ora_postarii text,

    -- Dacă videoclipul a fost deja încărcat cu succes pe YouTube
    status_postat boolean not null default false,

    -- ID-ul videoclipului pe YouTube, după upload (util pentru statistici ulterioare)
    youtube_video_id text,

    -- Dacă a fost generat manual via comanda /video din Telegram
    generat_manual boolean not null default false
);

-- Index pentru căutări rapide după categorie + dată (folosit la regula anti-repetare)
create index if not exists idx_videos_categorie_data on videos (categorie, data_crearii);

-- Index pentru căutări rapide după status (ce trebuie postat încă)
create index if not exists idx_videos_status on videos (status_postat);

-- Aceasta tabela este accesata DOAR de scriptul nostru (backend), nu de
-- utilizatori publici dintr-o aplicatie web, asa ca dezactivam Row Level
-- Security (Supabase il activeaza implicit pe tabelele noi si ar bloca
-- toate operatiile facute cu cheia "publishable").
alter table videos disable row level security;


-- ============================================================
-- Tabela bot_state: o mica tabela "cheie -> valoare" folosita de botul de
-- Telegram ca sa retina ultimul mesaj procesat (ca sa nu execute de doua
-- ori aceeasi comanda /video la rulari succesive ale cron-ului).
-- ============================================================
create table if not exists bot_state (
    cheie text primary key,
    valoare text not null
);

alter table bot_state disable row level security;
