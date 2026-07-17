/**
 * Resolve API base URL at runtime from the browser location.
 * Avoids baked-in localhost and avoids portal-nginx 502 when DNS to `api` fails.
 */
function resolveApiUrl() {
  const env = (import.meta.env.VITE_API_URL || '').trim().replace(/\/$/, '')
  if (
    env &&
    !env.includes('localhost') &&
    !env.includes('127.0.0.1') &&
    !env.includes('YOUR_SERVER_IP')
  ) {
    return env
  }

  if (typeof window !== 'undefined') {
    const { protocol, hostname } = window.location
    // Direct to exposed API port (docker maps 8000:8000)
    return `${protocol}//${hostname}:8000`
  }

  return 'http://127.0.0.1:8000'
}

const API_URL = resolveApiUrl()

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
      `Cannot reach API at ${API_URL}${path}. Is aibots-api running? Try: curl ${API_URL}/health`
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
