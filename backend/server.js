const express = require('express');
const cors = require('cors');
const path = require('path');
const http = require('http');
const { Server } = require('socket.io');
const planner = require('./planner');
const monitor = require('./monitor');
const taskCache = require('./tasks/taskCache');
const db = require('./db');
const { executor: executorManager, verifier: verifierManager } = require('./workers');
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

// AbortController for current plan run (stop button)
let planRunAbortController = null;

// Create executor runner instance
const executorRunner = new ExecutorRunner(io);

app.use(cors());
app.use(express.json());

// ========== API ROUTES (must come before static file serving) ==========

// Stop current plan run
app.post('/api/plan/stop', (req, res) => {
  if (planRunAbortController) {
    planRunAbortController.abort();
  }
  res.json({ success: true });
});

// Run plan: verify → decompose → format. If idea provided, create task 0 first.
app.post('/api/plan/run', async (req, res) => {
  planRunAbortController = new AbortController();
  const signal = planRunAbortController.signal;

  try {
    const { idea } = req.body;
    const planId = req.query.planId || req.body.planId || 'test';

    let plan = await db.getPlan(planId);
    if (idea != null && typeof idea === 'string') {
      const task0 = { task_id: '0', description: idea.trim(), dependencies: [] };
      await db.savePlan({ tasks: [task0] }, planId);
      plan = await db.getPlan(planId);
    }
    if (!plan || !plan.tasks || plan.tasks.length === 0) {
      return res.status(400).json({ error: 'No plan found. Provide idea or generate plan first.' });
    }

    io.emit('plan-start');
    taskCache.clearPlanCache(planId);
    (plan.tasks || []).forEach(t => taskCache.appendPlanCache(planId, t));

    // Emit task 0 (idea) first so it renders before decompose starts
    const task0 = plan.tasks.find(t => t.task_id === '0');
    if (task0) {
      const staged = taskCache.computeStaged(taskCache.getPlanCache(planId));
      const task0WithStage = taskCache.enrichTreeData(staged, plan.tasks).find(t => t.task_id === '0');
      if (task0WithStage) io.emit('plan-task', { task: task0WithStage });
    }

    const onTask = (task) => {
      taskCache.appendPlanCache(planId, task);
      const staged = taskCache.computeStaged(taskCache.getPlanCache(planId));
      const taskWithStage = taskCache.enrichTreeData(staged, [task]).find(t => t.task_id === task.task_id)
        || { ...task, stage: 1 };
      io.emit('plan-task', { task: taskWithStage });
    };
    const onThinking = (chunk) => io.emit('plan-thinking', { chunk });

    const { tasks: mergedTasks } = await planner.runPlan(plan, onTask, onThinking, { signal });

    await db.savePlan({ tasks: mergedTasks }, planId);
    const treeData = taskCache.buildTreeData(mergedTasks);
    io.emit('plan-complete', { treeData });

    res.json({ success: true });
  } catch (error) {
    const isAborted = error.name === 'AbortError' || signal?.aborted;
    planRunAbortController = null;
    console.error('Plan run error:', error.message);
    io.emit('plan-error', { error: isAborted ? 'Plan generation stopped by user' : error.message });
    if (isAborted) {
      return res.status(499).json({ error: 'Plan generation stopped by user' });
    }
    if (error.message?.includes('No decomposable task') || error.message?.includes('Provide idea')) {
      return res.status(400).json({ error: error.message });
    }
    res.status(500).json({ error: error.message || 'Failed to run plan' });
  } finally {
    planRunAbortController = null;
  }
});

// Monitor - generate timetable from execution
app.post('/api/monitor/timetable', async (req, res) => {
  try {
    const { execution } = req.body;
    
    if (!execution) {
      return res.status(400).json({
        error: 'Execution is required'
      });
    }

    const layout = monitor.buildLayoutFromExecution(execution);
    executorRunner.setTimetableLayoutCache(layout);
    
    res.json({ layout });
  } catch (error) {
    console.error('Monitor timetable error:', error);
    return res.status(500).json({
      error: error.message || 'Failed to generate timetable layout'
    });
  }
});

// ========== Agent JSONs (planId defaults to "test") ==========

// Plan (db only, no stage)
app.get('/api/plan', async (req, res) => {
  try {
    const planId = req.query.planId || 'test';
    const plan = await db.getPlan(planId);
    res.json({ plan: plan || null });
  } catch (error) {
    console.error('Error loading plan:', error);
    res.status(500).json({ error: error.message || 'Failed to load plan' });
  }
});

// Plan tree data for rendering (cache processed, with stage)
app.get('/api/plan/tree', async (req, res) => {
  try {
    const planId = req.query.planId || 'test';
    const plan = await db.getPlan(planId);
    if (!plan || !plan.tasks || plan.tasks.length === 0) {
      return res.json({ treeData: [] });
    }
    const treeData = taskCache.buildTreeData(plan.tasks);
    res.json({ treeData });
  } catch (error) {
    console.error('Error loading plan tree:', error);
    res.status(500).json({ error: error.message || 'Failed to load plan tree' });
  }
});

// Idea
app.get('/api/idea', async (req, res) => {
  try {
    const planId = req.query.planId || 'test';
    const idea = await db.getIdea(planId);
    res.json({ idea });
  } catch (error) {
    console.error('Error loading idea:', error);
    res.status(500).json({ error: 'Failed to load idea' });
  }
});

// Execution endpoints
app.get('/api/execution', async (req, res) => {
  try {
    const planId = req.query.planId || 'test';
    const execution = await db.getExecution(planId);
    res.json({ execution });
  } catch (error) {
    console.error('Error loading execution:', error);
    res.status(500).json({ error: 'Failed to load execution' });
  }
});

app.post('/api/execution', async (req, res) => {
  try {
    const planId = req.body.planId || req.query.planId || 'test';
    const execution = req.body;
    // Remove planId from execution if it was included
    delete execution.planId;
    const result = await db.saveExecution(execution, planId);
    res.json(result);
  } catch (error) {
    console.error('Error saving execution:', error);
    res.status(500).json({ error: error.message || 'Failed to save execution' });
  }
});

// Verification endpoints
app.get('/api/verification', async (req, res) => {
  try {
    const planId = req.query.planId || 'test';
    const verification = await db.getVerification(planId);
    res.json({ verification });
  } catch (error) {
    console.error('Error loading verification:', error);
    res.status(500).json({ error: 'Failed to load verification' });
  }
});

app.post('/api/verification', async (req, res) => {
  try {
    const planId = req.body.planId || req.query.planId || 'test';
    const verification = req.body;
    // Remove planId from verification if it was included
    delete verification.planId;
    const result = await db.saveVerification(verification, planId);
    res.json(result);
  } catch (error) {
    console.error('Error saving verification:', error);
    res.status(500).json({ error: error.message || 'Failed to save verification' });
  }
});

// Executors
app.get('/api/executors', (req, res) => {
  try {
    const stats = executorManager.getExecutorStats();
    const executors = executorManager.getAllExecutors();
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

// Verifiers
app.get('/api/verifiers', (req, res) => {
  try {
    const stats = verifierManager.getVerifierStats();
    const verifiers = verifierManager.getAllVerifiers();
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
