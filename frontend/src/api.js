import * as eventBus from './eventBus.js'

const BASE = '/api'

function authHeaders() {
  const token = localStorage.getItem('maars_access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function emitApiError(message) {
  eventBus.emit('error', { stage: 'system', data: { message } })
}

async function request(url, opts = {}) {
  opts.headers = { ...authHeaders(), ...opts.headers }
  const res = await fetch(url, opts)
  if (res.status === 401) {
    emitApiError('Access Token 无效或未设置，请在侧边栏中填写正确的 Access Token')
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    emitApiError(`${opts.method || 'GET'} ${url} failed (${res.status})`)
    throw new Error(`Request failed: ${res.status}`)
  }
  return res.json()
}

export function startPipeline(input) {
  return request(`${BASE}/pipeline/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ input }),
  })
}

export function fetchStatus() {
  return request(`${BASE}/pipeline/status`)
}

export function stopPipeline() {
  return request(`${BASE}/pipeline/stop`, { method: 'POST' })
}

export function stageAction(stageName, action) {
  return request(`${BASE}/stage/${stageName}/${action}`, { method: 'POST' })
}

export function checkDockerStatus() {
  return request(`${BASE}/docker/status`)
}

// --- Session management ---

export function listSessions() {
  return request(`${BASE}/sessions`)
}

export function getSession(id) {
  return request(`${BASE}/sessions/${encodeURIComponent(id)}`)
}

export function getSessionState(id) {
  return request(`${BASE}/sessions/${encodeURIComponent(id)}/state`)
}

export function deleteSession(id) {
  return request(`${BASE}/sessions/${encodeURIComponent(id)}`, { method: 'DELETE' })
}
