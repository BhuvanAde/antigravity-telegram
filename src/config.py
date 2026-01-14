"""
Configuration management for Antigravity Mobile Command.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv


@dataclass
class Config:
    """Application configuration loaded from environment variables."""
    
    # Telegram settings
    bot_token: str
    authorized_chat_ids: list[int] = field(default_factory=list)
    
    # Paths
    artifacts_path: Path = field(default_factory=lambda: Path.home() / ".gemini" / "antigravity" / "artifacts")
    workspace_path: Path = field(default_factory=lambda: Path.home())
    
    # MCP settings
    mcp_server_name: str = "telegram-bridge"
    log_level: str = "INFO"
    
    @classmethod
    def from_env(cls, env_file: Optional[Path] = None) -> "Config":
        """Load configuration from environment variables."""
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()
        
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
        
        # Parse authorized chat IDs
        chat_ids_str = os.getenv("AUTHORIZED_CHAT_IDS", "")
        chat_ids = []
        if chat_ids_str:
            chat_ids = [int(cid.strip()) for cid in chat_ids_str.split(",") if cid.strip()]
        
        # Parse paths
        artifacts_path_str = os.getenv("ARTIFACTS_PATH", "~/.gemini/antigravity/artifacts")
        artifacts_path = Path(artifacts_path_str).expanduser()
        
        workspace_path_str = os.getenv("WORKSPACE_PATH", "~/")
        workspace_path = Path(workspace_path_str).expanduser()
        
        return cls(
            bot_token=bot_token,
            authorized_chat_ids=chat_ids,
            artifacts_path=artifacts_path,
            workspace_path=workspace_path,
            mcp_server_name=os.getenv("MCP_SERVER_NAME", "telegram-bridge"),
            log_level=os.getenv("MCP_LOG_LEVEL", "INFO"),
        )
    
    def ensure_directories(self) -> None:
        """Ensure required directories exist."""
        self.artifacts_path.mkdir(parents=True, exist_ok=True)


# Global config instance (initialized in main)
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config


def set_config(config: Config) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config
