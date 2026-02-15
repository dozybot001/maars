/**
 * Database Module
 * File-based storage: each plan has its own folder with separate JSON files
 * Structure: {planId}/idea.json, plan.json, execution.json, verification.json
 */

const fs = require('fs').promises;
const path = require('path');

const DB_DIR = __dirname;
const DEFAULT_PLAN_ID = 'test';

// Get plan directory path
function getPlanDir(planId = DEFAULT_PLAN_ID) {
  return path.join(DB_DIR, planId);
}

// Get file path for a specific JSON file
function getFilePath(planId, filename) {
  return path.join(getPlanDir(planId), filename);
}

// Ensure plan directory exists
async function ensurePlanDir(planId = DEFAULT_PLAN_ID) {
  const planDir = getPlanDir(planId);
  try {
    await fs.access(planDir);
  } catch (error) {
    // Directory doesn't exist, create it
    await fs.mkdir(planDir, { recursive: true });
  }
}

// Read JSON file
async function readJsonFile(planId, filename) {
  try {
    await ensurePlanDir(planId);
    const filePath = getFilePath(planId, filename);
    try {
      const data = await fs.readFile(filePath, 'utf8');
      return JSON.parse(data);
    } catch (error) {
      // File doesn't exist, return null
      return null;
    }
  } catch (error) {
    console.error(`Error reading ${filename}:`, error);
    return null;
  }
}

// Write JSON file
async function writeJsonFile(planId, filename, data) {
  try {
    await ensurePlanDir(planId);
    const filePath = getFilePath(planId, filename);
    await fs.writeFile(filePath, JSON.stringify(data, null, 2), 'utf8');
    return { success: true };
  } catch (error) {
    console.error(`Error writing ${filename}:`, error);
    throw new Error(`Failed to save ${filename}`);
  }
}

// Get idea (example idea string for planner input)
async function getIdea(planId = DEFAULT_PLAN_ID) {
  return await readJsonFile(planId, 'idea.json');
}

// Get execution
async function getExecution(planId = DEFAULT_PLAN_ID) {
  return await readJsonFile(planId, 'execution.json');
}

// Save execution
async function saveExecution(execution, planId = DEFAULT_PLAN_ID) {
  await writeJsonFile(planId, 'execution.json', execution);
  return { success: true, execution };
}

// Get verification
async function getVerification(planId = DEFAULT_PLAN_ID) {
  return await readJsonFile(planId, 'verification.json');
}

// Save verification
async function saveVerification(verification, planId = DEFAULT_PLAN_ID) {
  await writeJsonFile(planId, 'verification.json', verification);
  return { success: true, verification };
}

// Get plan (AI-refined idea with tasks)
async function getPlan(planId = DEFAULT_PLAN_ID) {
  return await readJsonFile(planId, 'plan.json');
}

// Save plan
async function savePlan(plan, planId = DEFAULT_PLAN_ID) {
  await writeJsonFile(planId, 'plan.json', plan);
  return { success: true, plan };
}

module.exports = {
  getIdea,
  getExecution,
  saveExecution,
  getVerification,
  saveVerification,
  getPlan,
  savePlan
};
