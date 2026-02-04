const API_BASE_URL = 'http://localhost:3001/api';
const WS_URL = 'http://localhost:3001';

// WebSocket connection
let socket = null;

// DOM Elements
const settingsBtn = document.getElementById('settingsBtn');
const clearBtn = document.getElementById('clearBtn');
const planBtn = document.getElementById('planBtn');
const generateExecutionMapBtn = document.getElementById('generateExecutionMapBtn');
const abortPlanBtn = document.getElementById('abortPlanBtn');
const loadExampleBtn = document.getElementById('loadExampleBtn');
const loadDispatcherExampleBtn = document.getElementById('loadDispatcherExampleBtn');
const mockExecutionBtn = document.getElementById('mockExecutionBtn');
const queryArea = document.getElementById('queryArea');
const outputArea = document.getElementById('outputArea');
const diagramArea = document.getElementById('diagramArea');
const settingsModal = document.getElementById('settingsModal');
const closeBtn = document.querySelector('.close');
const saveConfigBtn = document.getElementById('saveConfigBtn');

// Abort controller for plan generation
let planAbortController = null;

// Store current plan
let currentPlan = null;

// Store database timestamp for plans polling
let lastPlansTimestamp = 0;
let plansPollingInterval = null;
const POLLING_INTERVAL_MS = 2000; // Poll every 2 seconds (for plans only)

// Chain cache - stores only id and dependencies for rendering
let chainCache = [];

// Store timetable layout data from backend
let timetableLayout = null;

// Settings form elements
const apiUrlInput = document.getElementById('apiUrl');
const apiKeyInput = document.getElementById('apiKey');
const modelInput = document.getElementById('model');
const temperatureInput = document.getElementById('temperature');

// Load configuration on page load
async function loadConfig() {
    try {
        const response = await fetch(`${API_BASE_URL}/config`);
        const config = await response.json();
        
        apiUrlInput.value = config.apiUrl || '';
        apiKeyInput.value = config.apiKey || '';
        modelInput.value = config.model || 'gpt-3.5-turbo';
        temperatureInput.value = config.temperature || 0.7;
    } catch (error) {
        // Intentionally silent
    }
}

// Save configuration
async function saveConfig() {
    const config = {
        apiUrl: apiUrlInput.value.trim(),
        apiKey: apiKeyInput.value.trim(),
        model: modelInput.value.trim() || 'gpt-3.5-turbo',
        temperature: parseFloat(temperatureInput.value) || 0.7
    };

    try {
        const response = await fetch(`${API_BASE_URL}/config`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });

        if (response.ok) {
            alert('Configuration saved successfully!');
            closeModal();
        } else {
            const error = await response.json();
            alert(`Failed to save configuration: ${error.error}`);
        }
    } catch (error) {
        alert(`Error saving configuration: ${error.message}`);
    }
}

// Helper function to update status message
function updateStatus(message) {
    outputArea.textContent = message;
    // Remove placeholder when there's content
    if (message) {
        outputArea.removeAttribute('data-placeholder');
    }
}

// Update button states based on current conditions
function updateButtonStates() {
    // Update planBtn: disabled if queryArea is empty
    const hasQuery = queryArea.textContent.trim().length > 0;
    planBtn.disabled = !hasQuery;
    
    // Update generateExecutionMapBtn: disabled if no plan in database
    const hasPlan = currentPlan !== null;
    generateExecutionMapBtn.disabled = !hasPlan;
    
    // Update mockExecutionBtn: disabled if no cache (already handled, but ensure consistency)
    const hasCache = chainCache && chainCache.length > 0;
    if (!hasCache) {
        mockExecutionBtn.disabled = true;
    }
}

// Helper function to clear output area and show placeholder
function clearOutputArea() {
    outputArea.textContent = '';
    outputArea.setAttribute('data-placeholder', 'Generated plan will appear here...');
}

// Generate plan and save to database (no display)
async function generatePlan() {
    const task = queryArea.textContent.trim();
    
    if (!task) {
        alert('Please enter a task');
        return;
    }
    
    // Update button states before starting
    updateButtonStates();

    planBtn.disabled = true;
    planBtn.style.display = 'none';
    abortPlanBtn.style.display = 'inline-block';
    abortPlanBtn.disabled = false;

    // Create abort controller for this request
    planAbortController = new AbortController();
    const startTime = Date.now();

    try {
        // Step 1: Generate plan using AI
        updateStatus('📡 Calling AI API...\n⏳ Waiting for response (no timeout)...');
        
        // Set up periodic status updates showing elapsed time
        const statusInterval = setInterval(() => {
            if (planAbortController.signal.aborted) {
                clearInterval(statusInterval);
                return;
            }
            const elapsedSeconds = Math.floor((Date.now() - startTime) / 1000);
            const minutes = Math.floor(elapsedSeconds / 60);
            const seconds = elapsedSeconds % 60;
            const timeStr = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
            updateStatus(`📡 Calling AI API...\n⏳ Waiting for response (${timeStr} elapsed)\n💡 Click "Abort" to cancel if needed...`);
        }, 1000); // Update every second
        
        let response;
        try {
            response = await fetch(`${API_BASE_URL}/plan`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ task }),
                signal: planAbortController.signal
            });
        } catch (fetchError) {
            if (fetchError.name === 'AbortError') {
                updateStatus('❌ Request aborted by user');
                throw new Error('Request aborted by user');
            }
            throw fetchError;
        } finally {
            // Clear the status update interval once we get a response (or error)
            clearInterval(statusInterval);
        }

        // Check if response is JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const text = await response.text();
            throw new Error(`Server returned non-JSON response: ${text.substring(0, 200)}`);
        }

        updateStatus('✅ AI response received\n📝 Parsing plan...');
        
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to generate plan');
        }

        // Step 2: Parse the plan
        const rawContent = data?.result?.choices?.[0]?.message?.content
            ?? data?.result?.content
            ?? JSON.stringify(data.result);
        
        let parsed;
        try {
            parsed = typeof rawContent === 'string' ? JSON.parse(rawContent) : rawContent;
        } catch (parseError) {
            throw new Error('Failed to parse plan: ' + parseError.message);
        }

        updateStatus('✅ Plan parsed successfully\n🔍 Validating plan structure...');

        // Step 3: Add original query to the plan before saving
        if (!parsed.plan_id) {
            throw new Error('Generated plan missing plan_id');
        }

        // Store the original query/task in the plan
        parsed.query = task;
        
        // Note: Status will be added later when mock execution is triggered
        // Do not initialize status here - keep plan clean without status fields

        updateStatus('✅ Plan validated\n💾 Saving to database...');

        // Step 4: Save plan to database (with original query included)
        const saveResponse = await fetch(`${API_BASE_URL}/plans`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(parsed)
        });

        // Check if save response is JSON
        const saveContentType = saveResponse.headers.get('content-type');
        if (!saveContentType || !saveContentType.includes('application/json')) {
            const saveText = await saveResponse.text();
            throw new Error(`Server returned non-JSON response when saving: ${saveText.substring(0, 200)}`);
        }

        const saveData = await saveResponse.json();

        if (!saveResponse.ok) {
            throw new Error(`Failed to save plan: ${saveData.error || 'Unknown error'}`);
        }

        updateStatus('✅ Plan saved to database successfully!\n\nPlan will be displayed automatically...');
        
        // Store the plan for dispatcher
        currentPlan = parsed;
        
        // Update button states after plan is saved
        updateButtonStates();
        
    } catch (error) {
        console.error('Error generating plan:', error);
        if (error.message !== 'Request aborted by user') {
            const errorMessage = `❌ Error: ${error.message}`;
            updateStatus(errorMessage);
            alert('Error generating plan: ' + error.message);
        }
        currentPlan = null;
    } finally {
        planBtn.disabled = false;
        planBtn.style.display = 'inline-block';
        abortPlanBtn.style.display = 'none';
        abortPlanBtn.disabled = true;
        planAbortController = null;
        // Update button states after plan generation completes
        updateButtonStates();
    }
}

// Abort plan generation
function abortPlanGeneration() {
    if (planAbortController) {
        planAbortController.abort();
        updateStatus('⏹️ Aborting request...');
    }
}

// Clear database
async function clearDatabase() {
    // Confirm before clearing
    const confirmed = confirm('Are you sure you want to clear all plans from the database? This action cannot be undone.');
    
    if (!confirmed) {
        return;
    }
    
    clearBtn.disabled = true;
    clearBtn.textContent = 'Clearing...';
    
    try {
        const response = await fetch(`${API_BASE_URL}/plans`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        // Check if response is JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const text = await response.text();
            throw new Error(`Server returned non-JSON response: ${text.substring(0, 200)}`);
        }
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to clear database');
        }
        
        // Success - clear the UI
        clearOutputArea();
        queryArea.textContent = '';
        currentPlan = null;
        
        // Clear chain cache
        chainCache = [];
        timetableLayout = null;
        
        // Clear diagram area
        const diagramContent = document.getElementById('diagramArea');
        if (diagramContent) {
            diagramContent.innerHTML = '<div class="execution-map"><div class="map-info">No execution map found. Generate or load a plan, then click "Generate Execution Map" to build the map.</div></div>';
        }
        
        // Update button states after clearing
        updateButtonStates();
        
        // Reset executor and verifier states, then reload and render
        try {
            const execRes = await fetch(`${API_BASE_URL}/executors/reset`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const verRes = await fetch(`${API_BASE_URL}/verifiers/reset`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const execData = execRes.ok ? await execRes.json() : null;
            const verData = verRes.ok ? await verRes.json() : null;
            if (execData?.executors && execData?.stats) renderExecutors(execData.executors, execData.stats);
            if (verData?.verifiers && verData?.stats) renderVerifiers(verData.verifiers, verData.stats);
        } catch (error) {
            console.error('Error resetting executors/verifiers:', error);
        }
        
        // The polling mechanism will automatically update the display
        alert('Database cleared successfully!');
        
    } catch (error) {
        console.error('Error clearing database:', error);
        alert('Error clearing database: ' + error.message);
    } finally {
        clearBtn.disabled = false;
        clearBtn.textContent = 'Clear';
    }
}

// Calculate cell size based on scroll container width and number of display columns
// This calculates the size for the visible 9 columns, then applies to all columns
function calculateCellSize(scrollContainer, displayCols) {
    if (!scrollContainer || displayCols === 0) {
        return 50; // Default size
    }
    // Get the actual available width of the scroll container
    const containerWidth = scrollContainer.clientWidth || scrollContainer.offsetWidth;
    const gap = 1; // gap between cells
    // Calculate cell size based on display columns (9): (container width - gaps) / display columns
    const cellSize = Math.floor((containerWidth - (gap * (displayCols - 1))) / displayCols);
    return Math.max(30, cellSize); // Minimum 30px
}

// Unified render function for timetable diagram
// Uses timetable layout data from backend
function renderTimetableDiagram() {
    const diagramContent = document.getElementById('diagramArea');
    
    // Show execution map
    let html = '<div class="execution-map">';
    
    if (!timetableLayout || !timetableLayout.grid) {
        html += '<div class="map-info">No execution map found. Generate or load a plan, then click "Generate Execution Map" to build the map.</div>';
        html += '</div>';
        diagramContent.innerHTML = html;
        return;
    }
    
    const { grid, maxRows, maxCols, isolatedTasks } = timetableLayout;
    
    // Fixed display dimensions: always show 9 columns and 5 rows
    const displayCols = 9;
    const displayRows = 5;
    // Actual data dimensions (may be larger)
    const actualCols = maxCols;
    const actualRows = maxRows;
    const rightCols = 9;
    const rightRows = isolatedTasks ? Math.max(Math.ceil(isolatedTasks.length / rightCols), 5) : 5;
    
    // Render timetable grid - simple left/right split
    html += '<div class="timetable-container">';
    html += '<div class="timetable-wrapper">';
    
    // Left side: Dependency tasks (supports horizontal and vertical scrolling)
    html += '<div class="timetable-left">';
    html += '<div class="timetable-left-scroll">';
    html += '<div class="timetable-left-header timetable-header-row">';
    // Render all actual columns (may be more than 9)
    for (let col = 0; col < actualCols; col++) {
        html += `<div class="timetable-header-cell">Stage ${col + 1}</div>`;
    }
    html += '</div>';
    
    html += '<div class="timetable-left-grid timetable-grid">';
    // Render all actual rows (may be more than 5)
    for (let row = 0; row < actualRows; row++) {
        for (let col = 0; col < actualCols; col++) {
            const task = (row < grid.length && col < grid[row].length) ? grid[row][col] : null;
            if (task && task.id) {
                const status = task.status || 'undone';
                html += `<div class="timetable-cell task-status-${status}" data-task-id="${task.id}">${task.id}</div>`;
            } else {
                html += `<div class="timetable-cell timetable-cell-empty"></div>`;
            }
        }
    }
    html += '</div>';
    html += '</div>';
    html += '</div>';
    
    // Right side: Isolated tasks (only vertical scrolling)
    html += '<div class="timetable-right">';
    html += '<div class="timetable-right-scroll">';
    html += '<div class="timetable-right-header timetable-header-row">';
    html += `<div class="timetable-header-cell" style="grid-column: 1 / -1;">Isolated Tasks</div>`;
    html += '</div>';
    
    html += '<div class="timetable-right-grid timetable-grid">';
    for (let row = 0; row < rightRows; row++) {
        for (let col = 0; col < rightCols; col++) {
            const idx = row * rightCols + col;
            if (isolatedTasks && idx < isolatedTasks.length && isolatedTasks[idx] && isolatedTasks[idx].id) {
                const task = isolatedTasks[idx];
                const status = task.status || 'undone';
                html += `<div class="timetable-cell task-status-${status}" data-task-id="${task.id}">${task.id}</div>`;
            } else {
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
    diagramContent.innerHTML = html;
    
    // Calculate and apply cell sizes after DOM is rendered
    setTimeout(() => {
        const leftScroll = diagramContent.querySelector('.timetable-left-scroll');
        const rightScroll = diagramContent.querySelector('.timetable-right-scroll');
        const leftHeader = diagramContent.querySelector('.timetable-left-header');
        const leftGrid = diagramContent.querySelector('.timetable-left-grid');
        const rightHeader = diagramContent.querySelector('.timetable-right-header');
        const rightGrid = diagramContent.querySelector('.timetable-right-grid');
        
        if (leftScroll && leftHeader && leftGrid) {
            // Calculate cell size based on display columns (9) and container width
            const leftCellSize = calculateCellSize(leftScroll, displayCols);
            // Apply to actual columns (may be more than 9)
            leftHeader.setAttribute('data-cols', actualCols);
            leftGrid.setAttribute('data-cols', actualCols);
            leftGrid.setAttribute('data-rows', actualRows);
            leftHeader.style.gridTemplateColumns = `repeat(${actualCols}, ${leftCellSize}px)`;
            leftGrid.style.gridTemplateColumns = `repeat(${actualCols}, ${leftCellSize}px)`;
            leftGrid.style.gridTemplateRows = `repeat(${actualRows}, ${leftCellSize}px)`;
            
            // Note: Header and grid are in the same scroll container (leftScroll),
            // so they scroll together automatically. The sticky positioning keeps
            // the header visible at the top during vertical scrolling.
        }
        
        if (rightScroll && rightHeader && rightGrid) {
            const rightCellSize = calculateCellSize(rightScroll, rightCols);
            rightHeader.setAttribute('data-cols', rightCols);
            rightGrid.setAttribute('data-cols', rightCols);
            rightGrid.setAttribute('data-rows', rightRows);
            rightHeader.style.gridTemplateColumns = `repeat(${rightCols}, ${rightCellSize}px)`;
            rightGrid.style.gridTemplateColumns = `repeat(${rightCols}, ${rightCellSize}px)`;
            rightGrid.style.gridTemplateRows = `repeat(${rightRows}, ${rightCellSize}px)`;
        }
    }, 0);
}

// Render node diagram using timetable layout from backend
function renderNodeDiagramFromCache() {
    if (!timetableLayout) {
        const diagramContent = document.getElementById('diagramArea');
        if (diagramContent) {
            diagramContent.innerHTML = '<div class="execution-map"><div class="map-info">No execution map found. Generate or load a plan, then click "Generate Execution Map" to build the map.</div></div>';
        }
        console.warn('renderNodeDiagramFromCache: timetableLayout is empty');
        return;
    }
    
    renderTimetableDiagram();
}

// Load example plan from mock_plan.json (backend handles saving to database)
async function loadDispatcherExample() {
    // Disable button during loading
    const btn = document.getElementById('loadDispatcherExampleBtn');
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Loading...';
    
    try {
        // Backend will read mock_plan.json and save to plans database
        const response = await fetch(`${API_BASE_URL}/load-mock-plan`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        // Check if response is JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const text = await response.text();
            throw new Error(`Server returned non-JSON response: ${text.substring(0, 200)}`);
        }

        const data = await response.json();

        if (!response.ok) {
            throw new Error(`Failed to load mock plan: ${data.error || 'Unknown error'}`);
        }

        // Success - plan saved to database by backend
        // The polling mechanism will automatically update the display
        alert('Example plan loaded from mock_plan.json and saved to database successfully!');
        
        // Update button states after loading example
        // Note: polling will update currentPlan, which will trigger updateButtonStates
        setTimeout(() => updateButtonStates(), 500);
        
    } catch (error) {
        console.error('Error loading dispatcher example:', error);
        alert('Error loading dispatcher example: ' + error.message);
    } finally {
        // Re-enable button
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

// Example task
const exampleTask = `Research the impact of artificial intelligence on healthcare delivery systems. Analyze how AI technologies are being integrated into patient care, diagnostic processes, and administrative workflows. Include case studies from different healthcare settings and evaluate both benefits and challenges.`;

// Load example task
function loadExample() {
    queryArea.textContent = exampleTask;
}

// Initialize WebSocket connection
function initializeWebSocket() {
    if (socket && socket.connected) {
        return; // Already connected
    }

    socket = io(WS_URL);

    socket.on('connect', () => {
        console.log('WebSocket connected');
    });

    socket.on('disconnect', () => {
        console.log('WebSocket disconnected');
    });

    // Listen for timetable layout updates
    socket.on('timetable-layout', (data) => {
        timetableLayout = data.layout;
        
        // Update chain cache from timetable layout
        chainCache = [];
        const { grid, isolatedTasks } = timetableLayout;
        grid.forEach(row => {
            row.forEach(cell => {
                if (cell && cell.id) {
                    chainCache.push({
                        id: cell.id,
                        dependencies: cell.dependencies || [],
                        status: cell.status || 'undone'
                    });
                }
            });
        });
        if (isolatedTasks) {
            isolatedTasks.forEach(task => {
                if (task && task.id) {
                    chainCache.push({
                        id: task.id,
                        dependencies: task.dependencies || [],
                        status: task.status || 'undone'
                    });
                }
            });
        }
        
        renderNodeDiagramFromCache();
    });

    // Listen for task state updates
    socket.on('task-states-update', (data) => {
        if (data.tasks && Array.isArray(data.tasks)) {
            // Update chain cache
            data.tasks.forEach(taskState => {
                const cacheNode = chainCache.find(node => node.id === taskState.id);
                if (cacheNode) {
                    cacheNode.status = taskState.status;
                }
            });

            // Update UI cells
            const diagramContent = document.getElementById('diagramArea');
            data.tasks.forEach(taskState => {
                const cell = diagramContent?.querySelector(`[data-task-id="${taskState.id}"]`);
                if (cell) {
                    cell.classList.remove('task-status-undone', 'task-status-doing', 'task-status-verifying', 'task-status-done', 'task-status-verification-failed', 'task-status-execution-failed');
                    cell.classList.add(`task-status-${taskState.status}`);
                }
            });
        }
    });

    // Listen for executor state updates
    socket.on('executor-states-update', (data) => {
        if (data.executors && data.stats) {
            renderExecutors(data.executors, data.stats);
        }
    });

    // Listen for verifier state updates
    socket.on('verifier-states-update', (data) => {
        if (data.verifiers && data.stats) {
            renderVerifiers(data.verifiers, data.stats);
        }
    });

    // Listen for execution errors
    socket.on('execution-error', (data) => {
        console.error('Execution error:', data.error);
        alert('Execution error: ' + data.error);
        mockExecutionBtn.disabled = false;
        mockExecutionBtn.textContent = 'Mock Execution';
        // Update button states after execution error
        updateButtonStates();
    });

    // Listen for execution completion
    socket.on('execution-complete', (data) => {
        console.log(`Execution complete: ${data.completed}/${data.total} tasks completed`);
        const btn = mockExecutionBtn;
        btn.disabled = false;
        btn.textContent = 'Execution Complete!';
        setTimeout(() => {
            btn.textContent = 'Mock Execution';
            // Update button states after execution completes
            updateButtonStates();
        }, 2000);
    });
}

// Initialize WebSocket on page load
initializeWebSocket();

// Mock execution process - only uses cache, not database
async function mockExecution() {
    const btn = mockExecutionBtn;
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Executing...';
    
    console.log('Mock execution started');
    
    try {
        // Check if cache exists (chainCache should be populated by generateExecutionMap)
        if (!chainCache || chainCache.length === 0) {
            throw new Error('No execution map cache found. Please generate execution map first.');
        }

        // Ensure WebSocket is connected
        if (!socket || !socket.connected) {
            initializeWebSocket();
            // Wait a bit for connection
            await new Promise(resolve => setTimeout(resolve, 500));
        }
        
        // Start execution on backend - backend will use cache only
        // Backend will:
        // 1. Use cached timetable layout
        // 2. Broadcast timetable-layout via WebSocket
        // 3. Broadcast task-states-update and executor-states-update in real-time
        const executionResponse = await fetch(`${API_BASE_URL}/mock-execution`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
            // No body needed - backend uses cache
        });

        if (!executionResponse.ok) {
            const errorData = await executionResponse.json().catch(() => ({ error: 'Unknown error' }));
            throw new Error(errorData.error || 'Failed to start mock execution');
        }

        // Execution is now running on backend, updates will come via WebSocket
        // The completion will be handled by the 'execution-complete' event
        // Button will be re-enabled by WebSocket event handlers
        
    } catch (error) {
        console.error('Error in mock execution:', error);
        console.error('Error stack:', error.stack);
        alert('Error in mock execution: ' + (error.message || String(error)));
        btn.textContent = originalText;
        btn.disabled = false;
        // Update button states after error
        updateButtonStates();
    }
    // Note: btn.disabled will be set to false by the 'execution-complete' or 'execution-error' WebSocket event
}

// Modal functions
function openModal() {
    settingsModal.style.display = 'block';
    loadConfig();
}

function closeModal() {
    settingsModal.style.display = 'none';
}

// Generate execution map handler - gets timetable layout from backend
async function generateExecutionMap() {
    const btn = generateExecutionMapBtn;
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Generating...';
    
    try {
        // Step 1: Load the latest plan from database
        const plansResponse = await fetch(`${API_BASE_URL}/plans`);
        
        const plansContentType = plansResponse.headers.get('content-type');
        if (!plansContentType || !plansContentType.includes('application/json')) {
            const text = await plansResponse.text();
            throw new Error(`Server returned non-JSON response: ${text.substring(0, 200)}`);
        }
        
        const plansData = await plansResponse.json();
        
        if (!plansResponse.ok || !plansData.plans || plansData.plans.length === 0) {
            throw new Error('No plans found in database. Please generate a plan first.');
        }
        
        const latestPlan = plansData.plans[plansData.plans.length - 1];
        
        // Step 2: Get timetable layout from backend
        const layoutResponse = await fetch(`${API_BASE_URL}/timetable-layout`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ planId: latestPlan.plan_id })
        });
        
        const layoutContentType = layoutResponse.headers.get('content-type');
        if (!layoutContentType || !layoutContentType.includes('application/json')) {
            const text = await layoutResponse.text();
            throw new Error(`Server returned non-JSON response: ${text.substring(0, 200)}`);
        }
        
        const layoutData = await layoutResponse.json();
        
        if (!layoutResponse.ok) {
            throw new Error(`Failed to generate timetable layout: ${layoutData.error || 'Unknown error'}`);
        }
        
        // Store timetable layout
        timetableLayout = layoutData.layout;
        
        // Step 3: Build chain cache from layout for status tracking during mock execution
        chainCache = [];
        const { grid, isolatedTasks } = timetableLayout;
        
        // Extract tasks from grid
        grid.forEach(row => {
            row.forEach(cell => {
                if (cell && cell.id) {
                    chainCache.push({
                        id: cell.id,
                        dependencies: cell.dependencies || [],
                        status: cell.status || 'undone'
                    });
                }
            });
        });
        
        // Add isolated tasks
        if (isolatedTasks) {
            isolatedTasks.forEach(task => {
                if (task && task.id) {
                    chainCache.push({
                        id: task.id,
                        dependencies: task.dependencies || [],
                        status: task.status || 'undone'
                    });
                }
            });
        }
        
        // Step 4: Render using timetable layout
        try {
            renderNodeDiagramFromCache();
            
            // Verify rendering succeeded
            const diagramContent = document.getElementById('diagramArea');
            if (!diagramContent || diagramContent.innerHTML.trim() === '') {
                throw new Error('Failed to render execution map. Diagram area is empty.');
            }
        } catch (renderError) {
            console.error('Error rendering execution map:', renderError);
            throw new Error('Failed to render execution map: ' + renderError.message);
        }
        
        btn.textContent = 'Generated!';
        setTimeout(() => {
            btn.textContent = originalText;
        }, 1000);
        
        // Enable mock execution button now that cache is ready
        mockExecutionBtn.disabled = false;
        
    } catch (error) {
        console.error('Error generating execution map:', error);
        alert('Error generating execution map: ' + error.message);
        btn.textContent = originalText;
    } finally {
        btn.disabled = false;
        // Update button states
        updateButtonStates();
    }
}

// Event listeners
settingsBtn.addEventListener('click', openModal);
closeBtn.addEventListener('click', closeModal);
saveConfigBtn.addEventListener('click', saveConfig);
planBtn.addEventListener('click', generatePlan);
generateExecutionMapBtn.addEventListener('click', generateExecutionMap);
abortPlanBtn.addEventListener('click', abortPlanGeneration);
clearBtn.addEventListener('click', clearDatabase);
loadExampleBtn.addEventListener('click', loadExample);
loadDispatcherExampleBtn.addEventListener('click', loadDispatcherExample);
mockExecutionBtn.addEventListener('click', (e) => {
    console.log('Mock execution button clicked');
    try {
        mockExecution().catch(error => {
            console.error('Unhandled error in mockExecution:', error);
            alert('Error in mock execution: ' + error.message);
            const btn = mockExecutionBtn;
            btn.disabled = false;
            btn.textContent = 'Mock Execution';
        });
    } catch (error) {
        console.error('Error setting up mock execution:', error);
        alert('Error: ' + error.message);
    }
});

// Close modal when clicking outside
window.addEventListener('click', (event) => {
    if (event.target === settingsModal) {
        closeModal();
    }
});

// Extract only AI-generated fields from plan (exclude query and status fields)
function extractAIGeneratedPlan(plan) {
    const raw = plan.task_list || plan.workflow?.task_list || [];
    const task_list = raw.map(task => {
        const { status, ...rest } = task;
        return rest;
    });
    return {
        plan_id: plan.plan_id,
        objective: plan.objective,
        task_list
    };
}

// Load plans from database and display in output area
async function loadPlansFromDatabase() {
    try {
        const response = await fetch(`${API_BASE_URL}/plans`);
        
        // Check if response is JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const text = await response.text();
            console.error('Server returned non-JSON response for plans:', text.substring(0, 200));
            return;
        }
        
        const data = await response.json();
        
        if (response.ok && data.plans && data.plans.length > 0) {
            // Display the most recent plan (last one in array)
            const latestPlan = data.plans[data.plans.length - 1];
            
            // Extract only AI-generated fields for display
            const aiGeneratedPlan = extractAIGeneratedPlan(latestPlan);
            outputArea.textContent = JSON.stringify(aiGeneratedPlan, null, 2);
            outputArea.removeAttribute('data-placeholder');
            
            // Display the query in the query area
            if (latestPlan.query) {
                queryArea.textContent = latestPlan.query;
            } else {
                queryArea.textContent = '';
            }
            
            // Store the full plan for dispatcher (needs all fields)
            currentPlan = latestPlan;
        } else if (response.ok && data.plans && data.plans.length === 0) {
            // No plans in database - show placeholder
            clearOutputArea();
            queryArea.textContent = '';
            currentPlan = null;
        } else if (!response.ok) {
            // Handle error response
            updateStatus(`Error loading plans: ${data.error || 'Unknown error'}`);
            queryArea.textContent = '';
            currentPlan = null;
        }
        
        // Update button states after loading plans
        updateButtonStates();
    } catch (error) {
        console.error('Error loading plans:', error);
        updateStatus(`Error: ${error.message}`);
        queryArea.textContent = '';
        currentPlan = null;
    }
}

// Check for database changes (for plans)
async function checkPlansDatabaseChanges() {
    try {
        const response = await fetch(`${API_BASE_URL}/db-timestamp`);
        
        // Check if response is JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const text = await response.text();
            console.error('Server returned non-JSON response for db-timestamp:', text.substring(0, 200));
            return;
        }
        
        const data = await response.json();
        
        if (response.ok && data.timestamp !== undefined) {
            // If timestamp changed, reload plans
            if (data.timestamp !== lastPlansTimestamp) {
                lastPlansTimestamp = data.timestamp;
                await loadPlansFromDatabase();
            }
        }
    } catch (error) {
        console.error('Error checking plans database changes:', error);
        // Silently fail for polling - don't show error to user
    }
}

// Start polling for plans database changes
function startPlansPolling() {
    // Stop existing polling if any
    if (plansPollingInterval) {
        clearInterval(plansPollingInterval);
    }
    
    // Initial load
    loadPlansFromDatabase();
    
    // Set up polling interval
    plansPollingInterval = setInterval(checkPlansDatabaseChanges, POLLING_INTERVAL_MS);
}

// Stop polling for plans
function stopPlansPolling() {
    if (plansPollingInterval) {
        clearInterval(plansPollingInterval);
        plansPollingInterval = null;
    }
}


// Handle placeholder for contenteditable query area
function updateQueryPlaceholder() {
    if (queryArea.textContent.trim() === '') {
        queryArea.setAttribute('data-placeholder', 'Enter your research task here...');
    } else {
        queryArea.removeAttribute('data-placeholder');
    }
}

queryArea.addEventListener('input', () => {
    updateQueryPlaceholder();
    updateButtonStates(); // Update button states when input changes
});
queryArea.addEventListener('blur', () => {
    updateQueryPlaceholder();
    updateButtonStates(); // Update button states on blur
});
queryArea.addEventListener('focus', () => {
    if (queryArea.textContent.trim() === '') {
        queryArea.textContent = '';
    }
    updateButtonStates(); // Update button states on focus
});

// Load config on page load
loadConfig();

// Start polling for plans (for planner section)
startPlansPolling();

// Initialize button states on page load
updateButtonStates();

// Load executor and verifier states on page load (default backend pool)
loadExecutorStates();
loadVerifierStates();

// Handle window resize - recalculate cell sizes
let resizeTimeout = null;
window.addEventListener('resize', () => {
    if (resizeTimeout) {
        clearTimeout(resizeTimeout);
    }
    resizeTimeout = setTimeout(() => {
        const diagramContent = document.getElementById('diagramArea');
        if (!diagramContent) return;
        
        const leftScroll = diagramContent.querySelector('.timetable-left-scroll');
        const rightScroll = diagramContent.querySelector('.timetable-right-scroll');
        const leftHeader = diagramContent.querySelector('.timetable-left-header');
        const leftGrid = diagramContent.querySelector('.timetable-left-grid');
        const rightHeader = diagramContent.querySelector('.timetable-right-header');
        const rightGrid = diagramContent.querySelector('.timetable-right-grid');
        
        if (leftScroll && leftHeader && leftGrid) {
            const actualCols = parseInt(leftGrid.getAttribute('data-cols')) || 9;
            const actualRows = parseInt(leftGrid.getAttribute('data-rows')) || 5;
            const displayCols = 9; // Always calculate based on 9 display columns
            const leftCellSize = calculateCellSize(leftScroll, displayCols);
            leftHeader.style.gridTemplateColumns = `repeat(${actualCols}, ${leftCellSize}px)`;
            leftGrid.style.gridTemplateColumns = `repeat(${actualCols}, ${leftCellSize}px)`;
            leftGrid.style.gridTemplateRows = `repeat(${actualRows}, ${leftCellSize}px)`;
        }
        
        if (rightScroll && rightHeader && rightGrid) {
            const rightCols = parseInt(rightGrid.getAttribute('data-cols')) || 9;
            const rightRows = parseInt(rightGrid.getAttribute('data-rows')) || 5;
            const rightCellSize = calculateCellSize(rightScroll, rightCols);
            rightHeader.style.gridTemplateColumns = `repeat(${rightCols}, ${rightCellSize}px)`;
            rightGrid.style.gridTemplateColumns = `repeat(${rightCols}, ${rightCellSize}px)`;
            rightGrid.style.gridTemplateRows = `repeat(${rightRows}, ${rightCellSize}px)`;
        }
    }, 150);
});

// Stop polling when page is hidden (optional optimization)
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        stopPlansPolling();
    } else {
        startPlansPolling();
    }
});

// Executor state management
async function loadExecutorStates() {
    try {
        const response = await fetch(`${API_BASE_URL}/executors`);
        
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const text = await response.text();
            console.error('Server returned non-JSON response for executors:', text.substring(0, 200));
            return;
        }
        
        const data = await response.json();
        
        if (response.ok && data.executors && data.stats) {
            renderExecutors(data.executors, data.stats);
        }
    } catch (error) {
        console.error('Error loading executor states:', error);
    }
}

async function loadVerifierStates() {
    try {
        const response = await fetch(`${API_BASE_URL}/verifiers`);
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const text = await response.text();
            console.error('Server returned non-JSON response for verifiers:', text.substring(0, 200));
            return;
        }
        const data = await response.json();
        if (response.ok && data.verifiers && data.stats) {
            renderVerifiers(data.verifiers, data.stats);
        }
    } catch (error) {
        console.error('Error loading verifier states:', error);
    }
}

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
    
    // Validate stats consistency
    // Use actual executor array length as source of truth for total
    const actualTotal = executors.length;
    const total = stats.total !== undefined ? stats.total : actualTotal;
    
    // Recalculate stats from executor array (source of truth)
    let busy = executors.filter(e => e.status === 'busy').length;
    let idle = executors.filter(e => e.status === 'idle').length;
    let failed = executors.filter(e => e.status === 'failed').length;
    
    // Validate consistency
    if (busy + idle + failed !== actualTotal) {
        console.warn(`Executor stats inconsistency detected: busy=${busy}, idle=${idle}, failed=${failed}, actualTotal=${actualTotal}, backendTotal=${total}`);
        // Fix any invalid states
        executors.forEach(executor => {
            if (executor.status !== 'busy' && executor.status !== 'idle' && executor.status !== 'failed') {
                console.warn(`Invalid executor status: ${executor.id} has status "${executor.status}", resetting to idle`);
                executor.status = 'idle';
            }
        });
        // Recalculate after fixing
        busy = executors.filter(e => e.status === 'busy').length;
        idle = executors.filter(e => e.status === 'idle').length;
        failed = executors.filter(e => e.status === 'failed').length;
    }
    
    // Use actualTotal as the authoritative total
    const finalTotal = actualTotal;
    
    // Update stats (use recalculated values)
    executorTotal.textContent = finalTotal;
    executorBusy.textContent = busy;
    executorIdle.textContent = idle;
    
    // Render executor grid - also recalculate stats from executor array as validation
    let html = '';
    let actualBusy = 0;
    let actualIdle = 0;
    let actualFailed = 0;
    
    executors.forEach(executor => {
        // Validate executor status
        if (executor.status !== 'busy' && executor.status !== 'idle' && executor.status !== 'failed') {
            console.warn(`Invalid executor status: executor ${executor.id} has status "${executor.status}"`);
            executor.status = 'idle'; // Default to idle
        }
        
        // Count actual states
        if (executor.status === 'busy') {
            actualBusy++;
        } else if (executor.status === 'failed') {
            actualFailed++;
        } else {
            actualIdle++;
        }
        
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
    
    // Final validation: ensure displayed stats match actual counts
    if (actualBusy !== busy || actualIdle !== idle || actualFailed !== failed) {
        console.warn(`Stats mismatch after recalculation: expected busy=${busy}, idle=${idle}, failed=${failed}, but executor array shows busy=${actualBusy}, idle=${actualIdle}, failed=${actualFailed}`);
        // Use actual counts from array
        busy = actualBusy;
        idle = actualIdle;
        failed = actualFailed;
        // Update stats display with corrected values
        executorTotal.textContent = finalTotal;
        executorBusy.textContent = busy;
        executorIdle.textContent = idle;
    }
    
    executorGrid.innerHTML = html;
}

// Verifier state management
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
    
    // Validate stats consistency
    // Use actual verifier array length as source of truth for total
    const actualTotal = verifiers.length;
    const total = stats.total !== undefined ? stats.total : actualTotal;
    
    // Recalculate stats from verifier array (source of truth)
    let busy = verifiers.filter(v => v.status === 'busy').length;
    let idle = verifiers.filter(v => v.status === 'idle').length;
    let failed = verifiers.filter(v => v.status === 'failed').length;
    
    // Validate consistency
    if (busy + idle + failed !== actualTotal) {
        console.warn(`Verifier stats inconsistency detected: busy=${busy}, idle=${idle}, failed=${failed}, actualTotal=${actualTotal}, backendTotal=${total}`);
        // Fix any invalid states
        verifiers.forEach(verifier => {
            if (verifier.status !== 'busy' && verifier.status !== 'idle' && verifier.status !== 'failed') {
                console.warn(`Invalid verifier status: ${verifier.id} has status "${verifier.status}", resetting to idle`);
                verifier.status = 'idle';
            }
        });
        // Recalculate after fixing
        busy = verifiers.filter(v => v.status === 'busy').length;
        idle = verifiers.filter(v => v.status === 'idle').length;
        failed = verifiers.filter(v => v.status === 'failed').length;
    }
    
    // Use actualTotal as the authoritative total
    const finalTotal = actualTotal;
    
    // Update stats (use recalculated values)
    verifierTotal.textContent = finalTotal;
    verifierBusy.textContent = busy;
    verifierIdle.textContent = idle;
    
    // Render verifier grid - also recalculate stats from verifier array as validation
    let html = '';
    let actualBusy = 0;
    let actualIdle = 0;
    let actualFailed = 0;
    
    verifiers.forEach(verifier => {
        // Validate verifier status
        if (verifier.status !== 'busy' && verifier.status !== 'idle' && verifier.status !== 'failed') {
            console.warn(`Invalid verifier status: verifier ${verifier.id} has status "${verifier.status}"`);
            verifier.status = 'idle'; // Default to idle
        }
        
        // Count actual states
        if (verifier.status === 'busy') {
            actualBusy++;
        } else if (verifier.status === 'failed') {
            actualFailed++;
        } else {
            actualIdle++;
        }
        
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
    
    // Final validation: ensure displayed stats match actual counts
    if (actualBusy !== busy || actualIdle !== idle || actualFailed !== failed) {
        console.warn(`Verifier stats mismatch after recalculation: expected busy=${busy}, idle=${idle}, failed=${failed}, but verifier array shows busy=${actualBusy}, idle=${actualIdle}, failed=${actualFailed}`);
        // Use actual counts from array
        busy = actualBusy;
        idle = actualIdle;
        failed = actualFailed;
        // Update stats display with corrected values
        verifierTotal.textContent = finalTotal;
        verifierBusy.textContent = busy;
        verifierIdle.textContent = idle;
    }
    
    verifierGrid.innerHTML = html;
}

// Initialize WebSocket on page load
initializeWebSocket();
