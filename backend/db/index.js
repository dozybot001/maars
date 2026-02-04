/**
 * Database Module
 * Simple JSON file-based storage for plans
 */

const fs = require('fs').promises;
const path = require('path');

const DB_FILE = path.join(__dirname, 'plans.json');

// Initialize database file if it doesn't exist
async function initDB() {
  try {
    await fs.access(DB_FILE);
  } catch (error) {
    // File doesn't exist, create it with empty array
    await fs.writeFile(DB_FILE, JSON.stringify([], null, 2));
  }
}

// Load all plans from database
async function getAllPlans() {
  try {
    await initDB();
    const data = await fs.readFile(DB_FILE, 'utf8');
    return JSON.parse(data);
  } catch (error) {
    console.error('Error loading plans:', error);
    return [];
  }
}

// Save a plan to database
async function savePlan(plan) {
  try {
    await initDB();
    const plans = await getAllPlans();
    
    // Check if plan with same plan_id already exists
    const existingIndex = plans.findIndex(p => p.plan_id === plan.plan_id);
    
    if (existingIndex >= 0) {
      // Update existing plan
      plans[existingIndex] = plan;
    } else {
      // Add new plan
      plans.push(plan);
    }
    
    await fs.writeFile(DB_FILE, JSON.stringify(plans, null, 2));
    return { success: true, plan };
  } catch (error) {
    console.error('Error saving plan:', error);
    throw new Error('Failed to save plan to database');
  }
}

// Get a plan by plan_id
async function getPlanById(planId) {
  try {
    const plans = await getAllPlans();
    return plans.find(p => p.plan_id === planId) || null;
  } catch (error) {
    console.error('Error getting plan:', error);
    return null;
  }
}

// Delete a plan by plan_id
async function deletePlan(planId) {
  try {
    await initDB();
    const plans = await getAllPlans();
    const filtered = plans.filter(p => p.plan_id !== planId);
    await fs.writeFile(DB_FILE, JSON.stringify(filtered, null, 2));
    return { success: true };
  } catch (error) {
    console.error('Error deleting plan:', error);
    throw new Error('Failed to delete plan from database');
  }
}

// Clear all plans from database
async function clearAllPlans() {
  try {
    await initDB();
    await fs.writeFile(DB_FILE, JSON.stringify([], null, 2));
    return { success: true };
  } catch (error) {
    console.error('Error clearing plans:', error);
    throw new Error('Failed to clear database');
  }
}

module.exports = {
  getAllPlans,
  savePlan,
  getPlanById,
  deletePlan,
  clearAllPlans
};
