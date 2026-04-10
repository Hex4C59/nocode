# Claude-Style Tools In `nocode`

This project now ships a local tool subset inspired by Claude Code.

## Supported Now

- `read_file`
  - Read UTF-8 text files from the workspace with optional line offsets.
- `glob_files`
  - Find files with glob patterns.
- `search_text`
  - Search UTF-8 text files with a regular expression.
- `run_shell_command`
  - Run a command as argv without `shell=True`.
- `todo_write`
  - Maintain a lightweight in-memory todo list for the current TUI session.
- `ask_user`
  - Pause tool execution and ask the user a focused text question.
- `web_fetch`
  - Fetch an HTTP(S) page and return response text.

## Local-Only Design

- Tools run against the local workspace rooted at the current repository.
- Shell execution is argv-based for cross-platform behavior.
- Tool results are returned through Anthropic `tool_result` blocks.
- TUI shows tool calls, todo state, and pending user questions inline.

## Intentionally Out Of Scope

These Claude Code capabilities are not implemented in this local runtime:

- MCP servers and dynamic MCP tools
- Browser automation and interactive web panels
- VS Code bridge and LSP-backed tools
- Remote triggers, notifications, cloud control plane features
- Claude Code internal agents, coordinator mode, and remote orchestration

## Notes

- The Anthropic / Kimi Anthropic-compatible path is the primary tool loop target.
- `NOCODE_LLM=moonshot` still falls back to single-round chat because its OpenAI-style tool protocol is not implemented yet.
