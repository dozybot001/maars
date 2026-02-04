# MAARS: Multi-Agent Automated Research System

## Basic Workflow

- Planner (Agent):
  - Break down the research task into subtasks with dependencies; output a flat task list.

- Dispatcher (Agent):
  - Decide execution order from dependencies and dispatch subtasks to idle executors.
- Executers (Basic Unit):
  - Execute subtasks
- Verifier (Agent):
  - Verify the output of Executer

- Reporter (Agent):
  - Gether the verified output and generate the final report