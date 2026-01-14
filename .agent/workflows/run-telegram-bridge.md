---
description: Run and test the Antigravity Telegram bridge
---

# Running Antigravity Mobile Command

## Setup
// turbo
1. Install dependencies:
```bash
cd /Users/bhuvan_ade/antigravity-telegram && pip install -e .
```

2. Copy environment file and configure:
```bash
cp .env.example .env
# Edit .env with your TELEGRAM_BOT_TOKEN and AUTHORIZED_CHAT_IDS
```

## Running

// turbo
3. Start the Telegram bot only:
```bash
python -m src.main --mode bot
```

// turbo
4. Start the MCP server only (for Antigravity integration):
```bash
python -m src.main --mode mcp
```

// turbo
5. Start both:
```bash
python -m src.main
```

## Testing

6. In Telegram, message your bot:
   - `/start` - Verify connection
   - `/prompt "Create a hello world file"` - Test prompt injection

7. Verify inline buttons appear for plan approval

## Integrating with Antigravity

8. Add to your `~/.gemini/mcp_config.json`:
```json
{
  "mcpServers": {
    "telegram-bridge": {
      "command": "python",
      "args": ["-m", "src.main", "--mode", "mcp"],
      "cwd": "/Users/bhuvan_ade/antigravity-telegram"
    }
  }
}
```
