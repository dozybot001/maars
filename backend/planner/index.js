const axios = require('axios');
const fs = require('fs').promises;
const path = require('path');

const SYSTEM_PROMPT_FILE = path.join(__dirname, 'system-prompt.txt');

// Load system prompt
async function loadSystemPrompt() {
  const data = await fs.readFile(SYSTEM_PROMPT_FILE, 'utf8');
  return data.trim();
}

// Generate plan using AI
async function generatePlan(task, config) {
  if (!config.apiUrl || !config.apiKey) {
    throw new Error('API configuration is missing. Please configure API settings first.');
  }

  // Normalize API URL - append /chat/completions if not present
  let apiUrl = config.apiUrl.trim();
  if (!apiUrl.endsWith('/chat/completions')) {
    apiUrl = apiUrl.replace(/\/$/, '') + '/chat/completions';
  }

  // Trim API key to remove any whitespace
  const apiKey = config.apiKey.trim();
  
  console.log('Making API request to:', apiUrl);
  console.log('Using model:', config.model);
  
  const systemPrompt = await loadSystemPrompt();

  // Call the custom API using axios
  try {
    const response = await axios.post(apiUrl, {
      model: config.model,
      messages: [
        {
          role: 'system',
          content: systemPrompt
        },
        {
          role: 'user',
          content: task
        }
      ],
      temperature: config.temperature
    }, {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      }
      // No timeout property - wait indefinitely for response
    });

    return response.data;
  } catch (error) {
    // Provide more detailed error information
    if (error.code === 'ECONNREFUSED') {
      throw new Error(`Connection refused. Please check if the API URL is correct: ${apiUrl}`);
    } else if (error.code === 'ENOTFOUND') {
      throw new Error(`DNS lookup failed. Please check if the API URL is correct: ${apiUrl}`);
    } else if (error.code === 'ETIMEDOUT' || error.message.includes('timeout')) {
      throw new Error(`Request timeout. The API did not respond. This may happen with complex tasks. Please try again or simplify your query. URL: ${apiUrl}`);
    } else if (error.request && !error.response) {
      throw new Error(`No response from API. URL: ${apiUrl}. Please check your API URL and network connection.`);
    }
    // Re-throw other errors
    throw error;
  }
}

module.exports = {
  generatePlan
};
