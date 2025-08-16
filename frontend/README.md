# Frontend – ChatGPT Personale

Stack: React 19, Tailwind, shadcn/ui, react-router.

Script (craco):
- `yarn start` – avvio in sviluppo
- `yarn build` – build produzione

Env: usare `REACT_APP_BACKEND_URL` per puntare al backend. Non hardcodare URL/porte.

Feature:
- Guard di rotta: /chat richiede login (/auth)
- UI chat con streaming token‑by‑token via SSE
- Menu Account (profilo, cambio password, logout)

Struttura principali:
- src/pages/Chat.jsx – interfaccia chat
- src/pages/Auth.jsx – login/registrazione
- src/context/AuthContext.jsx – stato auth
- src/lib/api.js – client API
- src/components/ui/* – componenti shadcn