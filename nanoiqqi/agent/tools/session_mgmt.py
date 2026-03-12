from datetime import datetime
from pathlib import Path
from typing import Any

from nanoiqqi.agent.tools.base import Tool
from nanoiqqi.session.manager import SessionManager
from nanoiqqi.utils.helpers import ensure_dir

class DumpSessionTool(Tool):
    """Tool to dump the current session to a persistent file and reset memory."""
    
    def __init__(self, session_manager: SessionManager, workspace: Path):
        self.session_manager = session_manager
        self.workspace = workspace
        self._channel = None
        self._chat_id = None
        
    def set_context(self, channel: str, chat_id: str) -> None:
        self._channel = channel
        self._chat_id = chat_id
        
    @property
    def name(self) -> str:
        return "new_session"

    @property
    def description(self) -> str:
        return "Usa esta herramienta cuando el usuario pida iniciar una nueva sesión, borrar la memoria o cambiar a un proyecto completamente distinto."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "summary_name": {
                    "type": "string",
                    "description": "Un título corto y descriptivo para el archivo de guardado (sin espacios, ej: 'resumen_proyecto_x')."
                }
            },
            "required": ["summary_name"]
        }

    async def execute(self, summary_name: str, **kwargs: Any) -> str:
        if not self._channel or not self._chat_id:
            return "Error: No active session context found."
            
        key = f"{self._channel}:{self._chat_id}"
        session = self.session_manager.get_or_create(key)
        
        # Prepare content
        lines = [f"# Session Dump: {summary_name}", f"Date: {datetime.now()}", f"Key: {key}", "-" * 40]
        for msg in session.messages:
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")
            lines.append(f"[{role}] {content}")
            
        # Save to file
        ltm_dir = ensure_dir(self.workspace / ".nanoiqqi" / "ltm")
        # Sanitize filename
        safe_name = "".join(c for c in summary_name if c.isalnum() or c in ('_', '-'))
        filename = f"{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        file_path = ltm_dir / filename
        
        try:
            file_path.write_text("\n".join(lines), encoding="utf-8")
            return f"Session successfully dumped to {file_path}.\n[CLEAR_SESSION_STATE_NOW]"
        except Exception as e:
            return f"Error dumping session: {e}"
