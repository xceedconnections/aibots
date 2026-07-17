/**
 * Always use same-origin /api proxy.
 * Works on :80 (main nginx) and :3000 (portal nginx) without exposing port 8000
 * to the public internet (often blocked on cloud firewalls like Hetzner).
 */
const API_URL = '/api'

function getToken() {
  return localStorage.getItem('aibots_token')
}

export function setToken(token) {
  localStorage.setItem('aibots_token', token)
}

export function clearToken() {
  localStorage.removeItem('aibots_token')
}

export function isLoggedIn() {
  return Boolean(getToken())
}

async function request(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  let res
  try {
    res = await fetch(`${API_URL}${path}`, { ...options, headers })
  } catch (err) {
    throw new Error(
      `Cannot reach API (${API_URL}${path}). On the server run: curl -s http://127.0.0.1:8000/health && docker logs --tail 50 aibots-api`
    )
  }

  if (res.status === 502 || res.status === 503 || res.status === 504) {
    throw new Error(
      `API gateway error (${res.status}). Is aibots-api running? On server: docker logs --tail 50 aibots-api`
    )
  }

  if (res.status === 401) {
    clearToken()
    if (!window.location.pathname.includes('/login')) {
      window.location.href = '/login'
    }
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const detail = err.detail
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail) || 'Request failed')
  }
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  login: (email, password) =>
    request('/auth/login/json', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  me: () => request('/auth/me'),
  stats: () => request('/dashboard/stats'),
  recentCalls: () => request('/dashboard/recent-calls'),
  listBots: () => request('/bots'),
  getBot: (id) => request(`/bots/${id}`),
  createBot: (data) => request('/bots', { method: 'POST', body: JSON.stringify(data) }),
  updateBot: (id, data) => request(`/bots/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteBot: (id) => request(`/bots/${id}`, { method: 'DELETE' }),
  cloneBot: (id) => request(`/bots/${id}/clone`, { method: 'POST' }),
  addQuestion: (botId, data) =>
    request(`/bots/${botId}/questions`, { method: 'POST', body: JSON.stringify(data) }),
  updateQuestion: (qid, data) =>
    request(`/bots/questions/${qid}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteQuestion: (qid) => request(`/bots/questions/${qid}`, { method: 'DELETE' }),
  addAnswer: (qid, data) =>
    request(`/bots/questions/${qid}/answers`, { method: 'POST', body: JSON.stringify(data) }),
  updateAnswer: (aid, data) =>
    request(`/bots/answers/${aid}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteAnswer: (aid) => request(`/bots/answers/${aid}`, { method: 'DELETE' }),
  startTestCall: (payload) =>
    request('/webhook/vicidial/start', { method: 'POST', body: JSON.stringify(payload) }),
  listCalls: () => request('/calls'),
}
