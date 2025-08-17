# ChatGPT Personale – Full‑stack (React + FastAPI + MongoDB)

Questo repository contiene una replica stile ChatGPT, pronta a girare in locale con:
- Frontend: React + Tailwind + shadcn/ui
- Backend: FastAPI (streaming SSE), integrazione OpenAI (token‑by‑token)
- Database: MongoDB (sessioni e messaggi persistiti)

## Deploy nel modo più facile (1 provider, senza terminale)

Usa Render Blueprint (un click per frontend + backend):

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

Passi:
1. Carica il repo su GitHub.
2. Vai su https://render.com/deploy e seleziona il tuo repo: il file `render.yaml` creerà automaticamente:
   - Web Service: backend FastAPI
   - Static Site: frontend React
3. Imposta le variabili:
   - Nel backend: `MONGO_URL` (Atlas), `DB_NAME` (es. chatdb), `OPENAI_API_KEY`, `SECRET_KEY` (già generata), `CORS_ORIGINS` = URL frontend dopo deploy
   - Nel frontend: `REACT_APP_BACKEND_URL` = URL del backend dopo deploy
4. Fai Deploy. Otterrai 2 URL pubblici (frontend e backend). Apri il frontend su iPhone/iPad/ovunque.

Nota: dopo il primo deploy, aggiorna `CORS_ORIGINS` del backend con l’URL del frontend e ridistribuisci.

## Caratteristiche
- UI ChatGPT‑like con sidebar conversazioni, titolo editabile, selettore modello
- Streaming token‑by‑token dalle API OpenAI (fallback mock automatico)
- Multi‑sessione con salvataggio in MongoDB
- Autenticazione email/password con JWT (cookie HttpOnly + Authorization header)
- Isolamento per utente: ogni utente vede solo le proprie chat
- CRUD sessioni, storico messaggi, copia testo, stop/rigenera, cambio password

## Requisiti locali (opzionale)
- Node + Yarn
- Python 3.11+
- MongoDB (Atlas consigliato anche in locale)

## Configurazione env
- frontend/.env: REACT_APP_BACKEND_URL
- backend/.env: MONGO_URL, DB_NAME, OPENAI_API_KEY, SECRET_KEY, CORS_ORIGINS

## Avvio locale (già gestito qui dall’ambiente)
- Supervisor: `sudo supervisorctl restart frontend` / `backend` / `all`
- Frontend: http://localhost:3000/chat

## API principali (prefisso /api)
- Auth: POST /auth/register, POST /auth/login, POST /auth/logout, GET /auth/me, POST /auth/change-password
- Sessioni: GET/POST/PUT/DELETE /sessions
- Messaggi: GET /sessions/:id/messages
- Chat streaming: POST /chat/stream (SSE)

## Note su OpenAI
- Se `OPENAI_API_KEY` è presente, lo streaming usa OpenAI (gpt‑4o / gpt‑4o‑mini). In caso di quota/errore, è possibile prevedere fallback.