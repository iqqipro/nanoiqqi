# Available Tools

This document describes the tools available to nanoiqqi.

## File Operations

### read_file
Read the contents of a file.
```
read_file(path: str) -> str
```

### write_file
Write content to a file (creates parent directories if needed).
```
write_file(path: str, content: str) -> str
```

### edit_file
Edit a file by replacing specific text.
```
edit_file(path: str, old_text: str, new_text: str) -> str
```

### list_dir
List contents of a directory.
```
list_dir(path: str) -> str
```

## Shell Execution

### exec
Execute a shell command and return output.
```
exec(command: str, working_dir: str = None) -> str
```

**Safety Notes:**
- Commands have a configurable timeout (default 60s)
- Dangerous commands are blocked (rm -rf, format, dd, shutdown, etc.)
- Output is truncated at 10,000 characters
- Optional `restrictToWorkspace` config to limit paths

## Web Access

### web_search
Search the web using Brave Search API.
```
web_search(query: str, count: int = 5) -> str
```

Returns search results with titles, URLs, and snippets. Requires `tools.web.search.apiKey` in config.

### web_fetch
Fetch and extract main content from a URL.
```
web_fetch(url: str, extractMode: str = "markdown", maxChars: int = 50000) -> str
```

**Notes:**
- Content is extracted using readability
- Supports markdown or plain text extraction
- Output is truncated at 50,000 characters by default

## Leads (México – DENUE)

### LeadsMx
Busca establecimientos en México con la API DENUE (INEGI). **Siempre hay que enviar el parámetro `method`.** No enviar cadenas vacías en entidad/municipio: usar `"00"` (todo el país) o `"0"` (omitir) o la clave correcta. **entidad** acepta clave de 2 dígitos **o** nombre/alias de estado (ej. Jalisco, CDMX); **estrato** acepta 0–7 **o** expresiones como "micro", "grande", "pyme"; la tool traduce.

```
LeadsMx(method, ...) -> str
```

**Reglas:** (1) Siempre incluir `method`. (2) Nunca enviar `entidad=""` ni `municipio=""`: usar `"00"` o `"0"` o la clave (ej. entidad=15 Estado de México, municipio=107 Toluca). (3) Para "buscar en [ciudad]" usar `method=buscarEntidad` con `condicion` y `entidad` (ver skill leads_mx para claves).

| Método | Parámetros típicos |
|--------|--------------------|
| **buscar** | condicion (oblig.), coordenadas?, distancia? (máx 5000 m) |
| **ficha** | id (oblig.) |
| **nombre** | nombre (oblig.), entidad?, registro_inicial?, registro_final? |
| **buscarEntidad** | condicion, entidad (ej. 15), registro_inicial?, registro_final? |
| **buscarAreaAct** | entidad, municipio?, sector?, …, nombre?, registro_inicial?, registro_final? |
| **buscarAreaActEstr** | igual + estrato? (0–7) |
| **cuantificar** | actividad?, area_geografica?, estrato? ("0" = no filtrar) |

**Ejemplos:** Buscar en Toluca → `method=buscarEntidad`, `condicion=toluca` (o tipo de negocio), `entidad=15`, `registro_inicial=1`, `registro_final=50`. Listar por municipio Toluca → `method=buscarAreaActEstr`, `entidad=15`, `municipio=107`, `nombre=0` o palabra, `registro_inicial=1`, `registro_final=50`.

- **entidad:** 2 dígitos o nombre/alias de estado (Jalisco, CDMX, etc.); "00" = todo el país.
- **estrato:** 0–7 o expresiones ("micro", "grande", "pyme"); la tool traduce.
- **Paginación:** registro_inicial, registro_final (ej. 1 y 50).

Requiere `tools.leads_mx.token` en config (https://www.inegi.org.mx/app/api/denue/).

## Image Generation

### generate_image
Generate an image from a text prompt using OpenRouter (e.g. Flux, Sourceful).
```
generate_image(prompt: str, model: str = None) -> str
```

Use when the user asks for a photo, illustration, or picture. Images are saved under `workspace/.nanoiqqi/generated/`. Returns the file path(s). Requires OpenRouter API key; optional `tools.image.model` in config for default model.

## Communication

### message
Send a message to the user (used internally).
```
message(content: str, channel: str = None, chat_id: str = None) -> str
```

## Background Tasks

### spawn
Spawn a subagent to handle a task in the background.
```
spawn(task: str, label: str = None) -> str
```

Use for complex or time-consuming tasks that can run independently. The subagent will complete the task and report back when done.

## Scheduled Reminders (Cron)

Use the `exec` tool to create scheduled reminders with `nanoiqqi cron add`:

### Set a recurring reminder
```bash
# Every day at 9am
nanoiqqi cron add --name "morning" --message "Good morning! ☀️" --cron "0 9 * * *"

# Every 2 hours
nanoiqqi cron add --name "water" --message "Drink water! 💧" --every 7200
```

### Set a one-time reminder
```bash
# At a specific time (ISO format)
nanoiqqi cron add --name "meeting" --message "Meeting starts now!" --at "2025-01-31T15:00:00"
```

### Manage reminders
```bash
nanoiqqi cron list              # List all jobs
nanoiqqi cron remove <job_id>   # Remove a job
```

## Heartbeat Task Management

The `HEARTBEAT.md` file in the workspace is checked every 30 minutes.
Use file operations to manage periodic tasks:

### Add a heartbeat task
```python
# Append a new task
edit_file(
    path="HEARTBEAT.md",
    old_text="## Example Tasks",
    new_text="- [ ] New periodic task here\n\n## Example Tasks"
)
```

### Remove a heartbeat task
```python
# Remove a specific task
edit_file(
    path="HEARTBEAT.md",
    old_text="- [ ] Task to remove\n",
    new_text=""
)
```

### Rewrite all tasks
```python
# Replace the entire file
write_file(
    path="HEARTBEAT.md",
    content="# Heartbeat Tasks\n\n- [ ] Task 1\n- [ ] Task 2\n"
)
```

---

## Adding Custom Tools

To add custom tools:
1. Create a class that extends `Tool` in `nanoiqqi/agent/tools/`
2. Implement `name`, `description`, `parameters`, and `execute`
3. Register it in `AgentLoop._register_default_tools()`
