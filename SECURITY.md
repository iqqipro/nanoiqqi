# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in **nanoiqqi**, please report it by:

1. **DO NOT** open a public GitHub issue.
2. Create a private security advisory on GitHub or contact the repository maintainers: **contactiqqi@gmail.com**.
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We aim to respond to security reports within 48 hours.

---

## Security Best Practices

### 1. API Key and Secret Management

**CRITICAL**: Never commit API keys or secrets to version control.

- Store secrets in `~/.nanoiqqi/config.json` with restricted file permissions:
  ```bash
  chmod 600 ~/.nanoiqqi/config.json
  chmod 700 ~/.nanoiqqi
  ```
- Consider environment variables for sensitive keys where supported.
- Rotate API keys regularly and use separate keys for development and production.
- Config file path is defined in `nanoiqqi/config/loader.py` (default: `~/.nanoiqqi/config.json`).

### 2. Channel Access Control

**IMPORTANT**: Configure `allowFrom` for production so only allowed users can talk to the agent.

In `~/.nanoiqqi/config.json`:

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["123456789", "987654321"]
    },
    "whatsapp": {
      "enabled": true,
      "allowFrom": ["+1234567890"]
    }
  }
}
```

- **Empty `allowFrom`** means **allow all** (convenient for personal use; lock it down for production).
- Channel configs and allowlists are in `nanoiqqi/config/schema.py` and enforced in `nanoiqqi/channels/base.py`.

### 3. Shell Command Execution (`exec` tool)

The `exec` tool (`nanoiqqi/agent/tools/shell.py`) runs shell commands. Safeguards in this repo:

- **Timeout**: Configurable via `tools.exec.timeout` (default **60** seconds). Process is killed on timeout.
- **Output truncation**: Command output is truncated at **10,000** characters.
- **Blocked patterns** (deny list):
  - `rm -r`, `rm -rf`, `rm -fr`
  - `del /f`, `del /q`
  - `rmdir /s`
  - `format` (standalone)
  - `mkfs`, `diskpart`
  - `dd if=`
  - Writes to `/dev/sd*`
  - `shutdown`, `reboot`, `poweroff`
  - Fork bomb pattern `:() { ... }; :`
- **Optional workspace restriction**: When `tools.restrictToWorkspace` is `true`, execution is restricted to the workspace directory (see schema and loader).

**Recommendations:**

- Run nanoiqqi as a **non-root**, dedicated user.
- Review agent logs for tool usage.
- Do not disable or weaken these checks on systems with sensitive data.

### 4. File System Access

File tools (`read_file`, `write_file`, `edit_file`, `list_dir`) in `nanoiqqi/agent/tools/filesystem.py` respect:

- **`tools.restrictToWorkspace`**: When `true`, all file operations are limited to the workspace directory (config: `gateway.workspace`, default `~/.nanoiqqi/workspace`). This mitigates path traversal and access outside the intended directory.

Set in config:

```json
{
  "tools": {
    "restrictToWorkspace": true
  }
}
```

- Run with a dedicated user and use OS permissions to protect sensitive directories.

### 5. Network and External Services

- **HTTPS**: External API calls use HTTPS (LiteLLM, OpenRouter, etc.).
- **Timeouts**: HTTP clients use timeouts (e.g. web_fetch 30s, web_search 10s, exec 60s) to reduce hang risk.
- **WhatsApp bridge**:
  - The Node.js bridge connects to the Python process via WebSocket. Default URL is `ws://localhost:3001` (`channels.whatsapp.bridge_url`).
  - Set `channels.whatsapp.bridge_token` in config and pass it as `BRIDGE_TOKEN` when starting the bridge so the bridge can authenticate (see `nanoiqqi/channels/whatsapp.py` and `nanoiqqi/cli/commands.py`).
  - Bridge files are copied under `~/.nanoiqqi/bridge`; keep that directory and config permissions restrictive.

### 6. Dependencies

- Keep dependencies updated. The project uses **pip** (Python) and **npm** (bridge).
- Audit dependencies periodically:

  ```bash
  pip install pip-audit
  pip-audit

  cd bridge
  npm audit
  npm audit fix
  ```

- Install from source: `pip install -e .` in the repo root. Do not rely on unpublished or untrusted packages.

### 7. Production Deployment

- **Isolation**: Run in a container or VM when possible.
- **User**: Run as a dedicated user, not root:
  ```bash
  sudo useradd -m -s /bin/bash nanoiqqi
  sudo -u nanoiqqi nanoiqqi gateway
  ```
- **Permissions**:
  ```bash
  chmod 700 ~/.nanoiqqi
  chmod 600 ~/.nanoiqqi/config.json
  chmod 700 ~/.nanoiqqi/bridge
  ```
- **Config**: Set `tools.restrictToWorkspace: true` for production when appropriate.
- **Rate limiting**: Rely on your LLM/API provider rate and spending limits; monitor usage.

### 8. Data Privacy

- **Logs** may contain user content or identifiers; protect log storage and retention.
- **LLM providers** receive prompts and responses; review their privacy and data policies.
- **Local state**: Session and workspace data under `~/.nanoiqqi` (and workspace path) should be protected with OS permissions.
- **Config**: API keys and tokens are stored in plain text in `config.json`; restrict file access and consider a keyring for high-security environments.

### 9. Incident Response

If you suspect a security incident:

1. Revoke compromised API keys and tokens immediately.
2. Review logs for unauthorized access or unexpected tool use.
3. Check for unexpected file or config changes under `~/.nanoiqqi`.
4. Rotate credentials and update to the latest nanoiqqi version.
5. Report to maintainers (contactiqqi@gmail.com) if it affects the nanoiqqi project.

---

## Security-Relevant Features in This Repo

| Feature | Location | Description |
|--------|----------|-------------|
| Path / workspace restriction | `config/schema.py`, `config/loader.py`, `agent/tools/filesystem.py`, `agent/tools/shell.py` | `tools.restrictToWorkspace` limits file and shell access to the workspace. |
| Channel allowlist | `config/schema.py`, `channels/base.py` | `allowFrom` per channel; empty = allow all. |
| Exec timeout | `config/schema.py` (`ExecToolConfig.timeout`), `agent/tools/shell.py` | Default 60s; configurable. |
| Exec deny list | `agent/tools/shell.py` | Blocks dangerous command patterns. |
| Exec output truncation | `agent/tools/shell.py` | 10,000 character limit. |
| Bridge token | `config/schema.py` (`WhatsAppConfig.bridge_token`), `channels/whatsapp.py`, `cli/commands.py` | Optional shared secret for WhatsApp bridge. |

---

## Known Limitations

- **No built-in rate limiting** for user messages; add at the channel or gateway layer if needed.
- **Config and secrets** are stored in plain text; use OS permissions and optionally a keyring.
- **No automatic session expiry**; implement cleanup or retention policies if required.
- **Exec filtering** is pattern-based and may not cover every dangerous command; run with least privilege.
- **Security event logging** is limited; enhance logging or integrate with your SIEM if needed.

---

## Security Checklist Before Deployment

- [ ] API keys and tokens not in code or public repos
- [ ] `~/.nanoiqqi/config.json` permissions set to `0600`
- [ ] `allowFrom` configured for all enabled channels in production
- [ ] Process runs as non-root user
- [ ] `tools.restrictToWorkspace` set to `true` when appropriate
- [ ] Dependencies reviewed and updated (`pip-audit`, `npm audit`)
- [ ] Logs and `~/.nanoiqqi` directory protected and monitored
- [ ] API provider rate/spending limits and monitoring in place
- [ ] Custom skills and tools reviewed for security impact

---

## Updates

**Last updated**: 2026-03-12

For security advisories and releases:

- GitHub: [iqqipro/nanoiqqi](https://github.com/iqqipro/nanoiqqi)
- Security advisories: https://github.com/iqqipro/nanoiqqi/security/advisories

## License

See the LICENSE file in the repository root.
