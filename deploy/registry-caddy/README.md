Registry behind Caddy (TLS + Basic auth)
========================================

This folder contains a minimal `docker-compose.yml` to run a Docker Registry bound to
`127.0.0.1:5000` and a sample `Caddyfile` that instructs an existing Caddy instance
to reverse-proxy `javitnas.ddns.net` to the local registry and protect it with `basicauth`.

Why bind to localhost?
- We assume you already have Caddy running on the NAS and handling TLS for `javitnas.ddns.net`.
- Binding the registry to `127.0.0.1:5000` prevents it being directly exposed on the public IP.

Files
- `docker-compose.yml`: runs `registry:2` and stores data at `./data`.
- `Caddyfile`: example snippet to add to your Caddy configuration (replace `<USER:HASH>`).

Steps to install
1. On the NAS, go to this folder and start the registry:

```bash
cd /path/to/MCP-CNC/deploy/registry-caddy
docker compose up -d
```

2. Create a bcrypt htpasswd line for your user (run on your workstation or NAS):

```bash
docker run --rm httpd:2-alpine htpasswd -Bbn registryuser 'TuContraseñaSegura'
# Example output: registryuser:$2y$05$...hash...
```

3. Edit `Caddyfile` and replace `<USER:HASH>` with the full htpasswd line from step 2.

4. Reload Caddy configuration.
- If Caddy is running as a system service, update its Caddyfile (or include this snippet) and reload:

```bash
sudo systemctl reload caddy
```

- If Caddy is running in Docker, copy the snippet into the container's Caddyfile and restart the container.

5. Test remote login/push/pull from your workstation:

```bash
docker login javitnas.ddns.net
docker tag mcp-cnc/mcp-orchestrator:0.1.0 javitnas.ddns.net/mcp-cnc/mcp-orchestrator:0.1.0
docker push javitnas.ddns.net/mcp-cnc/mcp-orchestrator:0.1.0
```

Notes & Troubleshooting
- Make sure Caddy is serving `javitnas.ddns.net` with a valid TLS certificate (Let's Encrypt).
- If Caddy is containerized, ensure it can reach `localhost:5000` on the host, or instead run the registry
  on the same Docker network and update `reverse_proxy` target to the registry container name and port.
- Back up `./data` regularly; it contains your Docker images.
