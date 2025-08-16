// API client centralizzato con credenziali (cookie HttpOnly)
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || import.meta.env.REACT_APP_BACKEND_URL;
const API_BASE = `${BACKEND_URL}/api`;

const withCreds = { credentials: 'include' };

export async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`, { ...withCreds });
  if (!res.ok) throw new Error(`GET ${path} ${res.status}`);
  return res.json();
}

export async function apiJson(path, method = 'POST', body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
    ...withCreds,
  });
  if (!res.ok) throw new Error(`${method} ${path} ${res.status}`);
  return res.json();
}

export async function apiDelete(path) {
  const res = await fetch(`${API_BASE}${path}`, { method: 'DELETE', ...withCreds });
  if (!res.ok) throw new Error(`DELETE ${path} ${res.status}`);
  return true;
}

// SSE POST streaming via fetch body
export async function* apiSSE(path, body, { signal } = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
    signal,
    ...withCreds,
  });
  if (!res.ok || !res.body) throw new Error(`SSE ${path} ${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, idx).trim();
      buffer = buffer.slice(idx + 2);
      if (raw.startsWith('data:')) {
        const jsonStr = raw.slice(5).trim();
        let evt;
        try { evt = JSON.parse(jsonStr); } catch (e) { continue; }
        yield evt;
      }
    }
  }
}

export const SessionsAPI = {
  list: () => apiGet('/sessions'),
  create: (payload) => apiJson('/sessions', 'POST', payload),
  update: (id, payload) => apiJson(`/sessions/${id}`, 'PUT', payload),
  remove: (id) => apiDelete(`/sessions/${id}`),
  messages: (id) => apiGet(`/sessions/${id}/messages`),
};

export const ChatAPI = {
  stream: (payload, opts) => apiSSE('/chat/stream', payload, opts),
};

export const AuthAPI = {
  me: () => apiGet('/auth/me'),
  login: (email, password) => apiJson('/auth/login', 'POST', { email, password }),
  register: (email, password) => apiJson('/auth/register', 'POST', { email, password }),
  logout: () => apiJson('/auth/logout', 'POST', {}),
};