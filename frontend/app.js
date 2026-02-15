const API_BASE_URL = 'http://localhost:3001/api';

// DOM Elements
const ideaInput = document.getElementById('ideaInput');

const generatePlanBtn = document.getElementById('generatePlanBtn');
const decomposeBtn = document.getElementById('decomposeBtn');
const stopPlanBtn = document.getElementById('stopPlanBtn');
const loadExampleIdeaBtn = document.getElementById('loadExampleIdeaBtn');

let planRunAbortController = null;

// Load example idea from backend
async function loadExampleIdea() {
    try {
        const response = await fetch(`${API_BASE_URL}/idea`);
        const data = await response.json();
        if (data.idea) {
            ideaInput.value = typeof data.idea === 'string' ? data.idea : JSON.stringify(data.idea);
        } else {
            ideaInput.value = 'Research and analyze the latest trends in AI technology';
        }
    } catch (error) {
        console.error('Error loading example idea:', error);
        ideaInput.value = 'Research and analyze the latest trends in AI technology';
    }
}

// Load execution from database
async function loadExecution() {
    try {
        const response = await fetch(`${API_BASE_URL}/execution`);
        const data = await response.json();
        return data.execution || null;
    } catch (error) {
        console.error('Error loading execution:', error);
        return null;
    }
}

// Save execution to database
async function saveExecution(execution) {
    try {
        const response = await fetch(`${API_BASE_URL}/execution`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(execution)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to save execution');
        }
        
        return await response.json();
    } catch (error) {
        console.error('Error saving execution:', error);
        throw error;
    }
}

// Task tree: see task-tree.js

// Generate plan: idea → decompose → 1,2,3,4 (unified decompose+verify+format flow)
async function generatePlan() {
    const idea = (ideaInput?.value || '').trim();
    if (!idea) {
        alert('Please enter an idea first.');
        return;
    }

    if (!socket || !socket.connected) {
        alert('WebSocket not connected. Please wait and try again.');
        return;
    }

    try {
        generatePlanBtn.disabled = true;
        decomposeBtn.disabled = true;
        if (stopPlanBtn) stopPlanBtn.style.display = '';
        planRunAbortController = new AbortController();

        TaskTree.clearPlannerTree();
        const response = await fetch(`${API_BASE_URL}/plan/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ idea }),
            signal: planRunAbortController.signal
        });

        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Failed to generate plan');
    } catch (error) {
        if (error.name === 'AbortError') return;
        console.error('Error generating plan:', error);
        alert('Error: ' + (error.message || 'Failed to generate plan'));
    } finally {
        generatePlanBtn.disabled = false;
        generatePlanBtn.textContent = 'Generate Plan';
        decomposeBtn.disabled = false;
        if (stopPlanBtn) stopPlanBtn.style.display = 'none';
        planRunAbortController = null;
    }
}

// Decompose first task without children (verify → decompose → format)
async function decomposeTask() {
    if (!decomposeBtn || decomposeBtn.disabled) return;
    try {
        decomposeBtn.disabled = true;
        decomposeBtn.textContent = 'Decomposing...';
        if (stopPlanBtn) stopPlanBtn.style.display = '';
        planRunAbortController = new AbortController();

        const response = await fetch(`${API_BASE_URL}/plan/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
            signal: planRunAbortController.signal
        });
        const res = await response.json();
        if (!response.ok) throw new Error(res.error || 'Failed to decompose');
    } catch (error) {
        if (error.name === 'AbortError') return;
        console.error('Error decomposing:', error);
        alert('Error: ' + (error.message || 'Failed to decompose'));
    } finally {
        decomposeBtn.disabled = false;
        decomposeBtn.textContent = 'Decompose';
        if (stopPlanBtn) stopPlanBtn.style.display = 'none';
        planRunAbortController = null;
    }
}

function stopPlanRun() {
    if (planRunAbortController) planRunAbortController.abort();
    fetch(`${API_BASE_URL}/plan/stop`, { method: 'POST' }).catch(() => {});
}

// Event listeners
if (generatePlanBtn) generatePlanBtn.addEventListener('click', generatePlan);
if (decomposeBtn) decomposeBtn.addEventListener('click', decomposeTask);
if (stopPlanBtn) stopPlanBtn.addEventListener('click', stopPlanRun);
if (loadExampleIdeaBtn) {
    loadExampleIdeaBtn.addEventListener('click', loadExampleIdea);
}

// Note: Data will be loaded when user clicks the corresponding generate buttons
// No automatic loading on page refresh

// ========== Monitor ==========

const WS_URL = 'http://localhost:3001';
let socket = null;
let plannerThinkingBuffer = '';
let timetableLayout = null;
let chainCache = [];
let previousTaskStates = new Map();

// Build chain cache from timetable layout (grid + isolatedTasks)
function buildChainCacheFromLayout(layout) {
  const cache = [];
  if (!layout) return cache;
  const { grid, isolatedTasks } = layout;
  if (grid) {
    grid.forEach(row => {
      row.forEach(cell => {
        if (cell && cell.task_id) {
          cache.push({
            task_id: cell.task_id,
            dependencies: cell.dependencies || [],
            status: cell.status || 'undone'
          });
        }
      });
    });
  }
  if (isolatedTasks) {
    isolatedTasks.forEach(task => {
      if (task && task.task_id) {
        cache.push({
          task_id: task.task_id,
          dependencies: task.dependencies || [],
          status: task.status || 'undone'
        });
      }
    });
  }
  return cache;
}

// DOM Elements for monitor
const diagramArea = document.getElementById('diagramArea');
const generateTimetableBtn = document.getElementById('generateTimetableBtn');
const mockExecutionBtn = document.getElementById('mockExecutionBtn');

// Initialize WebSocket connection (for monitor)
function initializeWebSocket() {
    if (socket && socket.connected) {
        return;
    }

    socket = io(WS_URL);

    socket.on('connect', () => {
        console.log('WebSocket connected');
    });

    socket.on('disconnect', () => {
        console.log('WebSocket disconnected');
    });

    socket.on('plan-start', () => {
        plannerThinkingBuffer = '';
        const el = document.getElementById('plannerThinkingContent');
        const area = document.getElementById('plannerThinkingArea');
        if (el) el.innerHTML = '';
        if (area) area.classList.remove('has-content');
        TaskTree.clearPlannerTree();
    });

    socket.on('plan-thinking', (data) => {
        const el = document.getElementById('plannerThinkingContent');
        const area = document.getElementById('plannerThinkingArea');
        if (el && data.chunk) {
            plannerThinkingBuffer += data.chunk;
            try {
                el.innerHTML = typeof marked !== 'undefined' ? marked.parse(plannerThinkingBuffer) : plannerThinkingBuffer;
            } catch (_) {
                el.textContent = plannerThinkingBuffer;
            }
            el.scrollTop = el.scrollHeight;
            if (area) area.classList.add('has-content');
        }
    });

    socket.on('plan-task', (data) => {
        if (data.task) TaskTree.appendPlannerTaskNode(data.task);
    });


    socket.on('plan-complete', (data) => {
        if (data.treeData && TaskTree.renderPlannerTree) {
            TaskTree.renderPlannerTree(data.treeData);
        }
        if (generatePlanBtn) {
            generatePlanBtn.disabled = false;
            generatePlanBtn.textContent = 'Generate Plan';
        }
        if (decomposeBtn) decomposeBtn.disabled = false;
        if (stopPlanBtn) stopPlanBtn.style.display = 'none';
    });

    socket.on('plan-error', () => {
        if (generatePlanBtn) {
            generatePlanBtn.disabled = false;
            generatePlanBtn.textContent = 'Generate Plan';
        }
        if (decomposeBtn) {
            decomposeBtn.disabled = false;
            decomposeBtn.textContent = 'Decompose';
        }
        if (stopPlanBtn) stopPlanBtn.style.display = 'none';
    });

    socket.on('timetable-layout', (data) => {
        timetableLayout = data.layout;
        chainCache = buildChainCacheFromLayout(timetableLayout);
        renderNodeDiagramFromCache();
    });

    socket.on('task-states-update', (data) => {
        if (data.tasks && Array.isArray(data.tasks)) {
            const diagramContent = document.getElementById('diagramArea');
            
            data.tasks.forEach(taskState => {
                const cacheNode = chainCache.find(node => node.task_id === taskState.task_id);
                const previousStatus = previousTaskStates.get(taskState.task_id);
                
                // Update cache
                if (cacheNode) {
                    cacheNode.status = taskState.status;
                }
                
                // Detect state changes and trigger connection line animations
                if (previousStatus !== undefined && previousStatus !== taskState.status) {
                    // Task started executing (from undone/verifying to doing)
                    if (taskState.status === 'doing' && (previousStatus === 'undone' || previousStatus === 'verifying')) {
                        // Trigger yellow glow animation on upstream connection lines (top to bottom)
                        setTimeout(() => {
                            animateUpstreamConnections(taskState.task_id, 'yellow');
                        }, 100); // Small delay for visual effect
                    }
                    
                    // Task rolled back (from any status back to undone, especially after failures)
                    if (taskState.status === 'undone' && previousStatus !== 'undone') {
                        // Check if this is a rollback (not initial state)
                        // Rollback typically happens after execution-failed or verification-failed
                        if (previousStatus === 'execution-failed' || previousStatus === 'verification-failed' || previousStatus === 'doing' || previousStatus === 'verifying') {
                            // Trigger red glow animation on upstream connection lines (bottom to top)
                            setTimeout(() => {
                                animateUpstreamConnections(taskState.task_id, 'red');
                            }, 100); // Small delay for visual effect
                        }
                    }
                }
                
                // Update previous state
                previousTaskStates.set(taskState.task_id, taskState.status);
                
                // Update all elements with this task ID (both timetable cells and tree tasks)
                // Search in the entire document, not just diagramContent, to include tasks tree
                const cells = document.querySelectorAll(`[data-task-id="${taskState.task_id}"]`);
                if (cells && cells.length > 0) {
                    cells.forEach(cell => {
                        cell.classList.remove('task-status-undone', 'task-status-doing', 'task-status-verifying', 'task-status-done', 'task-status-verification-failed', 'task-status-execution-failed');
                        cell.classList.add(`task-status-${taskState.status}`);
                    });
                }
            });
        }
    });

    socket.on('executor-states-update', (data) => {
        if (data.executors && data.stats) {
            renderExecutors(data.executors, data.stats);
        }
    });

    socket.on('verifier-states-update', (data) => {
        if (data.verifiers && data.stats) {
            renderVerifiers(data.verifiers, data.stats);
        }
    });

    socket.on('execution-error', (data) => {
        console.error('Execution error:', data.error);
        alert('Execution error: ' + data.error);
        mockExecutionBtn.disabled = false;
        mockExecutionBtn.textContent = 'Mock Execution';
    });

    socket.on('execution-complete', (data) => {
        console.log(`Execution complete: ${data.completed}/${data.total} tasks completed`);
        const btn = mockExecutionBtn;
        btn.disabled = false;
        btn.textContent = 'Execution Complete!';
        setTimeout(() => {
            btn.textContent = 'Mock Execution';
        }, 2000);
    });
}

// Render timetable diagram
function renderTimetableDiagram() {
    const diagramContent = document.getElementById('diagramArea');
    
    let html = '<div class="execution-map">';
    
    // Default display: 7 columns, 4 rows for Stage Tasks
    const displayCols = 7;
    const displayRows = 4;
    const rightCols = 3;  // Isolated Tasks: 3 columns
    const rightRows = 4;   // Isolated Tasks: 4 rows
    
    // If no timetable layout, show empty grid
    if (!timetableLayout || !timetableLayout.grid) {
        const actualCols = displayCols;
        const actualRows = displayRows;
        const grid = [];
        const isolatedTasks = [];
        
        html += '<div class="timetable-container">';
        html += '<div class="timetable-wrapper">';
        
        html += '<div class="timetable-left">';
        html += '<div class="timetable-left-scroll">';
        html += '<div class="timetable-left-header timetable-header-row">';
        for (let col = 0; col < actualCols; col++) {
            html += `<div class="timetable-header-cell">Stage ${col + 1}</div>`;
        }
        html += '</div>';
        
        html += '<div class="timetable-left-grid timetable-grid">';
        for (let row = 0; row < actualRows; row++) {
            for (let col = 0; col < actualCols; col++) {
                html += `<div class="timetable-cell timetable-cell-empty"></div>`;
            }
        }
        html += '</div>';
        html += '</div>';
        html += '</div>';
        
        html += '<div class="timetable-right">';
        html += '<div class="timetable-right-scroll">';
        html += '<div class="timetable-right-header timetable-header-row">';
        html += `<div class="timetable-header-cell" style="grid-column: 1 / -1;">Isolated Tasks</div>`;
        html += '</div>';
        
        html += '<div class="timetable-right-grid timetable-grid">';
        for (let row = 0; row < rightRows; row++) {
            for (let col = 0; col < rightCols; col++) {
                html += `<div class="timetable-cell timetable-cell-empty"></div>`;
            }
        }
        html += '</div>';
        html += '</div>';
        html += '</div>';
        
    html += '</div>';
    html += '</div>';
    html += '</div>';
    
    html += '</div>';
    html += '</div>';
    diagramContent.innerHTML = html;
    
    // Render tasks tree in separate area
    TaskTree.renderMonitorTasksTree(timetableLayout?.treeData || []);
    
    setTimeout(() => {
            // Get the main container for calculating fixed cell size
            const timetableWrapper = diagramContent.querySelector('.timetable-wrapper');
            if (!timetableWrapper) return;
            
            // Calculate fixed cell size: (container width - gap) / 10
            const { cellSize: fixedCellSize, rightAreaWidth } = calculateFixedCellSize(timetableWrapper);
            
            // Set right area width (3 cells + gap)
            const rightArea = diagramContent.querySelector('.timetable-right');
            if (rightArea) {
                rightArea.style.width = `${rightAreaWidth}px`;
                rightArea.style.minWidth = `${rightAreaWidth}px`;
                rightArea.style.maxWidth = `${rightAreaWidth}px`;
            }
            
            const leftScroll = diagramContent.querySelector('.timetable-left-scroll');
            const rightScroll = diagramContent.querySelector('.timetable-right-scroll');
            const leftHeader = diagramContent.querySelector('.timetable-left-header');
            const leftGrid = diagramContent.querySelector('.timetable-left-grid');
            const rightHeader = diagramContent.querySelector('.timetable-right-header');
            const rightGrid = diagramContent.querySelector('.timetable-right-grid');
            
            const gap = 1; // CSS gap is 1px
            
        // Apply fixed cell size to left grid
        if (leftScroll && leftHeader && leftGrid) {
            const actualGridWidth = actualCols * fixedCellSize + gap * (actualCols - 1);
            const actualGridHeight = actualRows * fixedCellSize + gap * (actualRows - 1);
            
            leftHeader.setAttribute('data-cols', actualCols);
            leftGrid.setAttribute('data-cols', actualCols);
            leftGrid.setAttribute('data-rows', actualRows);
            leftHeader.style.gridTemplateColumns = `repeat(${actualCols}, ${fixedCellSize}px)`;
            leftGrid.style.gridTemplateColumns = `repeat(${actualCols}, ${fixedCellSize}px)`;
            leftGrid.style.gridTemplateRows = `repeat(${actualRows}, ${fixedCellSize}px)`;
            
            // Set explicit width to allow horizontal scrolling when columns exceed visible area
            leftGrid.style.width = `${actualGridWidth}px`;
            leftGrid.style.minWidth = `${actualGridWidth}px`;
            leftGrid.style.height = `${actualGridHeight}px`;
            leftGrid.style.minHeight = `${actualGridHeight}px`;
            leftHeader.style.width = `${actualGridWidth}px`;
            leftHeader.style.minWidth = `${actualGridWidth}px`;
        }
            
            // Apply fixed cell size to right grid (Isolated Tasks)
            if (rightScroll && rightHeader && rightGrid) {
                const actualGridWidth = rightCols * fixedCellSize + gap * (rightCols - 1);
                const actualGridHeight = rightRows * fixedCellSize + gap * (rightRows - 1);
                
                rightHeader.setAttribute('data-cols', rightCols);
                rightGrid.setAttribute('data-cols', rightCols);
                rightGrid.setAttribute('data-rows', rightRows);
                
                rightHeader.style.gridTemplateColumns = `repeat(${rightCols}, ${fixedCellSize}px)`;
                rightGrid.style.gridTemplateColumns = `repeat(${rightCols}, ${fixedCellSize}px)`;
                rightGrid.style.gridTemplateRows = `repeat(${rightRows}, ${fixedCellSize}px)`;
                
                rightGrid.style.width = `${actualGridWidth}px`;
                rightGrid.style.minWidth = `${actualGridWidth}px`;
                rightGrid.style.height = `${actualGridHeight}px`;
                rightGrid.style.minHeight = `${actualGridHeight}px`;
                rightHeader.style.width = `${actualGridWidth}px`;
                rightHeader.style.minWidth = `${actualGridWidth}px`;
            }
            
    }, 0);
        return;
    }
    
    const { grid, maxRows, maxCols, isolatedTasks, treeData } = timetableLayout;
    
    // Use actual number of columns from backend, but ensure minimum of displayCols for empty states
    // If maxCols is available and greater than displayCols, use maxCols to allow scrolling
    const actualCols = Math.max(maxCols || displayCols, displayCols);
    const actualRows = Math.max(maxRows || 0, displayRows);
    
    html += '<div class="timetable-container">';
    html += '<div class="timetable-wrapper">';
    
    html += '<div class="timetable-left">';
    html += '<div class="timetable-left-scroll">';
    html += '<div class="timetable-left-header timetable-header-row">';
    for (let col = 0; col < actualCols; col++) {
        html += `<div class="timetable-header-cell">Stage ${col + 1}</div>`;
    }
    html += '</div>';
    
    html += '<div class="timetable-left-grid timetable-grid">';
    for (let row = 0; row < actualRows; row++) {
        for (let col = 0; col < actualCols; col++) {
            // Check if there's a task at this position
            const task = (grid && row < grid.length && col < grid[row].length) ? grid[row][col] : null;
            if (task && task.task_id) {
                const status = task.status || 'undone';
                const desc = task.description || task.objective || task.task_id;
                const safeTooltip = (desc || '').replace(/"/g, '&quot;');
                html += `<div class="timetable-cell task-status-${status}" data-task-id="${task.task_id}" title="${safeTooltip}">
                    <span class="task-number">${task.task_id}</span>
                    <span class="task-description">${desc}</span>
                </div>`;
            } else {
                // Empty cell
                html += `<div class="timetable-cell timetable-cell-empty"></div>`;
            }
        }
    }
    html += '</div>';
    html += '</div>';
    html += '</div>';
    
    html += '<div class="timetable-right">';
    html += '<div class="timetable-right-scroll">';
    html += '<div class="timetable-right-header timetable-header-row">';
    html += `<div class="timetable-header-cell" style="grid-column: 1 / -1;">Isolated Tasks</div>`;
    html += '</div>';
    
    html += '<div class="timetable-right-grid timetable-grid">';
    // Calculate actual rows needed for isolated tasks
    // Ensure minimum of rightRows (4), but expand if more tasks exist
    const isolatedTaskCount = isolatedTasks && isolatedTasks.length > 0 ? isolatedTasks.length : 0;
    const actualRightRows = Math.max(Math.ceil(isolatedTaskCount / rightCols), rightRows);
    
    // Create a map of task positions (right-aligned: fill from right to left)
    const totalCells = actualRightRows * rightCols;
    const taskPositionMap = new Map();
    if (isolatedTasks && isolatedTasks.length > 0) {
        isolatedTasks.forEach((task, i) => {
            if (task && task.task_id) {
                // Calculate position from right to left
                const positionFromRight = totalCells - 1 - i;
                const taskRow = Math.floor(positionFromRight / rightCols);
                const taskCol = positionFromRight % rightCols;
                taskPositionMap.set(`${taskRow}-${taskCol}`, task);
            }
        });
    }
    
    for (let row = 0; row < actualRightRows; row++) {
        for (let col = 0; col < rightCols; col++) {
            const positionKey = `${row}-${col}`;
            const task = taskPositionMap.get(positionKey);
            if (task && task.task_id) {
                const status = task.status || 'undone';
                const desc = task.description || task.objective || task.task_id;
                const safeTooltip = (desc || '').replace(/"/g, '&quot;');
                html += `<div class="timetable-cell task-status-${status}" data-task-id="${task.task_id}" title="${safeTooltip}">
                    <span class="task-number">${task.task_id}</span>
                    <span class="task-description">${desc}</span>
                </div>`;
            } else {
                // Empty cell
                html += `<div class="timetable-cell timetable-cell-empty"></div>`;
            }
        }
    }
    html += '</div>';
    html += '</div>';
    html += '</div>';
    
    html += '</div>';
    html += '</div>';
    html += '</div>';
    
    html += '</div>';
    html += '</div>';
    diagramContent.innerHTML = html;
    
    // Render tasks tree in separate area
    TaskTree.renderMonitorTasksTree(treeData || []);
    
    setTimeout(() => {
        // Get the main container for calculating fixed cell size
        const timetableWrapper = diagramContent.querySelector('.timetable-wrapper');
        if (!timetableWrapper) return;
        
        // Calculate fixed cell size: (container width - gap) / 10
        const { cellSize: fixedCellSize, rightAreaWidth } = calculateFixedCellSize(timetableWrapper);
        
        // Set right area width (3 cells + gap)
        const rightArea = diagramContent.querySelector('.timetable-right');
        if (rightArea) {
            rightArea.style.width = `${rightAreaWidth}px`;
            rightArea.style.minWidth = `${rightAreaWidth}px`;
            rightArea.style.maxWidth = `${rightAreaWidth}px`;
        }
        
        const leftScroll = diagramContent.querySelector('.timetable-left-scroll');
        const rightScroll = diagramContent.querySelector('.timetable-right-scroll');
        const leftHeader = diagramContent.querySelector('.timetable-left-header');
        const leftGrid = diagramContent.querySelector('.timetable-left-grid');
        const rightHeader = diagramContent.querySelector('.timetable-right-header');
        const rightGrid = diagramContent.querySelector('.timetable-right-grid');
        
        const gap = 1; // CSS gap is 1px
        
        // Apply fixed cell size to left grid
        if (leftScroll && leftHeader && leftGrid) {
            const actualGridWidth = actualCols * fixedCellSize + gap * (actualCols - 1);
            const actualGridHeight = actualRows * fixedCellSize + gap * (actualRows - 1);
            
            leftHeader.setAttribute('data-cols', actualCols);
            leftGrid.setAttribute('data-cols', actualCols);
            leftGrid.setAttribute('data-rows', actualRows);
            leftHeader.style.gridTemplateColumns = `repeat(${actualCols}, ${fixedCellSize}px)`;
            leftGrid.style.gridTemplateColumns = `repeat(${actualCols}, ${fixedCellSize}px)`;
            leftGrid.style.gridTemplateRows = `repeat(${actualRows}, ${fixedCellSize}px)`;
            
            // Set explicit width to allow horizontal scrolling when columns exceed visible area
            leftGrid.style.width = `${actualGridWidth}px`;
            leftGrid.style.minWidth = `${actualGridWidth}px`;
            leftGrid.style.height = `${actualGridHeight}px`;
            leftGrid.style.minHeight = `${actualGridHeight}px`;
            leftHeader.style.width = `${actualGridWidth}px`;
            leftHeader.style.minWidth = `${actualGridWidth}px`;
        }
        
        // Apply fixed cell size to right grid (Isolated Tasks)
        if (rightScroll && rightHeader && rightGrid) {
            // Calculate actual rows needed for isolated tasks
            const isolatedTaskCount = isolatedTasks && isolatedTasks.length > 0 ? isolatedTasks.length : 0;
            const actualRightRows = Math.max(Math.ceil(isolatedTaskCount / rightCols), rightRows);
            
            const actualGridWidth = rightCols * fixedCellSize + gap * (rightCols - 1);
            const actualGridHeight = actualRightRows * fixedCellSize + gap * (actualRightRows - 1);
            
            rightHeader.setAttribute('data-cols', rightCols);
            rightGrid.setAttribute('data-cols', rightCols);
            rightGrid.setAttribute('data-rows', actualRightRows);
            
            rightHeader.style.gridTemplateColumns = `repeat(${rightCols}, ${fixedCellSize}px)`;
            rightGrid.style.gridTemplateColumns = `repeat(${rightCols}, ${fixedCellSize}px)`;
            rightGrid.style.gridTemplateRows = `repeat(${actualRightRows}, ${fixedCellSize}px)`;
            
            rightGrid.style.width = `${actualGridWidth}px`;
            rightGrid.style.minWidth = `${actualGridWidth}px`;
            rightGrid.style.height = `${actualGridHeight}px`;
            rightGrid.style.minHeight = `${actualGridHeight}px`;
            rightHeader.style.width = `${actualGridWidth}px`;
            rightHeader.style.minWidth = `${actualGridWidth}px`;
        }
        
    }, 0);
}

/**
 * Calculate fixed cell size based on new logic:
 * Cell width = (container width - gap) / 10
 * Right area (isolated tasks) = 3 cells + gap, right-aligned, fixed first
 * Left area (stage tasks) = remaining space
 * @param {HTMLElement} container - The main container element (timetable-wrapper)
 * @returns {Object} Object containing cellSize and rightAreaWidth
 */
function calculateFixedCellSize(container) {
    if (!container) {
        return { cellSize: 60, rightAreaWidth: 200 }; // Default fallback
    }
    
    // Get the full container width
    const containerWidth = container.clientWidth || container.offsetWidth || container.getBoundingClientRect().width;
    
    // Get computed styles to calculate borders and padding
    const computedStyle = window.getComputedStyle(container);
    const paddingLeft = parseFloat(computedStyle.paddingLeft) || 0;
    const paddingRight = parseFloat(computedStyle.paddingRight) || 0;
    const borderLeft = parseFloat(computedStyle.borderLeftWidth) || 0;
    const borderRight = parseFloat(computedStyle.borderRightWidth) || 0;
    
    // Calculate available width: container width minus padding and border
    const availableWidth = containerWidth - (paddingLeft + paddingRight + borderLeft + borderRight);
    
    // Get gap value from CSS variable (default 20px)
    const gap = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--gap')) || 20;
    
    // Cell width = (container width - gap) / 10
    const cellSize = Math.floor((availableWidth - gap) / 10);
    
    // Right area width = 3 cells + gap
    const rightAreaWidth = 3 * cellSize + gap;
    
    return { cellSize, rightAreaWidth };
}

function renderNodeDiagramFromCache() {
    // Always render timetable diagram, even if no layout (will show empty 9x5 grid)
    renderTimetableDiagram();
}

/**
 * Animate upstream connection lines for a task
 * @param {string} taskId - The task ID
 * @param {string} animationType - 'yellow' for start animation, 'red' for rollback animation
 */
function animateUpstreamConnections(taskId, animationType) {
    // Look for SVG in monitor tasks tree area first, then fallback to separate section
    const tasksTreeArea = document.querySelector('.monitor-tasks-tree-area') 
        || document.querySelector('.tasks-tree-section');
    
    if (!tasksTreeArea) {
        return;
    }
    
    const svg = tasksTreeArea.querySelector('.tree-connection-lines');
    if (!svg) {
        return;
    }
    
    // Find all connection lines that end at this task (upstream connections)
    const upstreamLines = svg.querySelectorAll(`path[data-to-task="${taskId}"]`);
    
    if (upstreamLines.length === 0) {
        return;
    }
    
    // Remove any existing animation classes
    upstreamLines.forEach(line => {
        line.classList.remove('animate-yellow-glow', 'animate-red-glow');
    });
    
    // Trigger reflow to ensure class removal is processed
    void svg.offsetHeight;
    
    // Add animation class based on type
    const animationClass = animationType === 'yellow' ? 'animate-yellow-glow' : 'animate-red-glow';
    
    // Animate lines sequentially (top to bottom for yellow, bottom to top for red)
    const linesArray = Array.from(upstreamLines);
    
    if (animationType === 'yellow') {
        // Yellow: animate from top to bottom (by dependency order)
        linesArray.forEach((line, index) => {
            setTimeout(() => {
                line.classList.add(animationClass);
                // Remove animation class after animation completes
                setTimeout(() => {
                    line.classList.remove(animationClass);
                }, 1000);
            }, index * 50); // Stagger animation by 50ms
        });
    } else {
        // Red: animate from bottom to top (reverse order)
        linesArray.reverse().forEach((line, index) => {
            setTimeout(() => {
                line.classList.add(animationClass);
                // Remove animation class after animation completes
                setTimeout(() => {
                    line.classList.remove(animationClass);
                }, 1000);
            }, index * 50); // Stagger animation by 50ms
        });
    }
}

// Mock execution (requires backend)
async function mockExecution() {
    // Load execution from database
    const execution = await loadExecution();
    if (!execution) {
        alert('Please generate plan first.');
        return;
    }

    const btn = mockExecutionBtn;
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Executing...';
    
    try {
        if (!socket || !socket.connected) {
            initializeWebSocket();
            await new Promise(resolve => setTimeout(resolve, 500));
        }
        
        // Call backend API to start mock execution
        const response = await fetch(`${API_BASE_URL}/mock-execution`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to start mock execution');
        }

        const data = await response.json();
        console.log('Mock execution started:', data.message);
        // Button will be re-enabled when execution completes via WebSocket event
    } catch (error) {
        console.error('Error in mock execution:', error);
        alert('Error: ' + error.message);
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

// Generate task timetable from execution.json
async function generateTimetable() {
    const btn = generateTimetableBtn;
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Loading...';
    
    try {
        // Load execution.json from database
        const execution = await loadExecution();
        if (!execution) {
            alert('No execution found. Ensure backend/db/test/ has execution.json.');
            btn.textContent = originalText;
            btn.disabled = false;
            return;
        }

        // Call API to generate timetable layout
        const response = await fetch(`${API_BASE_URL}/monitor/timetable`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ execution })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to generate timetable');
        }

        const data = await response.json();
        timetableLayout = data.layout;
        
        // Reset state tracking when generating new timetable
        previousTaskStates.clear();
        chainCache = buildChainCacheFromLayout(timetableLayout);

        // Render the timetable diagram
        renderTimetableDiagram();
        
        // Render tasks tree in separate area
        if (timetableLayout?.treeData?.length) {
            TaskTree.renderMonitorTasksTree(timetableLayout.treeData);
        }
        
        // Emit timetable layout via WebSocket if connected
        if (socket && socket.connected) {
            socket.emit('timetable-layout', { layout: timetableLayout });
        }

        btn.textContent = 'Loaded!';
        setTimeout(() => {
            btn.textContent = 'Load Example Execution';
        }, 2000);
    } catch (error) {
        console.error('Error generating timetable:', error);
        alert('Error: ' + error.message);
        btn.textContent = originalText;
    } finally {
        btn.disabled = false;
    }
}

// Event listeners for monitor
if (generateTimetableBtn) {
    generateTimetableBtn.addEventListener('click', generateTimetable);
}
if (mockExecutionBtn) {
    mockExecutionBtn.addEventListener('click', mockExecution);
}

// Initialize WebSocket on page load
initializeWebSocket();

// Plan tree is only loaded via WebSocket (plan-complete) when user generates a plan

// Initialize task node click handlers (popover for task details)
if (typeof TaskTree !== 'undefined' && TaskTree.initTaskNodeClickHandlers) {
    TaskTree.initTaskNodeClickHandlers();
}

// ========== Executor/Verifier ==========

function renderExecutors(executors, stats) {
    const executorGrid = document.getElementById('executorGrid');
    const executorTotal = document.getElementById('executorTotal');
    const executorBusy = document.getElementById('executorBusy');
    const executorIdle = document.getElementById('executorIdle');
    
    if (!executorGrid || !executorTotal || !executorBusy || !executorIdle) {
        return;
    }
    
    if (!executors || executors.length === 0) {
        executorGrid.innerHTML = '';
        executorTotal.textContent = '0';
        executorBusy.textContent = '0';
        executorIdle.textContent = '0';
        return;
    }
    
    // Use backend-provided stats directly (no calculation in frontend)
    executorTotal.textContent = stats.total || executors.length;
    executorBusy.textContent = stats.busy || 0;
    executorIdle.textContent = stats.idle || 0;
    
    let html = '';
    executors.forEach(executor => {
        const statusClass = executor.status === 'busy' ? 'executor-busy' : 
                           executor.status === 'failed' ? 'executor-failed' : 'executor-idle';
        const taskText = executor.taskId ? `Task: ${executor.taskId}` : '';
        html += `
            <div class="executor-item ${statusClass}">
                <div class="executor-id">Executor ${executor.id}</div>
                <div class="executor-status status-${executor.status}">${executor.status.toUpperCase()}</div>
                <div class="executor-task">${taskText}</div>
            </div>
        `;
    });
    
    executorGrid.innerHTML = html;
}

function renderVerifiers(verifiers, stats) {
    const verifierGrid = document.getElementById('verifierGrid');
    const verifierTotal = document.getElementById('verifierTotal');
    const verifierBusy = document.getElementById('verifierBusy');
    const verifierIdle = document.getElementById('verifierIdle');
    
    if (!verifierGrid || !verifierTotal || !verifierBusy || !verifierIdle) {
        return;
    }
    
    if (!verifiers || verifiers.length === 0) {
        verifierGrid.innerHTML = '';
        verifierTotal.textContent = '0';
        verifierBusy.textContent = '0';
        verifierIdle.textContent = '0';
        return;
    }
    
    // Use backend-provided stats directly (no calculation in frontend)
    verifierTotal.textContent = stats.total || verifiers.length;
    verifierBusy.textContent = stats.busy || 0;
    verifierIdle.textContent = stats.idle || 0;
    
    let html = '';
    verifiers.forEach(verifier => {
        const statusClass = verifier.status === 'busy' ? 'verifier-busy' : 
                           verifier.status === 'failed' ? 'verifier-failed' : 'verifier-idle';
        const taskText = verifier.taskId ? `Task: ${verifier.taskId}` : '';
        html += `
            <div class="verifier-item ${statusClass}">
                <div class="verifier-id">Verifier ${verifier.id}</div>
                <div class="verifier-status status-${verifier.status}">${verifier.status.toUpperCase()}</div>
                <div class="verifier-task">${taskText}</div>
            </div>
        `;
    });
    
    verifierGrid.innerHTML = html;
}

// Handle window resize
let resizeTimeout = null;
window.addEventListener('resize', () => {
    if (resizeTimeout) {
        clearTimeout(resizeTimeout);
    }
    resizeTimeout = setTimeout(() => {
        const diagramContent = document.getElementById('diagramArea');
        if (!diagramContent) return;
        
        // Get the main container for calculating fixed cell size
        const timetableWrapper = diagramContent.querySelector('.timetable-wrapper');
        if (!timetableWrapper) return;
        
        // Calculate fixed cell size: (container width - gap) / 10
        const { cellSize: fixedCellSize, rightAreaWidth } = calculateFixedCellSize(timetableWrapper);
        
        // Set right area width (3 cells + gap)
        const rightArea = diagramContent.querySelector('.timetable-right');
        if (rightArea) {
            rightArea.style.width = `${rightAreaWidth}px`;
            rightArea.style.minWidth = `${rightAreaWidth}px`;
            rightArea.style.maxWidth = `${rightAreaWidth}px`;
        }
        
        const leftScroll = diagramContent.querySelector('.timetable-left-scroll');
        const rightScroll = diagramContent.querySelector('.timetable-right-scroll');
        const leftHeader = diagramContent.querySelector('.timetable-left-header');
        const leftGrid = diagramContent.querySelector('.timetable-left-grid');
        const rightHeader = diagramContent.querySelector('.timetable-right-header');
        const rightGrid = diagramContent.querySelector('.timetable-right-grid');
        
        const gap = 1; // CSS gap is 1px
        
        // Apply fixed cell size to left grid
        if (leftScroll && leftHeader && leftGrid) {
            const actualCols = parseInt(leftGrid.getAttribute('data-cols')) || 7;
            const actualRows = parseInt(leftGrid.getAttribute('data-rows')) || 4;
            const actualGridWidth = actualCols * fixedCellSize + gap * (actualCols - 1);
            const actualGridHeight = actualRows * fixedCellSize + gap * (actualRows - 1);
            
            leftHeader.style.gridTemplateColumns = `repeat(${actualCols}, ${fixedCellSize}px)`;
            leftGrid.style.gridTemplateColumns = `repeat(${actualCols}, ${fixedCellSize}px)`;
            leftGrid.style.gridTemplateRows = `repeat(${actualRows}, ${fixedCellSize}px)`;
            
            leftGrid.style.width = `${actualGridWidth}px`;
            leftGrid.style.minWidth = `${actualGridWidth}px`;
            leftGrid.style.height = `${actualGridHeight}px`;
            leftGrid.style.minHeight = `${actualGridHeight}px`;
            leftHeader.style.width = `${actualGridWidth}px`;
            leftHeader.style.minWidth = `${actualGridWidth}px`;
        }
        
        // Apply fixed cell size to right grid (Isolated Tasks)
        if (rightScroll && rightHeader && rightGrid) {
            const rightCols = parseInt(rightGrid.getAttribute('data-cols')) || 3;
            const rightRows = parseInt(rightGrid.getAttribute('data-rows')) || 4;
            const actualGridWidth = rightCols * fixedCellSize + gap * (rightCols - 1);
            const actualGridHeight = rightRows * fixedCellSize + gap * (rightRows - 1);
            
            rightHeader.style.gridTemplateColumns = `repeat(${rightCols}, ${fixedCellSize}px)`;
            rightGrid.style.gridTemplateColumns = `repeat(${rightCols}, ${fixedCellSize}px)`;
            rightGrid.style.gridTemplateRows = `repeat(${rightRows}, ${fixedCellSize}px)`;
            
            rightGrid.style.width = `${actualGridWidth}px`;
            rightGrid.style.minWidth = `${actualGridWidth}px`;
            rightGrid.style.height = `${actualGridHeight}px`;
            rightGrid.style.minHeight = `${actualGridHeight}px`;
            rightHeader.style.width = `${actualGridWidth}px`;
            rightHeader.style.minWidth = `${actualGridWidth}px`;
        }
        
        // Redraw connection lines for monitor task tree after resize
        if (timetableLayout?.treeData?.length) {
            TaskTree.renderMonitorTasksTree(timetableLayout.treeData);
        }
        TaskTree.redrawPlannerConnectionLines?.();
    }, 150);
});
