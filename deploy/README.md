# Deploying the prompt_guidance MCP server (HTTP/SSE)

PR #7 ships the stdio MCP wrapper at `prompt_guidance/mcp_server.py`. Local MCP clients (Claude Code, Claude Desktop, Codex CLI, Claw CLI) reach it directly via stdio — no service required.

This directory is the **production deployment recipe** for an HTTP/SSE wrapper so OFF-HOST clients (claude.ai web UI, chatgpt.com, remote agents) can also call the same two governance tools. The wrapper is `mcp-proxy` (the same npm binary used by `memory-mcp.service`) launching the stdio server as a subprocess.

The deployment was performed against the live host on 2026-05-08 under governed task `cc-81853411` (Codex QC `lt-qc-c3e9f358` — `validated_approved` · `substance_valid: True`). This file records what landed and how to reproduce it.

## Architecture

```
[external client]                                  [host]
                                                    ┌─────────────────────────┐
                                                    │ mcp-proxy               │
  claude.ai / chatgpt.com  ──HTTPS──▶ Cloudflare ──▶│ :9003 (127.0.0.1)       │
  (or local curl)                     Zero Trust    │                         │
                                      tunnel        │  spawns subprocess:     │
                                                    │  python3 -m             │
                                                    │  prompt_guidance        │
                                                    │  .mcp_server (stdio)    │
                                                    └─────────────────────────┘
```

- `mcp-proxy` listens on `127.0.0.1:9003` (loopback only). It enforces an `X-API-Key` header on every request.
- It launches `python3 -m prompt_guidance.mcp_server` as a subprocess and bridges MCP messages between the HTTP/SSE transport and the subprocess's stdio.
- Public reachability is **not** automatic: a separate operator step in Cloudflare Zero Trust (or any reverse proxy) must point a public hostname at `http://localhost:9003`.

## Files in this recipe

| File | Purpose |
|---|---|
| `prompt-guidance-mcp.service.example` | systemd unit. Install at `/etc/systemd/system/prompt-guidance-mcp.service` (mode 644 root:root). |
| `prompt-guidance-mcp.env.example` (NOT included; create on the host) | env file holding `MCP_PROXY_API_KEY=<256-bit hex>`. Install at `/etc/systemd/system/prompt-guidance-mcp.env` (mode 600 root:root). |

Secrets are **never** committed to this repo.

## Step-by-step on a fresh host

```bash
# 1. Generate a 256-bit token (32 hex bytes -> 64 chars).
KEY=$(openssl rand -hex 32)

# 2. Write the env file (chmod 600 root).
sudo install -m 600 -o root -g root /dev/null /etc/systemd/system/prompt-guidance-mcp.env
echo "MCP_PROXY_API_KEY=$KEY" | sudo tee /etc/systemd/system/prompt-guidance-mcp.env > /dev/null

# 3. Install the unit.
sudo install -m 644 -o root -g root \
    deploy/prompt-guidance-mcp.service.example \
    /etc/systemd/system/prompt-guidance-mcp.service

# 4. Reload systemd, enable + start.
sudo systemctl daemon-reload
sudo systemctl enable --now prompt-guidance-mcp.service

# 5. Verify.
systemctl is-active prompt-guidance-mcp.service       # -> active
ss -ltn | grep ":9003 "                                # -> 127.0.0.1:9003 only

# 6. Smoke-test (replace $KEY with the env value).
curl -sS -X POST http://127.0.0.1:9003/mcp \
    -H "X-API-Key: $KEY" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"0.1"}}}' \
    --max-time 10
```

A successful initialize returns:

```
event: message
data: {"result":{"protocolVersion":"2024-11-05","capabilities":{...},"serverInfo":{"name":"prompt_guidance","version":"1.27.1"}},"jsonrpc":"2.0","id":1}
```

## Public-exposure step (Cloudflare Zero Trust — operator dashboard)

The host's `cloudflared.service` runs a Cloudflare Zero Trust managed tunnel. Routes are configured in the Cloudflare dashboard, not in any local file. To expose this MCP server to claude.ai / chatgpt.com:

1. Cloudflare dashboard → Zero Trust → Networks → Tunnels.
2. Select the existing tunnel for this host.
3. Add a public hostname (e.g. `mcp-governance.example.com`) routing to `http://localhost:9003`.
4. In claude.ai → Settings → Integrations → Add custom connector:
   - Name: `prompt_guidance`
   - URL: `https://mcp-governance.example.com/mcp` (or `/sse`)
   - API Key (X-API-Key): the value of `MCP_PROXY_API_KEY`.
5. In ChatGPT → Settings → Integrations: same pattern.

This step deliberately stays out of automated deployment because changes to the live tunnel can affect other tunneled services and are operator-territory.

## Hardening notes

The unit applies:
- `User=ubuntu Group=ubuntu` (unprivileged)
- `NoNewPrivileges=true`
- `PrivateTmp=true`
- `ProtectSystem=strict`
- `ProtectHome=read-only`
- `ProtectKernelTunables / ProtectKernelModules / ProtectControlGroups=true`
- API key passed via `MCP_PROXY_API_KEY` env (NOT command line) so it does not appear in `/proc/<pid>/cmdline`.

The bind is loopback-only. Anything that wants public reach goes through Cloudflare with its own auth. There is no path on this host where a non-root, non-`ubuntu` local user can read the API key or talk to the service without the key.

## Rollback

```bash
sudo systemctl disable --now prompt-guidance-mcp.service
sudo rm /etc/systemd/system/prompt-guidance-mcp.service
sudo rm /etc/systemd/system/prompt-guidance-mcp.env
sudo systemctl daemon-reload
```

This is fully reversible. No other systemd unit, port, or service is touched.

## What this PR does NOT do

- Does not modify `cloudflared.service` or any tunnel route.
- Does not modify any other systemd unit.
- Does not commit any secret.
- Does not change `prompt_guidance/mcp_server.py` (that shipped in PR #7).
- Does not add the new server to any MCP client config (one-time operator edit; sample in `AGENTS.md`).

## Lineage

- Wrapper code: PR #7 (`cc-5baa4838` / `lt-qc-32690c14`).
- Deployment: `cc-81853411` (`lt-qc-c3e9f358`); host on 2026-05-08T21:30Z.
