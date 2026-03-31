<template>
  <div class="panel">
    <div class="panel-header">
      <h3>Process &amp; Output</h3>
      <span class="timer-badge">{{ timerDisplay }}</span>
      <button class="copy-btn" @click="copyContent">Copy</button>
    </div>
    <div ref="processBody" class="panel-body process-body"></div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { usePipelineStore } from '../stores/pipeline.js'
import { useAutoScroll } from '../composables/useAutoScroll.js'
import { STAGE_LABELS } from '../stores/pipeline.js'

const emit = defineEmits(['show-modal'])

const store = usePipelineStore()
const processBody = ref(null)
const { scroll, reset: resetScroll, isLocked } = useAutoScroll(processBody)

const PHASE_LABELS = {
  calibrate: 'Calibrate',
  strategy: 'Strategy',
  decompose: 'Decompose',
  execute: 'Execute',
  evaluate: 'Evaluate',
}

// --- DOM state (non-reactive) ---
let activeStage = null
let currentSection = null
let phaseGroups = {}
let currentPhaseName = null

// --- Timer ---
const timerDisplay = ref('')
let timerInterval = null

function updateTimer() {
  if (!store.timerStart) {
    timerDisplay.value = ''
    return
  }
  const elapsed = Math.floor((Date.now() - store.timerStart) / 1000)
  const m = Math.floor(elapsed / 60)
  const s = elapsed % 60
  timerDisplay.value = m > 0 ? `${m}m ${s}s` : `${s}s`
}

// --- DOM helpers (ported from old process-viewer.js) ---

function createFold(parent, labelText, level) {
  const label = document.createElement('div')
  label.className = 'fold-label'
  if (level) label.dataset.level = level
  label.textContent = labelText

  const body = document.createElement('div')
  body.className = 'fold-body'

  label.addEventListener('click', () => {
    const collapsed = body.classList.toggle('collapsed')
    label.classList.toggle('is-collapsed')
    if (collapsed) body.classList.remove('user-expanded')
    else body.classList.add('user-expanded')
  })

  parent.appendChild(label)
  parent.appendChild(body)
  return { label, body }
}

function appendSeparator(container, label) {
  const sep = document.createElement('div')
  sep.className = 'log-separator'
  sep.textContent = `\u2500\u2500 ${label} \u2500\u2500`
  sep.addEventListener('click', () => {
    const section = sep.nextElementSibling
    if (section && section.classList.contains('log-section')) {
      const nowCollapsed = section.classList.toggle('collapsed')
      sep.classList.toggle('is-collapsed')
      if (nowCollapsed) section.classList.remove('user-expanded')
      else section.classList.add('user-expanded')
    }
  })
  container.appendChild(sep)

  const section = document.createElement('div')
  section.className = 'log-section'
  container.appendChild(section)
  scroll()
  return section
}

function target() {
  if (currentPhaseName && phaseGroups[currentPhaseName]) return phaseGroups[currentPhaseName].body
  return currentSection
}

function appendDocCard(name, label, container) {
  const t = container || target()
  if (!t) return
  const item = document.createElement('div')
  item.className = 'po-file-item'
  const icon = document.createTextNode('\uD83D\uDCC4 ')
  const span = document.createElement('span')
  span.textContent = label
  item.appendChild(icon)
  item.appendChild(span)
  item.addEventListener('click', () => {
    const doc = store.documents[name]
    emit('show-modal', label, doc ? doc.content : '')
  })
  t.appendChild(item)
  scroll()
}

function appendScoreElement(data, container) {
  const t = container || target()
  if (!t) return
  const el = document.createElement('div')
  el.className = 'po-score'
  const current = data.current != null ? data.current.toFixed(5) : '\u2014'
  const prev = data.previous != null ? data.previous.toFixed(5) : 'N/A'
  el.classList.add(data.improved ? 'po-score-improved' : 'po-score-declined')
  const spans = [
    ['po-score-label', 'Score'],
    ['po-score-current', current],
    ['po-score-arrow', data.improved ? '\u2191' : '\u2192'],
    ['po-score-prev', prev],
  ]
  for (const [cls, text] of spans) {
    const s = document.createElement('span')
    s.className = cls
    s.textContent = text
    el.appendChild(s)
  }
  t.appendChild(el)
  scroll()
}

function renderDecompTree(data) {
  const body = processBody.value
  if (!body || !data || !data.id) return
  let container = body.querySelector('.po-tree')
  if (!container) {
    container = document.createElement('ul')
    container.className = 'po-tree'
    const t = target()
    if (t) t.appendChild(container)
  }
  clearChildren(container)
  container.appendChild(renderNode(data, true))
  scroll()
}

function renderNode(node, isRoot) {
  const li = document.createElement('li')
  const span = document.createElement('span')
  span.className = 'tree-node'

  if (isRoot) {
    span.classList.add('tree-root')
    span.textContent = 'Idea'
  } else {
    if (node.is_atomic === true) span.classList.add('tree-atomic')
    else if (node.is_atomic === false) span.classList.add('tree-decomposed')
    else span.classList.add('tree-pending')

    const id = document.createElement('span')
    id.className = 'tree-id'
    id.textContent = node.id
    const desc = document.createElement('span')
    desc.className = 'tree-desc'
    desc.textContent = node.description
    span.appendChild(id)
    span.appendChild(desc)

    if (node.dependencies && node.dependencies.length > 0) {
      const deps = document.createElement('span')
      deps.className = 'tree-deps'
      deps.textContent = `\u2192 ${node.dependencies.join(', ')}`
      span.appendChild(deps)
    }
  }

  li.appendChild(span)
  if (node.children && node.children.length > 0) {
    const ul = document.createElement('ul')
    for (const child of node.children) {
      if (child) ul.appendChild(renderNode(child, false))
    }
    li.appendChild(ul)
  }
  return li
}

function renderExecBatches(batches) {
  const body = processBody.value
  if (!body || !batches || !batches.length) return
  let container = body.querySelector('.po-exec')
  if (!container) {
    container = document.createElement('div')
    container.className = 'po-exec'
    const t = target()
    if (t) t.appendChild(container)
  }

  const existingNodes = {}
  container.querySelectorAll('.exec-node').forEach((node) => {
    existingNodes[node.dataset.taskId] = node
  })

  const fragment = document.createDocumentFragment()
  for (const batch of batches) {
    const batchDiv = document.createElement('div')
    batchDiv.className = 'exec-batch'
    const label = document.createElement('div')
    label.className = 'exec-batch-label'
    label.textContent = `Batch ${batch.batch}`
    batchDiv.appendChild(label)

    for (const task of batch.tasks) {
      const existing = existingNodes[task.id]
      if (existing) {
        batchDiv.appendChild(existing)
        delete existingNodes[task.id]
      } else {
        const node = document.createElement('div')
        node.className = 'exec-node exec-pending'
        node.dataset.taskId = task.id
        const id = document.createElement('span')
        id.className = 'tree-id'
        id.textContent = task.id
        const desc = document.createElement('span')
        desc.className = 'exec-desc'
        desc.textContent = task.description
        node.appendChild(id)
        node.appendChild(desc)
        batchDiv.appendChild(node)
      }
    }
    fragment.appendChild(batchDiv)
  }
  clearChildren(container)
  container.appendChild(fragment)
  scroll()
}

function updateTaskNode(taskId, status, summary) {
  const body = processBody.value
  if (!body) return
  const node = body.querySelector(`.exec-node[data-task-id="${CSS.escape(taskId)}"]`)
  if (!node) return
  node.classList.remove(
    'exec-pending', 'exec-running', 'exec-verifying',
    'exec-retrying', 'exec-decomposing', 'exec-completed', 'exec-failed',
  )
  node.classList.add(`exec-${status}`)

  if (status === 'completed' && summary) {
    node.style.cursor = 'pointer'
    node.onclick = () => emit('show-modal', `Task ${taskId}`, summary)
  }

  const batch = node.closest('.exec-batch')
  if (batch && isLocked()) {
    batch.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }
}

function clearChildren(el) {
  while (el && el.firstChild) el.removeChild(el.firstChild)
}

function resetDOM() {
  clearChildren(processBody.value)
  activeStage = null
  currentSection = null
  phaseGroups = {}
  currentPhaseName = null
}

// --- Copy ---
function copyContent() {
  const el = processBody.value
  if (!el) return
  const text = el.innerText
  navigator.clipboard.writeText(text).catch(() => {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.cssText = 'position:fixed;opacity:0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
  })
}

// --- Watchers ---

// Stage transitions
watch(() => store.activeStage, (stage, prevStage) => {
  if (!stage) {
    resetDOM()
    resetScroll()
    return
  }
  if (stage !== prevStage && processBody.value) {
    if (currentSection) {
      currentSection.classList.add('collapsed')
      const prevSep = currentSection.previousElementSibling
      if (prevSep) prevSep.classList.add('is-collapsed')
    }
    phaseGroups = {}
    currentPhaseName = null
    currentSection = appendSeparator(processBody.value, STAGE_LABELS[stage] || stage.toUpperCase())
    activeStage = stage
  }
})

// Phase transitions
watch(() => store.currentPhase, (phase) => {
  if (!phase || !currentSection) return
  const label = PHASE_LABELS[phase] || phase
  if (phaseGroups[label]) {
    currentPhaseName = label
    return
  }
  currentPhaseName = label
  phaseGroups[label] = createFold(currentSection, label)
  scroll()
})

// Documents
watch(() => ({ ...store.documents }), (docs, oldDocs) => {
  for (const name in docs) {
    if (!oldDocs || !oldDocs[name]) {
      const doc = docs[name]
      const t = target()
      if (!t) continue
      const lastRow = t.querySelector('.po-eval-row:last-child')
      if (name.startsWith('eval_') && lastRow) {
        appendDocCard(name, doc.label, lastRow)
      } else {
        appendDocCard(name, doc.label, t)
      }
    }
  }
}, { deep: true })

// Scores
watch(() => store.scores.length, (newLen, oldLen) => {

  if (newLen > (oldLen || 0)) {
    const data = store.scores[newLen - 1]
    const t = target()
    if (t) {
      const row = document.createElement('div')
      row.className = 'po-eval-row'
      t.appendChild(row)
      appendScoreElement(data, row)
    }
  }
})

// Decomp tree
watch(() => store.decompTree, (data) => {

  if (data) renderDecompTree(data)
}, { deep: true })

// Exec batches
watch(() => store.execBatches, (batches) => {

  if (batches && batches.length) renderExecBatches(batches)
}, { deep: true })

// Task states
watch(() => ({ ...store.taskStates }), (states, oldStates) => {

  for (const taskId in states) {
    const cur = states[taskId]
    const prev = oldStates ? oldStates[taskId] : null
    if (!prev || prev.status !== cur.status) {
      updateTaskNode(taskId, cur.status, cur.summary)
    }
  }
}, { deep: true })

// Reset when pipeline goes idle
watch(() => store.pipelineState, (state) => {
  if (state === 'idle' && !store.activeStage) {
    resetDOM()
    resetScroll()
  }
})

// Timer
onMounted(() => {
  timerInterval = setInterval(updateTimer, 1000)
  updateTimer()
})
onUnmounted(() => {
  if (timerInterval) clearInterval(timerInterval)
})
</script>
