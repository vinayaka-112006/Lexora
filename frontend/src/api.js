const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '')

function apiError(message, status) {
  const error = new Error(message)
  error.status = status
  return error
}

function messageForStatus(status, operation) {
  if (operation === 'login' && status === 401) return 'Invalid email or password.'
  if (operation === 'register' && status === 409) return 'An account with this email already exists.'
  if (status === 401) return 'Your session has expired. Please sign in again.'
  if (status === 400) return 'Please check the information and try again.'
  if (status === 404) return 'This saved conversation could not be found.'
  if (status === 503) return 'The legal answer service is temporarily unavailable. Please try again later.'
  if (status === 504) return 'The request timed out. Please try again.'
  return 'Something went wrong. Please try again.'
}

async function requestJson(path, { method = 'GET', body, operation = 'request', allowArray = false } = {}) {
  let response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      credentials: 'include',
      headers: body === undefined
        ? { Accept: 'application/json' }
        : { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw apiError('Could not connect to the application service. Please try again.', 0)
  }

  if (!response.ok) throw apiError(messageForStatus(response.status, operation), response.status)

  try {
    const result = await response.json()
    if (!result || typeof result !== 'object' || (!allowArray && Array.isArray(result))) throw new Error()
    return result
  } catch {
    throw apiError('The application returned an unreadable response.', response.status)
  }
}

export async function submitQuery(query, jurisdiction, history) {
  if (typeof query !== 'string' || !query.trim()) {
    throw apiError('Enter a question before sending it.', 400)
  }
  const payload = { query: query.trim() }
  if (jurisdiction) payload.jurisdiction = jurisdiction
  if (Array.isArray(history) && history.length > 0) {
    payload.history = history.slice(-6).map((item) => ({
      role: item.role === 'assistant' ? 'assistant' : 'user',
      content: typeof item.text === 'string' ? item.text : typeof item.content === 'string' ? item.content : '',
    })).filter((item) => item.content.trim())
  }
  return requestJson('/api/query', { method: 'POST', body: payload, operation: 'query' })
}

export function registerAccount({ name, email, password }) {
  return requestJson('/api/auth/register', {
    method: 'POST', body: { name, email, password }, operation: 'register',
  })
}

export function loginAccount({ email, password }) {
  return requestJson('/api/auth/login', {
    method: 'POST', body: { email, password }, operation: 'login',
  })
}

export function getCurrentUser() {
  return requestJson('/api/auth/me', { operation: 'session' })
}

export function logout() {
  return requestJson('/api/auth/logout', { method: 'POST', operation: 'logout' })
}

export async function getChats() {
  const result = await requestJson('/api/chats', { operation: 'history', allowArray: true })
  if (!Array.isArray(result)) throw apiError('Chat history could not be loaded.', 502)
  return result
}

export function getChat(id) {
  return requestJson(`/api/chats/${encodeURIComponent(id)}`, { operation: 'history-detail' })
}

export async function searchNews(query) {
  const response = await fetch(`${API_BASE_URL}/api/news/search`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ query }),
  }).catch(() => { throw apiError('Could not connect to the application service. Please try again.', 0) })
  let payload
  try { payload = await response.json() } catch { throw apiError('The application returned an unreadable response.', response.status) }
  if (!response.ok) {
    const message = payload.code === 'TAVILY_NOT_CONFIGURED'
      ? 'News search is not configured on the server. Please contact the administrator.'
      : payload.code === 'INVALID_QUERY' || payload.code === 'QUERY_TOO_LONG'
        ? payload.error
        : 'Unable to retrieve current information right now. Please try again.'
    throw apiError(message, response.status)
  }
  if (!payload || typeof payload !== 'object' || !Array.isArray(payload.results)) {
    throw apiError('The application returned an unreadable response.', 502)
  }
  return payload
}
