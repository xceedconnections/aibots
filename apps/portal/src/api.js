// Direct API (:8000) or same-origin nginx prefix (/api)
const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

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

  const res = await fetch(`${API_URL}${path}`, { ...options, headers })
  if (res.status === 401) {
    clearToken()
    if (!window.location.pathname.includes('/login')) {
      window.location.href = '/login'
    }
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
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
