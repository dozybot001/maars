const express = require('express');
const cors = require('cors');
const fs = require('fs').promises;
const path = require('path');
const http = require('http');
const { Server } = require('socket.io');
const planner = require('./planner');
const dispatcher = require('./dispatcher');
const db = require('./db');
const executorManager = require('./executor/manager');
const verifierManager = require('./verifier/manager');
const ExecutorRunner = require('./executor/runner');

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: {
    origin: "*",
    methods: ["GET", "POST"]
  }
});

const PORT = process.env.PORT || 3001;
const CONFIG_FILE = path.join(__dirname, 'config.json');

// Create executor runner instance
const executorRunner = new ExecutorRunner(io);

app.use(cors());
app.use(express.json());

// Default configuration
const defaultConfig = {
  apiUrl: '',
  apiKey: '',
  model: 'gpt-3.5-turbo',
  temperature: 0.7
};

// Load configuration
async function loadConfig() {
  try {
    const data = await fs.readFile(CONFIG_FILE, 'utf8');
    return JSON.parse(data);
  } catch (error) {
    return defaultConfig;
  }
}

// Save configuration
async function saveConfig(config) {
  await fs.writeFile(CONFIG_FILE, JSON.stringify(config, null, 2));
}

// ========== API ROUTES (must come before static file serving) ==========

// Get configuration endpoint
app.get('/api/config', async (req, res) => {
  try {
    const config = await loadConfig();
    res.json(config);
  } catch (error) {
    res.status(500).json({ error: 'Failed to load configuration' });
  }
});

// Update configuration endpoint
app.post('/api/config', async (req, res) => {
  try {
    const config = req.body;
    await saveConfig(config);
    res.json({ success: true, config });
  } catch (error) {
    res.status(500).json({ error: 'Failed to save configuration' });
  }
});

// AI communication endpoint
app.post('/api/plan', async (req, res) => {
  try {
    const { task } = req.body;
    const config = await loadConfig();

    const result = await planner.generatePlan(task, config);
    res.json({ result });
  } catch (error) {
    console.error('Plan generation error:', error.message);
    
    if (error.response) {
      if (error.response.status === 401) {
        return res.status(401).json({
          error: 'Authentication failed. Please verify your API key.'
        });
      }

      return res.status(error.response.status).json({
        error: `API request failed: ${error.response.status} ${error.response.statusText || ''}`
      });
    } else if (error.request) {
      return res.status(500).json({
        error: error.message || 'No response from API. Please check your API URL and network connection.'
      });
    }

    if (error.message && (error.message.includes('API configuration') || error.message.includes('API URL'))) {
      return res.status(400).json({
        error: error.message
      });
    }

    return res.status(500).json({
      error: error.message || 'Failed to communicate with AI.'
    });
  }
});

// Dispatcher endpoint - generate execution sequence from plan
app.post('/api/dispatcher', async (req, res) => {
  try {
    const { plan } = req.body;
    
    if (!plan) {
      return res.status(400).json({
        error: 'Plan is required'
      });
    }

    const executionSequence = dispatcher.generateExecutionSequence(plan);
    res.json({ result: executionSequence });
  } catch (error) {
    console.error('Dispatcher error:', error);
    return res.status(500).json({
      error: error.message || 'Failed to generate execution sequence'
    });
  }
});

// Database endpoints for plans
// Get all plans
app.get('/api/plans', async (req, res) => {
  try {
    const plans = await db.getAllPlans();
    res.json({ plans });
  } catch (error) {
    console.error('Error loading plans:', error);
    res.status(500).json({ error: 'Failed to load plans' });
  }
});

// Save a plan to database
app.post('/api/plans', async (req, res) => {
  try {
    const plan = req.body;
    
    if (!plan.plan_id) {
      return res.status(400).json({
        error: 'Plan ID is required'
      });
    }

    const result = await db.savePlan(plan);
    res.json(result);
  } catch (error) {
    console.error('Error saving plan:', error);
    res.status(500).json({
      error: error.message || 'Failed to save plan'
    });
  }
});

// Clear all plans from database (must be before /api/plans/:planId)
app.delete('/api/plans', async (req, res) => {
  try {
    await db.clearAllPlans();
    res.json({ success: true });
  } catch (error) {
    console.error('Error clearing plans:', error);
    res.status(500).json({
      error: error.message || 'Failed to clear database'
    });
  }
});

// Get a plan by ID
app.get('/api/plans/:planId', async (req, res) => {
  try {
    const { planId } = req.params;
    const plan = await db.getPlanById(planId);
    
    if (!plan) {
      return res.status(404).json({ error: 'Plan not found' });
    }
    
    res.json({ plan });
  } catch (error) {
    console.error('Error getting plan:', error);
    res.status(500).json({ error: 'Failed to get plan' });
  }
});

// Delete a plan
app.delete('/api/plans/:planId', async (req, res) => {
  try {
    const { planId } = req.params;
    await db.deletePlan(planId);
    res.json({ success: true });
  } catch (error) {
    console.error('Error deleting plan:', error);
    res.status(500).json({
      error: error.message || 'Failed to delete plan'
    });
  }
});

// Get all execution sequences from stored plans
app.get('/api/execution-sequences', async (req, res) => {
  try {
    const plans = await db.getAllPlans();
    const executionSequences = plans.map(plan => {
      try {
        return dispatcher.generateExecutionSequence(plan);
      } catch (error) {
        console.error(`Error generating execution sequence for plan ${plan.plan_id}:`, error);
        return null;
      }
    }).filter(seq => seq !== null);
    
    res.json({ executionSequences });
  } catch (error) {
    console.error('Error loading execution sequences:', error);
    res.status(500).json({ error: 'Failed to load execution sequences' });
  }
});

// Get database file modification time for change detection
app.get('/api/db-timestamp', async (req, res) => {
  try {
    const dbFile = path.join(__dirname, 'db', 'plans.json');
    try {
      const stats = await fs.stat(dbFile);
      res.json({ timestamp: stats.mtime.getTime() });
    } catch (error) {
      // File doesn't exist yet
      res.json({ timestamp: 0 });
    }
  } catch (error) {
    console.error('Error getting database timestamp:', error);
    res.status(500).json({ error: 'Failed to get database timestamp' });
  }
});

// Load mock plan from mock_plan.json and save to plans database
app.post('/api/load-mock-plan', async (req, res) => {
  try {
    const mockPlanFile = path.join(__dirname, 'db', 'mock_plan.json');
    
    // Read mock_plan.json
    let mockPlan;
    try {
      const data = await fs.readFile(mockPlanFile, 'utf8');
      mockPlan = JSON.parse(data);
    } catch (error) {
      if (error.code === 'ENOENT') {
        return res.status(404).json({ error: 'mock_plan.json file not found' });
      }
      if (error instanceof SyntaxError) {
        return res.status(400).json({ error: 'Invalid JSON in mock_plan.json' });
      }
      throw error;
    }
    
    // Validate plan structure
    if (!mockPlan || !mockPlan.plan_id) {
      return res.status(400).json({ error: 'Invalid mock plan: missing plan_id' });
    }
    
    // Save to plans database using db module
    const result = await db.savePlan(mockPlan);
    res.json(result);
  } catch (error) {
    console.error('Error loading mock plan:', error);
    res.status(500).json({ error: error.message || 'Failed to load mock plan' });
  }
});

// Get timetable layout for a plan and cache it in executor runner
app.post('/api/timetable-layout', async (req, res) => {
  try {
    const { planId } = req.body;
    
    if (!planId) {
      return res.status(400).json({ error: 'planId is required' });
    }
    
    // Get plan from database
    const plan = await db.getPlanById(planId);
    
    if (!plan) {
      return res.status(404).json({ error: 'Plan not found' });
    }
    
    // Generate execution stages using dispatcher
    const executionStages = dispatcher.generateExecutionSequence(plan);
    
    // Build timetable layout using dispatcher
    const layout = dispatcher.buildTimetableLayout(executionStages);
    
    // Cache the layout and build chain cache in executor runner
    executorRunner.setTimetableLayoutCache(layout);
    
    res.json({ layout });
  } catch (error) {
    console.error('Error generating timetable layout:', error);
    res.status(500).json({ error: error.message || 'Failed to generate timetable layout' });
  }
});

// Get executor states
app.get('/api/executors', (req, res) => {
  try {
    // Get stats first (this validates and fixes any inconsistencies)
    const stats = executorManager.getExecutorStats();
    // Then get executors (after stats validation)
    const executors = executorManager.getAllExecutors();
    
    // Final validation: ensure stats match executor array
    const actualBusy = executors.filter(e => e.status === 'busy').length;
    const actualIdle = executors.filter(e => e.status === 'idle').length;
    
    if (stats.busy !== actualBusy || stats.idle !== actualIdle) {
      console.warn(`Stats mismatch in API response: stats say busy=${stats.busy}, idle=${stats.idle}, but executors show busy=${actualBusy}, idle=${actualIdle}`);
      // Use actual values from executor array
      stats.busy = actualBusy;
      stats.idle = actualIdle;
    }
    
    res.json({ executors, stats });
  } catch (error) {
    console.error('Error getting executors:', error);
    res.status(500).json({ error: 'Failed to get executor states' });
  }
});

// Assign executor to task
app.post('/api/executors/assign', (req, res) => {
  try {
    const { taskId } = req.body;
    
    if (!taskId) {
      return res.status(400).json({ error: 'taskId is required' });
    }
    
    const executorId = executorManager.assignTask(taskId);
    
    if (executorId === null) {
      return res.status(503).json({ error: 'No idle executor available' });
    }
    
    res.json({ executorId, taskId });
  } catch (error) {
    console.error('Error assigning executor:', error);
    res.status(500).json({ error: 'Failed to assign executor' });
  }
});

// Release executor from task
app.post('/api/executors/release', (req, res) => {
  try {
    const { taskId } = req.body;
    
    if (!taskId) {
      return res.status(400).json({ error: 'taskId is required' });
    }
    
    const executorId = executorManager.releaseExecutorByTaskId(taskId);
    
    // Always return success - even if executorId is null (task might already be released)
    // This prevents errors from duplicate release attempts
    res.json({ 
      success: true, 
      executorId: executorId !== null ? executorId : undefined,
      taskId,
      message: executorId !== null ? 'Executor released successfully' : 'No executor was assigned to this task'
    });
  } catch (error) {
    console.error('Error releasing executor:', error);
    res.status(500).json({ error: 'Failed to release executor: ' + error.message });
  }
});

// Reset all executors to idle state
app.post('/api/executors/reset', (req, res) => {
  try {
    executorManager.initializeExecutors();
    const executors = executorManager.getAllExecutors();
    const stats = executorManager.getExecutorStats();
    res.json({ success: true, executors, stats });
  } catch (error) {
    console.error('Error resetting executors:', error);
    res.status(500).json({ error: 'Failed to reset executors' });
  }
});

// Get verifier states
app.get('/api/verifiers', (req, res) => {
  try {
    // Get stats first (this validates and fixes any inconsistencies)
    const stats = verifierManager.getVerifierStats();
    // Then get verifiers (after stats validation)
    const verifiers = verifierManager.getAllVerifiers();
    
    // Final validation: ensure stats match verifier array
    const actualBusy = verifiers.filter(v => v.status === 'busy').length;
    const actualIdle = verifiers.filter(v => v.status === 'idle').length;
    
    if (stats.busy !== actualBusy || stats.idle !== actualIdle) {
      console.warn(`Stats mismatch in API response: stats say busy=${stats.busy}, idle=${stats.idle}, but verifiers show busy=${actualBusy}, idle=${actualIdle}`);
      // Use actual values from verifier array
      stats.busy = actualBusy;
      stats.idle = actualIdle;
    }
    
    res.json({ verifiers, stats });
  } catch (error) {
    console.error('Error getting verifiers:', error);
    res.status(500).json({ error: 'Failed to get verifier states' });
  }
});

// Assign verifier to task
app.post('/api/verifiers/assign', (req, res) => {
  try {
    const { taskId } = req.body;
    
    if (!taskId) {
      return res.status(400).json({ error: 'taskId is required' });
    }
    
    const verifierId = verifierManager.assignTask(taskId);
    
    if (verifierId === null) {
      return res.status(503).json({ error: 'No idle verifier available' });
    }
    
    res.json({ verifierId, taskId });
  } catch (error) {
    console.error('Error assigning verifier:', error);
    res.status(500).json({ error: 'Failed to assign verifier' });
  }
});

// Release verifier from task
app.post('/api/verifiers/release', (req, res) => {
  try {
    const { taskId } = req.body;
    
    if (!taskId) {
      return res.status(400).json({ error: 'taskId is required' });
    }
    
    const verifierId = verifierManager.releaseVerifierByTaskId(taskId);
    
    // Always return success - even if verifierId is null (task might already be released)
    res.json({ 
      success: true, 
      verifierId: verifierId !== null ? verifierId : undefined,
      taskId,
      message: verifierId !== null ? 'Verifier released successfully' : 'No verifier was assigned to this task'
    });
  } catch (error) {
    console.error('Error releasing verifier:', error);
    res.status(500).json({ error: 'Failed to release verifier: ' + error.message });
  }
});

// Reset all verifiers to idle state
app.post('/api/verifiers/reset', (req, res) => {
  try {
    verifierManager.initializeVerifiers();
    const verifiers = verifierManager.getAllVerifiers();
    const stats = verifierManager.getVerifierStats();
    res.json({ success: true, verifiers, stats });
  } catch (error) {
    console.error('Error resetting verifiers:', error);
    res.status(500).json({ error: 'Failed to reset verifiers' });
  }
});

// Start mock execution endpoint - only uses cache, not database
app.post('/api/mock-execution', async (req, res) => {
  try {
    // Start execution in background using cache only
    executorRunner.startMockExecution().catch(error => {
      console.error('Error in background execution:', error);
      // Broadcast error to clients
      executorRunner.io.emit('execution-error', { error: error.message });
    });

    res.json({ success: true, message: 'Mock execution started' });
  } catch (error) {
    console.error('Error starting mock execution:', error);
    res.status(500).json({ error: error.message || 'Failed to start mock execution' });
  }
});

// Stop mock execution endpoint
app.post('/api/mock-execution/stop', (req, res) => {
  try {
    executorRunner.stop();
    res.json({ success: true, message: 'Mock execution stopped' });
  } catch (error) {
    console.error('Error stopping mock execution:', error);
    res.status(500).json({ error: error.message || 'Failed to stop mock execution' });
  }
});

// Static file serving - MUST come after all API routes
app.use(express.static(path.join(__dirname, '../frontend')));

// WebSocket connection handling
io.on('connection', (socket) => {
  console.log('Client connected:', socket.id);

  // Send initial executor states
  const executors = executorManager.getAllExecutors();
  const executorStats = executorManager.getExecutorStats();
  socket.emit('executor-states-update', { executors, stats: executorStats });

  // Send initial verifier states
  const verifiers = verifierManager.getAllVerifiers();
  const verifierStats = verifierManager.getVerifierStats();
  socket.emit('verifier-states-update', { verifiers, stats: verifierStats });

  socket.on('disconnect', () => {
    console.log('Client disconnected:', socket.id);
  });
});

server.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
  console.log(`WebSocket server is ready`);
});

server.on('error', (err) => {
  if (err.code === 'EADDRINUSE') {
    console.error(`Port ${PORT} is already in use. Please stop the other process or use a different port.`);
    process.exit(1);
  } else {
    console.error('Server error:', err);
    throw err;
  }
});
