/*
  Frontend-only mock utilities for a local ChatGPT-like experience.
  - Stores sessions/messages in localStorage
  - Provides a streaming-like generator for assistant replies
*/

export const STORAGE_KEYS = {
  sessions: "chat_sessions_v1",
  activeId: "chat_active_session_id_v1",
};

export function loadSessions() {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.sessions);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch (e) {
    console.error("Failed to load sessions", e);
    return [];
  }
}

export function saveSessions(sessions) {
  try {
    localStorage.setItem(STORAGE_KEYS.sessions, JSON.stringify(sessions));
  } catch (e) {
    console.error("Failed to save sessions", e);
  }
}

export function setActiveSessionId(id) {
  try {
    localStorage.setItem(STORAGE_KEYS.activeId, id);
  } catch (e) {
    console.error("Failed to save active session id", e);
  }
}

export function getActiveSessionId() {
  try {
    return localStorage.getItem(STORAGE_KEYS.activeId);
  } catch (e) {
    return null;
  }
}

export const defaultModels = [
  { id: "gpt-4o", label: "GPT-4o" },
  { id: "gpt-4o-mini", label: "GPT-4o mini" },
  { id: "o3-mini", label: "o3-mini" },
];

export function createNewSession({
  title = "Nuova chat",
  model = defaultModels[1].id,
} = {}) {
  const id = crypto.randomUUID();
  const now = new Date().toISOString();
  return {
    id,
    title,
    model,
    createdAt: now,
    updatedAt: now,
    messages: [],
  };
}

export function upsertSession(sessions, session) {
  const idx = sessions.findIndex((s) => s.id === session.id);
  const updated = { ...session, updatedAt: new Date().toISOString() };
  if (idx === -1) return [updated, ...sessions];
  const next = [...sessions];
  next[idx] = updated;
  // keep most recent on top
  return [next[idx], ...next.filter((s, i) => i !== idx)];
}

export function deleteSessionById(sessions, id) {
  return sessions.filter((s) => s.id !== id);
}

// Very simple mock response database for a slightly personalized feel
const cannedReplies = [
  "Certo! Ti aiuto volentieri. Ecco una spiegazione semplice e diretta.",
  "Ottima domanda. Possiamo affrontarla passo dopo passo.",
  "Ecco un esempio pratico che puoi copiare e provare subito.",
  "Riassumendo in pochi punti: 1) comprendi il problema, 2) applica la soluzione, 3) verifica i risultati.",
  "Posso anche generare una versione più concisa o più dettagliata se preferisci.",
];

function synthesizeReply(prompt) {
  const base = cannedReplies[Math.floor(Math.random() * cannedReplies.length)];
  const suffix =
    "\n\nNota: questa è una risposta mock (solo frontend) per la demo locale.";
  // lightly echo prompt topic
  const topic = prompt?.slice(0, 60) || "la tua richiesta";
  return `${base}\n\nRiferimento al tema: \"${topic}\".${suffix}`;
}

// Async generator that yields text chunks like streaming
export async function* mockStreamResponse(prompt, model = defaultModels[1].id, { signal } = {}) {
  const full = synthesizeReply(prompt);
  const words = full.split(" ");
  let chunk = "";
  for (let i = 0; i < words.length; i++) {
    if (signal?.aborted) {
      return;
    }
    chunk += (i === 0 ? "" : " ") + words[i];
    // simulate variable network/compute delay
    await new Promise((r) => setTimeout(r, 30 + Math.random() * 70));
    yield chunk;
  }
}