// API client centralizzato con supporto token (Authorization) e cookie
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || import.meta.env.REACT_APP_BACKEND_URL;
const API_BASE = `${BACKEND_URL}/api`;

const withCreds = { credentials: 'include' };

function getToken() {
  try { return localStorage.getItem('auth_token') || null; } catch { return null; }
}

function authHeaders() {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

async function parseOrText(res) {
  try { return await res.json(); } catch { return { detail: res.statusText }; }
}

export async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`, { ...withCreds, headers: { ...authHeaders() } });
  if (!res.ok) {
    const data = await parseOrText(res);
    throw new Error(data.detail || `GET ${path} ${res.status}`);
  }
  return res.json();
}

export async function apiJson(path, method = 'POST', body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body || {}),
    ...withCreds,
  });
  if (!res.ok) {
    const data = await parseOrText(res);
    throw new Error(data.detail || `${method} ${path} ${res.status}`);
  }
  return res.json();
}

export async function apiDelete(path) {
  const res = await fetch(`${API_BASE}${path}`, { method: 'DELETE', ...withCreds, headers: { ...authHeaders() } });
  if (!res.ok) {
    const data = await parseOrText(res);
    throw new Error(data.detail || `DELETE ${path} ${res.status}`);
  }
  return true;
}

export async function* apiSSE(path, body, { signal } = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body || {}),
    signal,
    ...withCreds,
  });
  if (!res.ok || !res.body) {
    const data = await parseOrText(res);
    throw new Error(data.detail || `SSE ${path} ${res.status}`);
  }
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
  changePassword: (currentPassword, newPassword) => apiJson('/auth/change-password', 'POST', { currentPassword, newPassword }),
};