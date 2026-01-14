# 🚀 Antigravity Mobile Command

**Transform your mobile device into a remote Mission Control for your coding environment.**

Antigravity Mobile Command is an "Agentic Bridge" that leverages Google Antigravity's native Model Context Protocol (MCP) and Artifact system to provide a bi-directional, real-time feedback loop via Telegram.

![Telegram Bot Preview](docs/preview.png)

## ✨ Features

- **📱 Prompt-to-Action Loop**: Send coding tasks from your phone, approve plans with inline buttons
- **📸 Visual Verification**: Auto-receive screenshots and recordings of UI changes
- **✅ Interactive Governance**: Approve or reject code diffs via Telegram buttons
- **🚨 Error Awareness**: Get notified of terminal crashes with full stack traces
- **📊 Live Status Ticker**: Real-time progress updates without message spam

## 🛠️ Quick Start

### Prerequisites

- Python 3.10+
- A Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Your Telegram Chat ID (from [@userinfobot](https://t.me/userinfobot))

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/antigravity-telegram.git
cd antigravity-telegram

# Install dependencies
pip install -e .

# Or with uv
uv pip install -e .
```

### Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` with your credentials:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
AUTHORIZED_CHAT_IDS=your_chat_id
ARTIFACTS_PATH=~/.gemini/antigravity/artifacts
```

### Running

**Run both Telegram bot and MCP server:**
```bash
python -m src.main
```

**Run only the Telegram bot:**
```bash
python -m src.main --mode bot
```

**Run only the MCP server (for Antigravity integration):**
```bash
python -m src.main --mode mcp
```

## 🔌 Antigravity MCP Integration

### 1. Add to MCP Config

Add the Telegram bridge to your Antigravity MCP configuration (`~/.gemini/mcp_config.json`):

```json
{
  "mcpServers": {
    "telegram-bridge": {
      "command": "python",
      "args": ["-m", "src.main", "--mode", "mcp"],
      "cwd": "/path/to/antigravity-telegram",
      "env": {
        "TELEGRAM_BOT_TOKEN": "your_token",
        "AUTHORIZED_CHAT_IDS": "your_chat_id",
        "ARTIFACTS_PATH": "~/.gemini/antigravity/artifacts"
      }
    }
  }
}
```

### 2. Copy the Workflow

Copy the workflow file to your Antigravity workflows:
```bash
cp workflows/mobile-command.md ~/.agent/workflows/
```

### 3. Use from Telegram

1. Start a chat with your bot on Telegram
2. Send `/start` to verify the connection
3. Send `/prompt "Your coding task here"`
4. Approve plans and review changes from your phone!

## 📱 Telegram Commands

| Command | Description |
|---------|-------------|
| `/start` | Show welcome message and verify connection |
| `/prompt <text>` | Send a coding task to Antigravity |
| `/status` | Check current execution status |
| `/cancel` | Cancel the current operation |
| `/help` | Show help message |

## 🔧 MCP Tools Available

The following tools are exposed to Antigravity for communication:

| Tool | Description |
|------|-------------|
| `send_telegram_message` | Send messages to the user |
| `request_plan_approval` | Request approval for implementation plans |
| `request_change_approval` | Request approval for code changes |
| `send_artifact` | Send screenshots/recordings to Telegram |
| `update_status` | Update the status ticker message |
| `notify_error` | Send critical error notifications |
| `await_user_response` | Wait for user input |

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  📱 Telegram    │◄───►│  🌉 Python       │◄───►│  🌌 Antigravity │
│     App         │     │     Bridge       │     │     Agent       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │  📁 Artifact     │
                        │     Watcher      │
                        └──────────────────┘
```

## 📁 Project Structure

```
antigravity-telegram/
├── src/
│   ├── main.py              # Entry point
│   ├── config.py            # Configuration management
│   ├── bot/
│   │   ├── handlers.py      # Telegram command handlers
│   │   ├── keyboards.py     # Inline keyboard builders
│   │   └── message_queue.py # Async message queue
│   ├── mcp_server/
│   │   ├── server.py        # MCP server implementation
│   │   ├── tools.py         # MCP tool definitions
│   │   └── state.py         # Approval state management
│   ├── monitors/
│   │   ├── artifacts.py     # Artifact directory watcher
│   │   └── terminal.py      # Terminal output monitor
│   └── utils/
│       └── formatting.py    # Message formatting
├── config/
│   └── mcp_config.json      # MCP config template
├── workflows/
│   └── mobile-command.md    # Antigravity workflow
├── .env.example
├── pyproject.toml
└── README.md
```

## 🔒 Security

- Only authorized chat IDs can interact with the bot
- Bot tokens are stored in environment variables
- Session files are gitignored

## 📝 License

MIT License - see [LICENSE](LICENSE) for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

Built with ❤️ for the Antigravity community
