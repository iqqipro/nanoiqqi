"""
Compaction Safeguard: High-performance session context management.
"""
from collections import deque
from typing import List, Dict, Any, Protocol

# Protocol for strict typing of the Provider (Async Interface for nanoiqqi)
class AsyncLLMProvider(Protocol):
    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> Any:
        ...

class CompactionSafeguard:
    """
    Manages the lifecycle of the message window using a Compaction Safeguard algorithm.
    
    Architecture:
    - Buffer: O(1) Circular Buffer (deque)
    - Strategy: Semantic Compression + Sliding Window
    """
    
    # Constants for the Safeguard
    TRIGGER_COUNT = 20
    TRIGGER_TOKENS = 50_000
    
    # After activation, re-compact every N new messages
    # Base state: [System, Summary] + [5 Recent] = 7 messages
    # Trigger next: 7 + 5 = 12 messages
    STEADY_STATE_INCREMENT = 5 
    
    CONTEXT_PRESERVATION_WINDOW = 5 # Keep last 5 messages intact
    SUMMARY_MAX_TOKENS = 2_000

    def __init__(self, provider: AsyncLLMProvider, summarizer_model: str = "google/gemini-2.5-flash"):
        self.provider = provider
        self.summarizer_model = summarizer_model
        self._safeguard_active = False
        self._last_compaction_size = 0

    def _estimate_tokens(self, text: str) -> int:
        """Heuristic O(1) token estimation (char/4) to avoid tokenizer overhead."""
        if not text: return 0
        return len(text) // 4

    def _calculate_buffer_tokens(self, buffer: deque) -> int:
        """Sum tokens in the buffer."""
        return sum(self._estimate_tokens(msg.get("content", "")) for msg in buffer)

    async def process(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Main Pipeline.
        Input: Standard list of messages.
        Output: Optimized payload for the API.
        """
        # 1. Convert to Deque for O(1) operations
        buffer = deque(messages)
        
        # Fast exit: Empty or just System message
        if len(buffer) <= 1:
            return list(buffer)

        # 2. Logic: Detection
        current_count = len(buffer)
        current_tokens = self._calculate_buffer_tokens(buffer)
        
        should_trigger = False
        
        # Initial Trigger
        if not self._safeguard_active:
            if current_count >= self.TRIGGER_COUNT or current_tokens >= self.TRIGGER_TOKENS:
                should_trigger = True
        # Iterative Update (Steady State)
        else:
            # If active, trigger every 5 new messages added to the compacted base
            if current_count >= (self._last_compaction_size + self.STEADY_STATE_INCREMENT):
                should_trigger = True

        if should_trigger:
            return await self._execute_compaction(buffer)
        
        return list(buffer)

    async def _execute_compaction(self, buffer: deque) -> List[Dict[str, Any]]:
        """
        Executes the 'Resumen por Chunks' and 'Payload Reconstruction'.
        Strictly sequential flow.
        """
        # Structure: [System(0), ...Old...(1 to N-5), ...Recent...(N-5 to N)]
        
        # A. Preserve System Message (Index 0)
        system_msg = buffer.popleft() 
        
        # B. Isolate Context Preservation (Last 5)
        # We rotate the deque to extract the last 5 in O(k) where k=5 -> O(1)
        recent_context = deque()
        for _ in range(min(len(buffer), self.CONTEXT_PRESERVATION_WINDOW)):
            if buffer:
                recent_context.appendleft(buffer.pop())
        
        # C. Chunk to Compress (What remains in buffer)
        # This includes previous summaries if they exist at index 1
        chunk_to_compress = list(buffer)
        
        if not chunk_to_compress:
            # Edge case: nothing to compress
            new_payload = [system_msg] + list(recent_context)
            self._last_compaction_size = len(new_payload)
            return new_payload

        # D. Summarization (Synchronous Blocking Call logic - via await)
        # "Block semantic strict max 2000 tokens"
        try:
            summary_text = await self._summarize_chunk(chunk_to_compress)
        except Exception as e:
            # Fallback in case of failure: return original
            print(f"Safeguard Error: {e}")
            return [system_msg] + chunk_to_compress + list(recent_context)
        
        # E. Reconstruct Payload
        # [System] + [Summary] + [Recent]
        new_payload = deque()
        new_payload.append(system_msg)
        
        summary_msg = {
            "role": "system",
            "content": f"### PREVIOUS CONTEXT SUMMARY\n{summary_text}"
        }
        new_payload.append(summary_msg)
        new_payload.extend(recent_context)
        
        # F. Update State
        self._safeguard_active = True
        self._last_compaction_size = len(new_payload)
        
        return list(new_payload)

    async def _summarize_chunk(self, messages: List[Dict[str, Any]]) -> str:
        """
        Generates the semantic block summary using a high-fidelity technical prompt.
        """
        # Convert messages to a string block for the LLM
        transcript = "\n".join([f"{m.get('role', 'unknown').upper()}: {m.get('content', '')}" for m in messages])
        
        system_instruction = (
            "Eres el módulo de Memoria Semántica (LTM) de un asistente técnico avanzado. "
            "Tu tarea es analizar el [Resumen Semántico Anterior] y los [Mensajes Antiguos a Compactar], "
            "para generar un nuevo estado de memoria unificado.\n"
            f"Debes redactar este nuevo resumen en un máximo estricto de {self.SUMMARY_MAX_TOKENS} tokens.\n\n"
            "Reglas de Preservación Crítica (No Negociables):\n"
            "1. Fidelidad Técnica: Nunca omitas, alteres ni resumas excesivamente directivas de código "
            "(ej. pragmas de OpenMP, dependencias de MPI, flags de compilación en C++). Mantén la sintaxis exacta si es el núcleo de la discusión.\n"
            "2. Rigor Matemático: Las ecuaciones matemáticas, planteamientos de cálculo, condiciones de frontera "
            "(ej. difusión de calor) y topologías de redes neuronales (ej. PINNs en MLX) deben conservarse intactas. No las parafrasees.\n"
            "3. Estado del Proyecto: Documenta claramente en qué fase se encuentra el desarrollo actual, "
            "qué errores de compilación o bugs se están depurando, y cualquier referencia a repositorios de GitHub mencionados.\n"
            "4. Decisiones de Diseño: Si se eligió una arquitectura específica (ej. HPC vs. procesamiento estándar, "
            "o una GPU específica para aceleración), registra el por qué de esa decisión.\n\n"
            "Formato de Salida:\n"
            "Devuelve ÚNICAMENTE el texto del nuevo resumen estructurado de forma jerárquica "
            "(usa viñetas para los estados del proyecto y bloques de código para la sintaxis clave). "
            "No incluyas saludos, introducciones ni confirmaciones."
        )

        user_content = (
            f"Genera el nuevo estado de memoria unificado basado en el siguiente transcrito:\n\n"
            f"{transcript}"
        )
        
        # Payload for the summarizer
        summary_request = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_content}
        ]
        
        response = await self.provider.chat(
            messages=summary_request,
            model=self.summarizer_model,
            max_tokens=self.SUMMARY_MAX_TOKENS
        )
        return response.content or "[Summary failed]"
