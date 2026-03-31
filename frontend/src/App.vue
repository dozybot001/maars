<template>
  <ProgressBar @toggle-sidebar="toggleSidebar" />
  <main>
    <section id="workspace">
      <LogViewer />
      <div class="panel-divider"></div>
      <ProcessViewer @show-modal="onShowModal" />
    </section>
  </main>
  <AppModal ref="modal" />
  <SessionDrawer ref="sessionDrawer" />
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { usePipelineStore } from './stores/pipeline.js'
import { fetchStatus, checkDockerStatus } from './api.js'
import { useSSE } from './composables/useSSE.js'

import ProgressBar from './components/ProgressBar.vue'
import LogViewer from './components/LogViewer.vue'
import ProcessViewer from './components/ProcessViewer.vue'
import AppModal from './components/AppModal.vue'
import SessionDrawer from './components/SessionDrawer.vue'

const store = usePipelineStore()
const modal = ref(null)
const sessionDrawer = ref(null)
const { connect: connectSSE } = useSSE()

function toggleSidebar() {
  sessionDrawer.value?.toggle()
}

let dockerInterval = null

function onShowModal(title, content) {
  modal.value?.open(title, content)
}

let dockerCheckPending = false
async function checkDocker() {
  if (dockerCheckPending) return
  dockerCheckPending = true
  try {
    const data = await checkDockerStatus()
    store.setDockerStatus(data.connected, data.error)
  } catch {
    store.setDockerStatus(false, 'Cannot check Docker status')
  } finally {
    dockerCheckPending = false
  }
}

function onBeforeUnload() {
  if (store.pipelineState === 'running') {
    const token = localStorage.getItem('maars_access_token')
    const headers = token ? { Authorization: `Bearer ${token}` } : {}
    fetch('/api/pipeline/stop', { method: 'POST', keepalive: true, headers })
      .catch(() => {})
  }
}

onMounted(async () => {
  window.addEventListener('beforeunload', onBeforeUnload)
  // Sync with backend state, then connect SSE
  try {
    const status = await fetchStatus()
    store.syncFromStatus(status)
  } catch (err) {
    console.warn('[App] Failed to fetch initial status:', err.message)
  }

  connectSSE()

  // Docker status polling
  checkDocker()
  dockerInterval = setInterval(checkDocker, 30000)
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', onBeforeUnload)
  if (dockerInterval) clearInterval(dockerInterval)
})
</script>
