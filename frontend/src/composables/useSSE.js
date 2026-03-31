import { onUnmounted } from 'vue'
import { usePipelineStore } from '../stores/pipeline.js'
import * as eventBus from '../eventBus.js'

function safeParse(raw) {
  try {
    return JSON.parse(raw)
  } catch {
    console.warn('[SSE] Failed to parse event data:', raw)
    return null
  }
}

/**
 * Dispatch a parsed SSE event to the store / eventBus.
 */
function dispatch(store, eventType, dataStr) {
  const data = safeParse(dataStr)
  if (!data) return

  switch (eventType) {
    case 'state':
      store.handleStageState(data.stage, data.data)
      break
    case 'phase':
      store.handlePhase(data.data)
      eventBus.emit('phase', data)
      break
    case 'chunk':
      store.markActivity()
      eventBus.emit('chunk', data)
      break
    case 'task_state':
      store.updateTaskState(data.data)
      eventBus.emit('task_state', data)
      break
    case 'exec_tree':
      store.setExecBatches(data.data)
      break
    case 'tree':
      store.setDecompTree(data.data)
      break
    case 'tokens':
      store.markActivity()
      store.addTokens(data.data)
      eventBus.emit('tokens', data)
      break
    case 'document':
      store.addDocument(data.data)
      break
    case 'score':
      store.addScore(data.data)
      break
    case 'error':
      store.addError(data.stage, data.data?.message || data.data)
      eventBus.emit('error', data)
      break
  }
}

export function useSSE() {
  let controller = null
  let reconnectTimer = null
  let reconnectDelay = 2000     // start at 2s
  const MAX_RECONNECT_DELAY = 30000  // cap at 30s

  async function connect() {
    disconnect()

    const store = usePipelineStore()
    const token = localStorage.getItem('maars_access_token')
    const headers = token ? { Authorization: `Bearer ${token}` } : {}

    controller = new AbortController()
    const connectTimeout = setTimeout(() => controller.abort(), 30000)

    try {
      const res = await fetch('/api/events', {
        headers,
        signal: controller.signal,
      })
      clearTimeout(connectTimeout)
      if (!res.ok || !res.body) {
        scheduleReconnect()
        return
      }

      reconnectDelay = 2000  // reset backoff on successful connection

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      let currentEvent = ''
      let currentData = ''
      let readTimeout = null

      function resetReadTimeout() {
        if (readTimeout) clearTimeout(readTimeout)
        readTimeout = setTimeout(() => controller && controller.abort(), 45000)
      }

      while (true) {
        resetReadTimeout()
        const { done, value } = await reader.read()
        if (done) break

        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() // keep incomplete last line in buffer

        for (const line of lines) {
          if (line.startsWith('event:')) {
            currentEvent = line.slice(6).trim()
          } else if (line.startsWith('data:')) {
            // SSE spec: multiple data: lines are joined with '\n'
            const d = line.slice(5).trim()
            currentData = currentData ? currentData + '\n' + d : d
          } else if (line === '' && currentEvent && currentData) {
            dispatch(store, currentEvent, currentData)
            currentEvent = ''
            currentData = ''
          }
        }
      }

      if (readTimeout) clearTimeout(readTimeout)
      // Stream ended normally — server closed connection, try reconnect
      scheduleReconnect()
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.warn('[SSE] Connection error, reconnecting...', err.message)
        scheduleReconnect()
      }
    }
  }

  function scheduleReconnect() {
    if (reconnectTimer) return
    const delay = reconnectDelay
    reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY)
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      connect()
    }, delay)
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (controller) {
      controller.abort()
      controller = null
    }
  }

  onUnmounted(disconnect)

  return { connect, disconnect }
}
