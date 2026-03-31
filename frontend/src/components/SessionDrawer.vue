<template>
  <!-- Overlay: click outside to close -->
  <div v-if="panelVisible" class="sidebar-overlay" @click.self="close">
    <!-- Sidebar shell — always visible when panelVisible -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <h3>Sessions</h3>
        <div class="sidebar-header-right">
          <span
            class="sidebar-docker"
            :class="`sidebar-docker-${store.dockerStatus}`"
            :title="store.dockerTitle"
          >{{ store.dockerStatus === 'connected' ? 'Docker OK' : 'Docker' }}</span>
          <button class="sidebar-close" @click="close"><span class="arrow-left"></span></button>
        </div>
      </div>

      <!-- Content area — only shown after shell is ready -->
      <div v-if="contentVisible" class="sidebar-content">
        <!-- New session card (always first, with all 3 control buttons) -->
        <div class="session-card new-card">
          <input
            ref="newInputEl"
            v-model="newInput"
            type="text"
            class="card-input"
            placeholder="Research idea or Kaggle URL..."
            autocomplete="off"
            @keydown.enter="handleStart"
          >
          <div class="card-actions">
            <button class="card-btn card-btn-start" :disabled="!canStart" @click="handleStart">Start</button>
            <button
              class="card-btn"
              :disabled="!canPause"
              @click="handlePause"
            >{{ store.pipelineState === 'pausing' ? 'Pausing...' : 'Pause' }}</button>
            <button
              class="card-btn"
              :disabled="!canResume"
              @click="handleResume"
            >Resume</button>
          </div>
        </div>

        <!-- Separator -->
        <div v-if="sessions.length" class="sidebar-divider"></div>

        <!-- History sessions -->
        <div v-if="loading" class="sidebar-empty">Loading...</div>
        <div
          v-for="s in sessions"
          :key="s.id"
          class="session-card history-card"
          :class="{ 'card-loading': loadingSessionId === s.id }"
          @click="loadSession(s.id)"
        >
          <div class="card-status-row">
            <span class="card-status" :data-status="s.status">{{ s.status }}</span>
            <span class="card-date">{{ formatDate(s.created) }}</span>
          </div>
          <div class="card-idea">{{ s.idea_summary || '(no input)' }}</div>
          <button class="card-delete" @click.stop="handleDelete(s.id)" title="Delete">&times;</button>
        </div>
      </div>

      <!-- Access Token footer -->
      <div class="sidebar-footer">
        <div class="token-row">
          <input
            v-model="tokenInput"
            type="password"
            class="token-input"
            placeholder="Access Token"
            autocomplete="off"
            @keydown.enter="saveToken"
          >
          <button class="token-btn" @click="saveToken">{{ tokenSaved ? '✓' : 'Save' }}</button>
        </div>
      </div>
    </aside>
  </div>

</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { usePipelineStore } from '../stores/pipeline.js'
import { startPipeline, stopPipeline, stageAction, listSessions, getSessionState, deleteSession } from '../api.js'

const store = usePipelineStore()

// --- Panel visibility (two-phase open/close) ---
const panelVisible = ref(false)
const contentVisible = ref(false)

// --- New session ---
const newInput = ref('')
const newInputEl = ref(null)

// --- Access Token ---
const tokenInput = ref(localStorage.getItem('maars_access_token') || '')
const tokenSaved = ref(false)

function saveToken() {
  const val = tokenInput.value.trim()
  if (val) {
    localStorage.setItem('maars_access_token', val)
  } else {
    localStorage.removeItem('maars_access_token')
  }
  tokenSaved.value = true
  setTimeout(() => { tokenSaved.value = false }, 1500)
}

// --- History ---
const loading = ref(false)
const loadingSessionId = ref(null)
const sessions = ref([])

// --- Computed ---
const canStart = computed(() => {
  const s = store.pipelineState
  return s !== 'running' && s !== 'paused' && s !== 'pausing' && newInput.value.trim().length > 0
})

const canPause = computed(() => store.pipelineState === 'running')
const canResume = computed(() => store.pipelineState === 'paused')

// --- Open / Close (two-phase) ---

async function open() {
  if (panelVisible.value) return
  panelVisible.value = true
  // Wait for sidebar shell to render, then show content
  await nextTick()
  contentVisible.value = true
  loading.value = true
  try {
    sessions.value = await listSessions()
  } catch (err) {
    console.error('Failed to load sessions:', err)
  } finally {
    loading.value = false
  }
  // Focus input after content renders
  await nextTick()
  newInputEl.value?.focus()
}

function close() {
  if (!panelVisible.value) return
  // Phase 1: hide content immediately
  contentVisible.value = false
  // Phase 2: hide sidebar shell on next frame
  requestAnimationFrame(() => {
    panelVisible.value = false
  })
}

function toggle() {
  if (panelVisible.value) close()
  else open()
}

// --- Pipeline actions ---

async function handleStart() {
  const text = newInput.value.trim()
  if (!text || !canStart.value) return
  newInput.value = ''
  close()
  try {
    await startPipeline(text)
  } catch (err) {
    console.error('Failed to start pipeline:', err)
  }
}

async function handlePause() {
  if (store.pipelineState !== 'running') return
  const running = Object.keys(store.stageStates).find((s) => store.stageStates[s] === 'running')
  if (running) store.stageStates[running] = 'pausing'
  try {
    await stopPipeline()
  } catch (err) {
    console.error('Pause error:', err)
  }
}

async function handleResume() {
  const paused = Object.keys(store.stageStates).find((s) => store.stageStates[s] === 'paused')
  if (!paused) return
  try {
    await stageAction(paused, 'resume')
  } catch (err) {
    console.error('Resume error:', err)
  }
}

// --- History actions ---

async function loadSession(id) {
  if (loadingSessionId.value) return
  loadingSessionId.value = id
  try {
    const state = await getSessionState(id)
    close()
    await store.loadSessionState(state)
  } catch (err) {
    console.error('Failed to load session state:', err)
  } finally {
    loadingSessionId.value = null
  }
}

async function handleDelete(id) {
  if (!confirm(`Delete session ${id}?`)) return
  try {
    await deleteSession(id)
    sessions.value = sessions.value.filter((s) => s.id !== id)
  } catch (err) {
    console.error('Failed to delete session:', err)
  }
}

// --- Keyboard shortcut ---
function onKeydown(e) {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault()
    toggle()
  }
  if (e.key === 'Escape' && panelVisible.value) {
    close()
  }
}

onMounted(() => document.addEventListener('keydown', onKeydown))
onUnmounted(() => document.removeEventListener('keydown', onKeydown))

// --- Helpers ---
function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

defineExpose({ open, close, toggle })
</script>

<style scoped>
/* ---- Overlay ---- */
.sidebar-overlay {
  position: fixed;
  inset: 0;
  z-index: 900;
  background: rgba(0, 0, 0, 0.35);
}

/* ---- Sidebar shell ---- */
.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  width: 340px;
  max-width: 85vw;
  height: 100vh;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  box-shadow: 8px 0 24px rgba(0, 0, 0, 0.3);
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.sidebar-header h3 {
  font-size: 14px;
  font-weight: 600;
}

.sidebar-header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.sidebar-docker {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
}

.sidebar-docker-unknown { color: var(--text-muted); }
.sidebar-docker-connected { color: var(--green); }
.sidebar-docker-disconnected { color: var(--red); }

.sidebar-close {
  background: none;
  border: none;
  cursor: pointer;
  padding: 8px 12px;
  margin: -8px;
  display: flex;
  align-items: center;
}

.arrow-left {
  width: 6px;
  height: 6px;
  border-top: 1.5px solid var(--text-secondary);
  border-left: 1.5px solid var(--text-secondary);
  transform: rotate(-45deg);
}

.sidebar-close:hover .arrow-left {
  border-color: var(--accent);
}

/* ---- Footer ---- */
.sidebar-footer {
  padding: 10px 12px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}

.token-row {
  display: flex;
  gap: 6px;
}

.token-input {
  flex: 1;
  min-width: 0;
  padding: 5px 8px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text-primary);
  font-size: 12px;
  font-family: var(--font-mono);
  outline: none;
}

.token-input:focus {
  border-color: var(--accent);
}

.token-btn {
  padding: 4px 12px;
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  background: transparent;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  white-space: nowrap;
}

.token-btn:hover {
  color: var(--accent);
  border-color: var(--accent);
}

/* ---- Content ---- */
.sidebar-content {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.sidebar-divider {
  height: 1px;
  background: var(--border);
  margin: 8px 4px;
}

.sidebar-empty {
  text-align: center;
  color: var(--text-muted);
  padding: 20px;
  font-size: 12px;
}

/* ---- Session card (shared) ---- */
.session-card {
  position: relative;
  padding: 10px 12px;
  margin-bottom: 6px;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  background: var(--bg-card);
}
.card-loading {
  opacity: 0.5;
  pointer-events: none;
}

/* ---- New session card ---- */
.new-card {
  border-color: var(--accent);
  border-style: dashed;
  background: transparent;
}

.card-input {
  width: 100%;
  padding: 6px 8px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text-primary);
  font-size: 13px;
  font-family: var(--font-mono);
  outline: none;
}

.card-input:focus {
  border-color: var(--accent);
}

/* ---- History card ---- */
.history-card {
  cursor: pointer;
}

.history-card:hover {
  background: var(--bg-input);
}

/* ---- Card internals ---- */
.card-status-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.card-status {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 5px;
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.card-status[data-status="completed"] { color: var(--green); background: rgba(63, 185, 80, 0.12); }
.card-status[data-status="researching"] { color: var(--blue); background: rgba(88, 166, 255, 0.12); }
.card-status[data-status="refining"] { color: var(--yellow); background: rgba(210, 153, 34, 0.12); }
.card-status[data-status="created"] { color: var(--text-muted); background: var(--bg-input); }
.card-status[data-status="running"] { color: var(--blue); background: rgba(88, 166, 255, 0.12); }
.card-status[data-status="paused"] { color: var(--yellow); background: rgba(210, 153, 34, 0.12); }
.card-status[data-status="pausing"] { color: var(--yellow); background: rgba(210, 153, 34, 0.12); }

.card-date {
  font-size: 10px;
  color: var(--text-muted);
}

.card-idea {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.card-actions {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}

.card-btn {
  padding: 4px 12px;
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  background: transparent;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

.card-btn:hover:not(:disabled) {
  color: var(--accent);
  border-color: var(--accent);
}

.card-btn:disabled {
  opacity: 0.25;
  cursor: not-allowed;
}

.card-btn-start {
  color: var(--accent);
  border-color: var(--accent);
}

.card-btn-start:hover:not(:disabled) {
  background: rgba(88, 166, 255, 0.1);
}

.card-delete {
  position: absolute;
  top: 6px;
  right: 6px;
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 14px;
  cursor: pointer;
  opacity: 0;
  line-height: 1;
}

.history-card:hover .card-delete {
  opacity: 1;
}

.card-delete:hover {
  color: var(--red);
}

</style>
