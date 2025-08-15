# contracts.md

Scopo: integrare il frontend ChatGPT-like (ora mock) con un backend FastAPI + MongoDB e con un LLM reale, mantenendo le regole d'ambiente (URL, prefix "/api", ecc.).

A. API Contracts (tutte le rotte sono prefissate con /api)
1) Salute
- GET /api/ → { message: "Hello World" }

2) Sessioni
- GET /api/sessions → 200 [{ id, title, model, createdAt, updatedAt }]
- POST /api/sessions { title?, model? } → 201 { id, title, model, createdAt, updatedAt }
- PUT /api/sessions/:id { title?, model? } → 200 { ...session }
- DELETE /api/sessions/:id → 204

3) Messaggi
- GET /api/sessions/:id/messages → 200 [{ id, sessionId, role, content, createdAt }]

4) Chat streaming (SSE)
- POST /api/chat/stream body: { sessionId: string, model: string, messages: [{ role: 'user'|'assistant'|'system', content: string }], temperature?: number }
- Response: text/event-stream. Eventi formattati come:
  data: { "type": "chunk", "delta": "stringa parziale" }
  data: { "type": "end", "messageId": "uuid" }
  data: { "type": "error", "error": "messaggio" }

Error schema (JSON): { error: { code: string, message: string } }

B. Dati mock attuali (frontend/src/mock.js)
- Sessions & messages salvati in localStorage: id, title, model, timestamps, array messages.
- mockStreamResponse(prompt, model): genera risposta finta a chunk.
Questi dati saranno sostituiti con dati reali via API; manterremo fallback mock se l'API non risponde.

C. Backend da implementare (FastAPI)
- Modelli Mongo:
  • sessions: { _id: string, title: string, model: string, createdAt: ISO, updatedAt: ISO }
  • messages: { _id: string, sessionId: string, role: 'user'|'assistant'|'system', content: string, createdAt: ISO }
- CRUD sessioni + GET messaggi.
- SSE /api/chat/stream: orchestra chiamata al provider LLM e invia chunk. Salva su Mongo i messaggi (user e assistant) al termine o progressivamente.
- Config: bind 0.0.0.0:8001 (già gestito), CORS aperto, usa MONGO_URL da backend/.env.

D. Integrazione LLM (da confermare)
Opzioni supportate via Emergent Integrations + Universal Key: OpenAI (GPT‑4o/mini), Anthropic (Claude 3.x), Google (Gemini 2.x).
- Serve: modello preferito, temperatura di default (es. 0.3), max tokens.
- Implementazione: client server-side; streaming token-by-token verso SSE.

E. Integrazione Frontend
- Rimpiazzare mockStreamResponse con fetch streaming su `${process.env.REACT_APP_BACKEND_URL}/api/chat/stream`.
- Gestire abort (AbortController), riproduzione chunk, salvataggio nel DB via server.
- Mantenere lo stato locale per UX reattiva; le sessioni non saranno più create in localStorage ma via API. Opzione: soft cache in localStorage per velocità.

F. Sicurezza/limiti
- Rate limit semplice a livello di sessione (server-side) e lunghezza messaggio.
- Sanitizzazione input.

G. Test & rollout
- Backend: usare deep_testing_backend_v2 per testare CRUD e SSE.
- Frontend: dopo integrazione, chiedere consenso per auto_frontend_testing_agent.

H. Mapping mock → reale
- createNewSession() → POST /api/sessions
- upsertSession() → PUT /api/sessions/:id
- deleteSessionById() → DELETE /api/sessions/:id
- mockStreamResponse() → POST /api/chat/stream (SSE)

Note ambientali
- Frontend usa esclusivamente import.meta.env.REACT_APP_BACKEND_URL o process.env.REACT_APP_BACKEND_URL.
- Nessun hardcode di URL/porte. Tutte le rotte hanno prefisso /api.