# ChatGPT Personale – Full‑stack (React + FastAPI + MongoDB)

Questo repository contiene una replica stile ChatGPT, pronta a girare in locale con:
- Frontend: React + Tailwind + shadcn/ui
- Backend: FastAPI (streaming SSE), integrazione OpenAI (token‑by‑token)
- Database: MongoDB (sessioni e messaggi persistiti)

## Caratteristiche
- UI ChatGPT‑like con sidebar conversazioni, titolo editabile, selettore modello
- Streaming token‑by‑token dalle API OpenAI (fallback mock automatico)
- Multi‑sessione con salvataggio in MongoDB
- Autenticazione email/password con JWT (cookie HttpOnly + Authorization header)
- Isolamento per utente: ogni utente vede solo le proprie chat
- CRUD sessioni, storico messaggi, copia testo, stop/rigenera, cambio password

## Requisiti
- Node + Yarn (già gestiti nell’ambiente)
- Python 3.11+
- MongoDB accessibile (usa MONGO_URL nel backend/.env)

## Configurazione
- frontend/.env: REACT_APP_BACKEND_URL (già impostato dall’ambiente)
- backend/.env: 
  - MONGO_URL="mongodb://localhost:27017"
  - DB_NAME="test_database"
  - OPENAI_API_KEY="sk-..." (opzionale; se assente usa mock)
  - SECRET_KEY="cambia-questa-chiave"

Nota: Non modificare URL/porte nei .env. Tutte le rotte backend hanno prefisso /api.

## Avvio
I servizi sono gestiti da supervisor (hot reload attivo):
- Riavvia frontend/backend: `sudo supervisorctl restart frontend` / `backend` / `all`

Accedi al frontend:
- http://localhost:3000/chat

## API principali (prefisso /api)
- Auth: POST /auth/register, POST /auth/login, POST /auth/logout, GET /auth/me, POST /auth/change-password
- Sessioni: GET/POST/PUT/DELETE /sessions
- Messaggi: GET /sessions/:id/messages
- Chat streaming: POST /chat/stream (SSE)

## Note su OpenAI
- Se OPENAI_API_KEY è presente, lo streaming usa OpenAI (gpt‑4o / gpt‑4o‑mini). In caso di quota/errore, si può abilitare fallback.

## Testing
- Backend: testato con agent dedicato (CRUD + SSE)
- Frontend: test manuali con screenshot; è possibile aggiungere test automatici su richiesta

## Licenza
Uso interno per MVP. Personalizza a piacere per distribuzione privata.