# Análisis de inconsistencias lógicas en el código

Documento generado a partir del análisis en profundidad del código de nanoiqqi. Se listan inconsistencias de lógica, diseño y comportamiento que pueden causar bugs o confusión.

---

## 1. **Modo `agent -m` (mensaje único): respuesta perdida si el modelo usa la herramienta `message`**

**Ubicación:** `nanoiqqi/cli/commands.py` (run_once con `-m`), `nanoiqqi/agent/loop.py` (`_process_message` → `process_direct`).

**Qué pasa:**  
En modo `nanoiqqi agent -m "pregunta"` no se arranca ningún consumidor del bus. Si el LLM responde usando la herramienta `message`, esa herramienta llama a `bus.publish_outbound(...)`. Ese mensaje se publica en el bus pero **nadie lo consume**, así que la respuesta del modelo nunca se muestra. Además, `_process_message` devuelve `None` cuando `message_tool._sent_in_turn` es True, y `process_direct` hace `return response.content if response else ""`, por lo que el CLI recibe `""` e imprime una respuesta vacía.

**Inconsistencia:**  
En modo interactivo la respuesta enviada por la herramienta `message` sí se consume y se muestra; en modo `-m` se pierde y el usuario ve cadena vacía.

**Posible corrección:**  
En modo `-m`, o bien no registrar la herramienta `message` (o darle un callback que acumule en una variable y devolver eso al final), o bien hacer que `process_direct` en canal `cli` no dependa solo del valor de retorno de `_process_message` cuando la respuesta fue enviada por la herramienta (p. ej. acumulando lo que se publica en outbound durante esa ejecución y devolviendo eso como “contenido” de la respuesta).

---

## 2. **`MCP2CLIConfig.cache_dir` declarado pero no usado**

**Ubicación:** `nanoiqqi/config/schema.py` (MCP2CLIConfig), `nanoiqqi/agent/tools/mcp2cli_wrapper.py`.

**Qué pasa:**  
En el schema, `MCP2CLIConfig` tiene:

```python
cache_dir: str = Field(default="~/.nanoiqqi/.mcp2cli-cache", description="Optional cache directory for mcp2cli")
```

En `mcp2cli_wrapper.py`, `MCP2CLITool` no recibe ni usa `cache_dir` (solo `workspace_path` y `timeout_seconds`). Si `mcp2cli` espera un directorio de caché vía variable de entorno o flag, la configuración del usuario se ignora.

**Inconsistencia:**  
Configuración expuesta en el schema que no tiene efecto en el comportamiento real.

**Posible corrección:**  
O bien pasar `cache_dir` al wrapper y usarlo (p. ej. `cwd` o env `MCP2CLI_CACHE_DIR`), o bien quitar el campo del schema y documentar que no se usa.

---

## 3. **Marcador `[CLEAR_SESSION_STATE_NOW]` en el resultado de herramientas**

**Ubicación:** `nanoiqqi/agent/loop.py` (dentro de `_run_agent_loop`), `nanoiqqi/agent/tools/session_mgmt.py`.

**Qué pasa:**  
Se hace:

```python
if "[CLEAR_SESSION_STATE_NOW]" in result:
    raise SessionCleared(result.replace("[CLEAR_SESSION_STATE_NOW]", "").strip())
```

Cualquier herramienta que devuelva un string que contenga literalmente `"[CLEAR_SESSION_STATE_NOW]"` (por ejemplo un error o un log) provocaría un clear de sesión. Hoy solo `DumpSessionTool` incluye ese texto de forma intencionada, pero la lógica es frágil.

**Inconsistencia:**  
Un marcador de control que debería ser privado de una herramienta se interpreta de forma global; no hay forma de que solo una herramienta concreta dispare el clear.

**Posible corrección:**  
Restringir la comprobación a la herramienta que debe provocar el clear (p. ej. solo cuando `tool_call.name == "new_session"`) o usar un contrato explícito (p. ej. excepción o valor estructurado) en lugar de un substring en el texto.

---

## 4. **Estado interno de `CompactionSafeguard` modificado desde fuera**

**Ubicación:** `nanoiqqi/agent/loop.py` (manejo de `SessionCleared`), `nanoiqqi/agent/compaction.py`.

**Qué pasa:**  
Al capturar `SessionCleared` se hace:

```python
self.safeguard._safeguard_active = False
```

Se está tocando un atributo “privado” (`_safeguard_active`) de otro objeto desde el loop. El diseño actual hace que, tras un “new session”, el siguiente turno se comporte como si la compactación nunca hubiera estado activa, lo cual es coherente con una sesión nueva, pero la forma de hacerlo (mutar estado interno desde fuera) acopla el loop al detalle de implementación del safeguard.

**Inconsistencia:**  
Violación de encapsulación; cambios futuros en `CompactionSafeguard` podrían romper o requerir tocar el loop.

**Posible corrección:**  
Añadir en `CompactionSafeguard` un método público, p. ej. `reset()` o `mark_session_cleared()`, que ponga `_safeguard_active = False` (y quizá `_last_compaction_size`), y llamar a ese método desde el loop en lugar de asignar el atributo directamente.

---

## 5. **MCP nativo vs mcp2cli: quién tiene qué herramientas**

**Ubicación:** `nanoiqqi/agent/loop.py` (registro de herramientas, `_connect_mcp`, `subagent_tool_registry_factory`).

**Qué pasa:**  
- **MCP “nativo”** (`config.tools.mcp_servers`): se conecta en el primer uso en `_connect_mcp()` y las herramientas se registran solo en el agente principal (`self.tools`). Los subagentes no las reciben.  
- **mcp2cli**: se registra dentro de `register_shared_tools`, así que tanto el agente principal como los subagentes tienen las herramientas mcp2cli.

**Inconsistencia:**  
Desde el punto de vista del usuario, “MCP” puede significar tanto servidores MCP nativos como mcp2cli. El comportamiento es distinto: unas herramientas solo en el agente principal y otras también en subagentes. No es un bug per se, pero puede ser confuso si se espera que todo lo MCP se comporte igual.

**Posible corrección:**  
Documentar claramente en configuración y/o docs que los servidores MCP nativos son solo para el agente principal y que mcp2cli está disponible también en subagentes; o, si se desea paridad, exponer también las herramientas MCP nativas a los subagentes (con las implicaciones de sesión/conexión que eso tenga).

---

## 6. **`process_direct` y mensajes de tipo "system"**

**Ubicación:** `nanoiqqi/agent/loop.py` (`_process_message`, rama `msg.channel == "system"`).

**Qué pasa:**  
`process_direct` construye un `InboundMessage` con `channel` y `chat_id` por defecto `"cli"` y `"direct"`. Nunca usa `channel="system"`. La rama `if msg.channel == "system"` en `_process_message` existe para mensajes que llegan por el bus con origen “system” (p. ej. cron/heartbeat que inyectan con otro chat_id). Quienes llaman a `process_direct` (CLI, cron, heartbeat) no pasan `channel="system"`, así que esa rama no se ejecuta en esas vías.

**Inconsistencia:**  
Solo es inconsistencia si en algún sitio se documenta o se asume que “system” se usa vía `process_direct`; por el código actual, `process_direct` es siempre canal no-system. Revisar que no quede documentación o comentarios que digan lo contrario.

---

## 7. **Respuesta vacía explícita cuando `channel == "cli"` y `response is None`**

**Ubicación:** `nanoiqqi/agent/loop.py` en `run()`.

**Qué pasa:**  
Cuando `_process_message` devuelve `None` (porque la respuesta se envió con la herramienta `message`) y el canal es `"cli"`, el loop hace:

```python
elif msg.channel == "cli":
    await self.bus.publish_outbound(OutboundMessage(
        channel=msg.channel, chat_id=msg.chat_id, content="", metadata=msg.metadata or {},
    ))
```

Se publica un mensaje con `content=""` para que el consumidor (p. ej. CLI interactivo) reciba “algo” y pueda cerrar el turno. En modo interactivo, el consumidor ya habrá recibido antes el mensaje real publicado por la herramienta `message`, así que este mensaje vacío solo sirve como señal de “turno terminado”. Eso es coherente con el diseño actual; la inconsistencia real está en el modo `-m` (punto 1), no en este publish.

---

## 8. **Posible orden de mensajes outbound en un mismo turno**

**Ubicación:** `nanoiqqi/agent/loop.py`, `nanoiqqi/agent/tools/message.py`, consumidor en `commands.py`.

**Qué pasa:**  
Durante un turno pueden publicarse varios `OutboundMessage`: por ejemplo, actualizaciones de progreso (`_progress`) y luego la respuesta final (por contenido en `final_content` o por la herramienta `message`). El consumidor en `commands.py` distingue por `msg.metadata.get("_progress")` y por `turn_done`. Si en el futuro se añaden más publicaciones (p. ej. varios mensajes de la herramienta `message`), el orden y la asociación “último mensaje = respuesta del turno” dependen del orden en cola; no hay secuencia explícita ni identificador de turno en el mensaje.

**Inconsistencia menor:**  
Para el flujo actual puede ser suficiente, pero cualquier extensión que publique más de un mensaje “final” por turno podría hacer ambiguo qué debe mostrarse como respuesta. Considerar, si se extiende, un campo tipo `turn_id` o `is_final_reply` en `OutboundMessage`.

---

## Resumen de prioridad

| # | Severidad  | Resumen                                                                 |
|---|------------|-------------------------------------------------------------------------|
| 1 | Alta       | Modo `-m`: respuesta perdida si el modelo usa la herramienta `message` |
| 2 | Media      | `cache_dir` de mcp2cli en schema no usado en el wrapper                 |
| 3 | Media      | Clear de sesión disparado por cualquier tool que devuelva el marcador   |
| 4 | Media      | Encapsulación del safeguard rota (mutar `_safeguard_active` desde loop)  |
| 5 | Baja       | MCP nativo solo agente principal, mcp2cli también en subagentes         |
| 6 | Baja       | Aclarar que `process_direct` no usa canal "system"                      |
| 7 | N/A        | Comportamiento actual coherente (mensaje vacío en cli)                  |
| 8 | Baja       | Orden/identificación de mensajes outbound en turnos complejos            |

Si quieres, el siguiente paso puede ser proponer parches concretos para los puntos 1–4 (por ejemplo, corrección en modo `-m`, uso o eliminación de `cache_dir`, restricción del clear de sesión y método `reset()` en el safeguard).
