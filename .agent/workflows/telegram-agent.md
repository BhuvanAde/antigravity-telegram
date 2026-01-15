---
description: Check Telegram for pending prompts and execute them automatically
---

# Telegram Agent Workflow

This workflow enables automatic execution of prompts sent from Telegram.

## How to Use

// turbo
1. **Start Infinite Automation Loop**
   - Notify the user: "Starting 24/7 Telegram Auto-Executor. I will run in the background."

   **Continuous Loop Logic:**
   Run the following steps locally in an infinite loop:

   a. **Wait for Task**
      - Call `wait_for_new_prompt(timeout_seconds=3600)` # Wait for 1 hour (Event-driven)
      - If result is "No new prompts", loop back to (a).

   b. **Process Task**
      - If "New prompts detected", call `get_pending_prompts()`
      - For each prompt found:
        - **Acknowledge**: Immediately call `send_telegram_message` with "Received: [Prompt]. Working on it... 👨‍💻"
        - **Log**: "Executing task: [Prompt text]"
        - **Execute**: Perform the requested task actions.
          - *Tip*: Send occasional `update_status` or `send_telegram_message` if the task is long (e.g., "Reading files...", "Found bug...").
        - **Report Results**: CRITICAL! Send the final output/confirmation back via `send_telegram_message`.
          - Example: "✅ Done! Modified 2 files. [Description of changes]"
        - **Safety**: Do NOT call `notify_user` (blocking). Use `send_telegram_message` for all communication.
      - Loop back to (a).

## Available MCP Tools

### Communication
- `send_telegram_message` - Send status updates
- `request_plan_approval` - Request approval before major changes
- `request_change_approval` - Request approval for code changes
- `notify_error` - Report errors
- `update_status` - Update progress ticker

### IDE Capabilities
- `read_project_file` - Read file contents
- `write_project_file` - Write files (notifies Telegram)
- `list_project_files` - List directory contents
- `search_project_code` - Search codebase
- `run_terminal_command` - Execute commands
- `get_project_context` - Get current project info
- `set_project_context` - Set working project
- `send_code_update` - Notify about code changes

### Artifacts
- `send_artifact` - Send screenshots/recordings

## Best Practices

1. **Always check for prompts first** - Call `get_pending_prompts` at session start
2. **Request approval** - Use `request_plan_approval` before modifying >3 files
3. **Send updates** - Use `update_status` for progress
4. **Share visuals** - Use `send_artifact` for UI screenshots
5. **Report errors** - Use `notify_error` if something fails
