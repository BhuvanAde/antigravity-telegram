"""
Project management utilities for persistent project registry.
"""

import json
import os
import fnmatch
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict, field


@dataclass
class Project:
    """Represents a registered project."""
    path: str
    name: str
    last_used: str
    settings: Dict[str, Any] = field(default_factory=dict)
    

# Persistent storage path
PROJECTS_FILE = Path.home() / ".gemini" / "telegram_projects.json"


def _load_projects() -> Dict[str, Project]:
    """Load projects from persistent storage."""
    if not PROJECTS_FILE.exists():
        return {}
    
    try:
        with open(PROJECTS_FILE, 'r') as f:
            data = json.load(f)
            return {
                path: Project(
                    path=path,
                    name=p.get("name", Path(path).name),
                    last_used=p.get("last_used", ""),
                    settings=p.get("settings", {})
                )
                for path, p in data.items()
            }
    except Exception:
        return {}


def _save_projects(projects: Dict[str, Project]) -> None:
    """Save projects to persistent storage."""
    PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    data = {
        path: {
            "name": p.name,
            "last_used": p.last_used,
            "settings": p.settings
        }
        for path, p in projects.items()
    }
    
    with open(PROJECTS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


class ProjectManager:
    """Manages project registry and context."""
    
    _instance: Optional['ProjectManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._projects = _load_projects()
            cls._instance._current_path: Optional[str] = None
        return cls._instance
    
    def register_project(self, path: str, name: Optional[str] = None) -> Project:
        """Register or update a project."""
        path = str(Path(path).expanduser().resolve())
        
        if path in self._projects:
            project = self._projects[path]
            project.last_used = datetime.now().isoformat()
        else:
            project = Project(
                path=path,
                name=name or Path(path).name,
                last_used=datetime.now().isoformat()
            )
            self._projects[path] = project
        
        _save_projects(self._projects)
        return project
    
    def set_current_project(self, path: str) -> Project:
        """Set the current active project."""
        path = str(Path(path).expanduser().resolve())
        project = self.register_project(path)
        self._current_path = path
        return project
    
    def get_current_project(self) -> Optional[Project]:
        """Get the current active project."""
        if not self._current_path:
            return None
        return self._projects.get(self._current_path)
    
    def get_current_path(self) -> Optional[str]:
        """Get the current project path."""
        return self._current_path
    
    def list_projects(self) -> List[Project]:
        """List all registered projects, sorted by last used."""
        projects = list(self._projects.values())
        projects.sort(key=lambda p: p.last_used, reverse=True)
        return projects
    
    def remove_project(self, path: str) -> bool:
        """Remove a project from the registry."""
        path = str(Path(path).expanduser().resolve())
        if path in self._projects:
            del self._projects[path]
            _save_projects(self._projects)
            if self._current_path == path:
                self._current_path = None
            return True
        return False


def get_project_manager() -> ProjectManager:
    """Get the singleton ProjectManager instance."""
    return ProjectManager()


# ===== IDE Capability Functions =====

def read_project_file(file_path: str, project_path: Optional[str] = None) -> str:
    """
    Read a file from the project.
    
    Args:
        file_path: Relative or absolute path to the file
        project_path: Optional project root (uses current if not specified)
        
    Returns:
        File contents as string
    """
    pm = get_project_manager()
    base = project_path or pm.get_current_path()
    
    if not base:
        raise ValueError("No project context set")
    
    full_path = Path(base) / file_path if not Path(file_path).is_absolute() else Path(file_path)
    
    if not full_path.exists():
        raise FileNotFoundError(f"File not found: {full_path}")
    
    return full_path.read_text()


def write_project_file(file_path: str, content: str, project_path: Optional[str] = None) -> str:
    """
    Write content to a file in the project.
    
    Args:
        file_path: Relative or absolute path to the file
        content: Content to write
        project_path: Optional project root
        
    Returns:
        Confirmation message
    """
    pm = get_project_manager()
    base = project_path or pm.get_current_path()
    
    if not base:
        raise ValueError("No project context set")
    
    full_path = Path(base) / file_path if not Path(file_path).is_absolute() else Path(file_path)
    
    # Create parent directories if needed
    full_path.parent.mkdir(parents=True, exist_ok=True)
    
    full_path.write_text(content)
    return f"Successfully wrote {len(content)} bytes to {full_path}"


def list_project_files(
    directory: str = ".",
    pattern: str = "*",
    recursive: bool = False,
    project_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List files in a project directory.
    
    Args:
        directory: Directory to list (relative to project root)
        pattern: Glob pattern to filter files
        recursive: Whether to search recursively
        project_path: Optional project root
        
    Returns:
        List of file info dicts
    """
    pm = get_project_manager()
    base = project_path or pm.get_current_path()
    
    if not base:
        raise ValueError("No project context set")
    
    search_dir = Path(base) / directory if directory != "." else Path(base)
    
    if not search_dir.exists():
        raise FileNotFoundError(f"Directory not found: {search_dir}")
    
    files = []
    glob_method = search_dir.rglob if recursive else search_dir.glob
    
    for item in glob_method(pattern):
        # Skip hidden files and common ignore patterns
        if any(part.startswith('.') for part in item.parts[-1:]):
            continue
        if 'node_modules' in item.parts or '__pycache__' in item.parts:
            continue
            
        files.append({
            "path": str(item.relative_to(base)),
            "name": item.name,
            "is_dir": item.is_dir(),
            "size": item.stat().st_size if item.is_file() else None,
        })
    
    return files[:100]  # Limit to 100 files


def search_project_code(
    query: str,
    file_types: Optional[List[str]] = None,
    project_path: Optional[str] = None,
    max_results: int = 20
) -> List[Dict[str, Any]]:
    """
    Search for code patterns in the project using grep.
    
    Args:
        query: Search string or pattern
        file_types: Optional list of file extensions to search (e.g., ['.py', '.js'])
        project_path: Optional project root
        max_results: Maximum number of results to return
        
    Returns:
        List of match dicts with file, line, and content
    """
    pm = get_project_manager()
    base = project_path or pm.get_current_path()
    
    if not base:
        raise ValueError("No project context set")
    
    # Build grep command
    cmd = ["grep", "-rn", "--include=*"]
    
    if file_types:
        cmd = ["grep", "-rn"]
        for ext in file_types:
            ext = ext if ext.startswith('.') else f'.{ext}'
            cmd.extend(["--include", f"*{ext}"])
    
    cmd.extend([
        "--exclude-dir=node_modules",
        "--exclude-dir=.git",
        "--exclude-dir=__pycache__",
        "--exclude-dir=.next",
        "--exclude-dir=dist",
        "--exclude-dir=build",
        query,
        str(base)
    ])
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        matches = []
        for line in result.stdout.strip().split('\n')[:max_results]:
            if not line:
                continue
            
            parts = line.split(':', 2)
            if len(parts) >= 3:
                file_path = parts[0]
                try:
                    rel_path = str(Path(file_path).relative_to(base))
                except ValueError:
                    rel_path = file_path
                    
                matches.append({
                    "file": rel_path,
                    "line": int(parts[1]),
                    "content": parts[2].strip()[:200]
                })
        
        return matches
        
    except subprocess.TimeoutExpired:
        return [{"error": "Search timed out"}]
    except Exception as e:
        return [{"error": str(e)}]


def run_terminal_command(
    command: str,
    project_path: Optional[str] = None,
    timeout: int = 30
) -> Dict[str, Any]:
    """
    Run a terminal command in the project directory.
    
    Args:
        command: Command to run
        project_path: Optional project root (used as cwd)
        timeout: Command timeout in seconds
        
    Returns:
        Dict with stdout, stderr, and return_code
    """
    pm = get_project_manager()
    cwd = project_path or pm.get_current_path() or str(Path.home())
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        return {
            "stdout": result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout,
            "stderr": result.stderr[-500:] if len(result.stderr) > 500 else result.stderr,
            "return_code": result.returncode,
            "success": result.returncode == 0
        }
        
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
            "return_code": -1,
            "success": False
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": str(e),
            "return_code": -1,
            "success": False
        }


def get_project_context(project_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Get context information about the current project.
    
    Args:
        project_path: Optional project path
        
    Returns:
        Dict with project info, file counts, git status, etc.
    """
    pm = get_project_manager()
    path = project_path or pm.get_current_path()
    
    if not path:
        return {"error": "No project context set"}
    
    project = pm.get_current_project()
    base = Path(path)
    
    # Count files by type
    file_counts: Dict[str, int] = {}
    for item in base.rglob('*'):
        if item.is_file() and not any(p.startswith('.') for p in item.parts):
            ext = item.suffix.lower() or 'no_extension'
            file_counts[ext] = file_counts.get(ext, 0) + 1
    
    # Get git info if available
    git_info = None
    git_dir = base / ".git"
    if git_dir.exists():
        try:
            branch_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(base),
                capture_output=True,
                text=True
            )
            status_result = subprocess.run(
                ["git", "status", "--short"],
                cwd=str(base),
                capture_output=True,
                text=True
            )
            git_info = {
                "branch": branch_result.stdout.strip(),
                "changes": len(status_result.stdout.strip().split('\n')) if status_result.stdout.strip() else 0
            }
        except Exception:
            pass
    
    return {
        "path": path,
        "name": project.name if project else base.name,
        "file_counts": dict(sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
        "git": git_info,
        "settings": project.settings if project else {}
    }
