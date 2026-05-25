# MCP-CNC (scaffold)

Repositorio inicial con la estructura propuesta para el MCP + microservicios.

Servicios:
- `mcp-orchestrator` (FastAPI)
- `dxf-engine` (DXF handling + boolean ops)
- `cam-engine` (G-code generator)
- `catalogue` (tools & materials)
- `linuxcnc-bridge` (stub to send G-code)
- `chatgpt-agent` (natural language CNC design assistant)

LinuxCNC bridge remoto por Tailscale
-----------------------------------
`linuxcnc-bridge` ahora puede seguir en modo `stub` o conectarse a una instancia real de LinuxCNC mediante `linuxcncrsh` por TCP, lo que encaja bien si el PC de control está accesible por Tailscale.

Variables relevantes:

```bash
BRIDGE_BACKEND=linuxcncrsh
LINUXCNCRSH_HOST=100.x.y.z
LINUXCNCRSH_PORT=5007
LINUXCNCRSH_CONNECT_PASSWORD=
LINUXCNCRSH_ENABLE_PASSWORD=
LINUXCNCRSH_CLIENT_NAME=mcp-cnc
LINUXCNCRSH_TIMEOUT=2.0
LINUXCNCRSH_SOCKS5_PROXY_HOST=
LINUXCNCRSH_SOCKS5_PROXY_PORT=1080
LINUXCNC_REMOTE_GCODE_DIR=/home/cnc/linuxcnc/nc_files
```

Para el despliegue actual del taller, el bloque listo para copiar al `.env` del NAS es:

```bash
BRIDGE_BACKEND=linuxcncrsh
LINUXCNCRSH_HOST=100.x.y.z
LINUXCNCRSH_PORT=5007
LINUXCNCRSH_CONNECT_PASSWORD=
LINUXCNCRSH_ENABLE_PASSWORD=
LINUXCNCRSH_CLIENT_NAME=mcp-cnc
LINUXCNCRSH_TIMEOUT=2.0
LINUXCNCRSH_SOCKS5_PROXY_HOST=
LINUXCNCRSH_SOCKS5_PROXY_PORT=1080
LINUXCNC_REMOTE_GCODE_DIR=/home/linuxcnc/linuxcnc/nc_files
```

El repositorio incluye `.env.example` con las variables necesarias. Copia a `.env` y rellena las credenciales reales — el `.env` no se commitea.

Si el NAS no puede usar TUN/rutas de kernel para Tailscale, `linuxcnc-bridge` puede salir por un proxy SOCKS5. En ese caso define `LINUXCNCRSH_SOCKS5_PROXY_HOST` y `LINUXCNCRSH_SOCKS5_PROXY_PORT` para que la conexión TCP a `linuxcncrsh` pase por ese proxy en lugar de depender de una ruta `100.x` en el host.

En el host LinuxCNC debes tener `linuxcncrsh` levantado, por ejemplo desde HAL o desde terminal, y el puerto elegido debe ser accesible desde la red Tailscale.

Con esta configuración:
- `GET /status` intenta leer estado real de la máquina.
- `POST /motion/jog` usa `jog_incr` en modo teleop.
- `POST /motion/home` lanza `home -1`.
- `POST /gcode/send` y `POST /gcode/spindle` envían MDI.
- `POST /files/run` requiere además que `LINUXCNC_REMOTE_GCODE_DIR` apunte al directorio real de G-code en el host LinuxCNC.

Arrancar con Docker Compose:

```bash
docker-compose up --build
```

API de orquestación
-------------------
`mcp-orchestrator` actúa como proxy para los microservicios.

Endpoints disponibles:
- `GET /catalogue/tools`
- `GET /catalogue/materials`
- `GET /catalogue/designs`
- `GET /dxf/analyze?filename=<file>`
- `POST /dxf/rectangle`
- `POST /dxf/circle`
- `POST /dxf/text`
- `POST /dxf/nesting`
- `POST /dxf/boolean`
- `POST /cam/generate`

Los endpoints de `dxf-engine` y `cam-engine` se invocan internamente a través de los servicios Docker.

ChatGPT agent
--------------
`chatgpt-agent` proporciona una interfaz conversacional para crear diseños a partir de instrucciones naturales.

- `POST /chat` con payload `{ "prompt": "..." }`
- Traduce tus instrucciones a funciones de diseño y las ejecuta a través de `mcp-orchestrator`
- Soporta creación de DXF, operaciones booleanas, análisis de DXF y generación de G-code

Requisitos para `chatgpt-agent`:
- `OPENAI_API_KEY` debe estar configurado en el entorno del contenedor
- `OPENAI_MODEL` es opcional y por defecto es `gpt-4o-mini`

Configura la variable en `docker-compose.yml` o en tu entorno local:

```bash
export OPENAI_API_KEY=tu_api_key
```

Si usas Docker Compose, la variable se pasa al servicio automáticamente porque el `docker-compose.yml` ya incluye:

```yaml
  chatgpt-agent:
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
```

Ejemplo de petición a `chatgpt-agent`:

```json
{
  "prompt": "Crea un rectángulo de 80x40 mm y luego un círculo de 10 mm centrado en su interior.",
  "history": []
}
```

El servicio responde con el texto generado y el resultado de la operación ejecutada.

ChatGPT Business Plugin
-----------------------
También puedes usar `mcp-orchestrator` directamente como un plugin de ChatGPT Business, sin necesidad de `OPENAI_API_KEY` en tu entorno local.

- El orquestador expone `/.well-known/ai-plugin.json`
- Usa la URL pública de `mcp-orchestrator` como manifiesto de plugin
- El plugin se basa en el `openapi.json` de FastAPI para describir los endpoints

Si tu aplicación está detrás de `/mcp-cnc`, usa esta ruta:

```text
https://javitnas.ddns.net/mcp-cnc/.well-known/ai-plugin.json
```

En ese caso, configura `PLUGIN_BASE_URL` con la ruta completa base:

```bash
export PLUGIN_BASE_URL="https://javitnas.ddns.net/mcp-cnc"
```

Porque tu proxy Caddy ya entrega `/mcp-cnc/*` a `mcp-orchestrator`.

Endpoints disponibles para el plugin:
- `GET /catalogue/tools`
- `GET /catalogue/materials`
- `GET /catalogue/designs`
- `GET /dxf/analyze?filename=<file>`
- `POST /dxf/rectangle`
- `POST /dxf/circle`
- `POST /dxf/text`
- `POST /dxf/nesting`
- `POST /dxf/boolean`
- `POST /cam/generate`

Si expones `mcp-orchestrator` con una URL pública, registra esa URL como plugin de ChatGPT Business y el modelo podrá usar tu orquestador como herramienta.

Building for ARM64 (NAS)
---------------------------------
If you deploy to an ARM64 NAS but build on an x86 machine, use Docker Buildx to build multi-arch images.

Create and use a builder (one-time):

```bash
docker buildx create --name multiarch-builder --use
```

Example: build and push images for `linux/arm64` (push to registry):

```bash
docker buildx build --platform linux/arm64 -t mcp-cnc/mcp-orchestrator:latest -f mcp/Dockerfile mcp --push
docker buildx build --platform linux/arm64 -t mcp-cnc/dxf-engine:latest -f dxf-engine/Dockerfile dxf-engine --push
docker buildx build --platform linux/arm64 -t mcp-cnc/cam-engine:latest -f cam-engine/Dockerfile cam-engine --push
docker buildx build --platform linux/arm64 -t mcp-cnc/catalogue:latest -f catalogue/Dockerfile catalogue --push
docker buildx build --platform linux/arm64 -t mcp-cnc/linuxcnc-bridge:latest -f linuxcnc-bridge/Dockerfile linuxcnc-bridge --push
```

If you prefer to load the image into the local Docker daemon (requires buildx with qemu support), replace `--push` with `--load`.

Note: `docker-compose` will respect `platform: linux/arm64` entries in `docker-compose.yml`, but images must be available for that architecture (either pushed to a registry or built on the NAS).

NAS private registry and Caddy proxy
-----------------------------------
This repo also supports a NAS-hosted private registry behind Caddy for TLS and authentication.

On the NAS:
- `registry` must run on `127.0.0.1:5000` inside the NAS and be reachable from the Caddy proxy container.
- `odoo_local_proxy` must be able to resolve `registry` and `odoo_local_odoo` by Docker network alias.
- The `Caddyfile` should only proxy `/v2*` to `registry:5000` and use `odoo_local_odoo:8069` for the default web backend.

Example Caddy registry block:

```caddy
@registry {
    path /v2* /v2/*
}
handle @registry {
    basic_auth {
        javi <BCRYPT_HASH>
    }
    reverse_proxy registry:5000
}
```

Example Odoo backend block:

```caddy
reverse_proxy odoo_local_odoo:8069 {
    header_up X-Forwarded-Proto https
    header_up X-Forwarded-Host {host}
    header_up X-Forwarded-For {remote_host}
}
```

Make sure the proxy and backend containers share the same Docker network, for example `odoo_local_net`.

Offline image transfer for NAS
-----------------------------
If the NAS cannot pull directly from Docker Hub, build or pull the ARM64 image on your PC and transfer it with `scp`:

```powershell
# on PC
docker pull --platform linux/arm64 registry:2
docker save registry:2 -o registry_arm64.tar
scp -P 9222 registry_arm64.tar admin@javitnas.ddns.net:/tmp/
```

On the NAS:

```bash
sudo docker load -i /tmp/registry_arm64.tar
```

Login from your client:

```powershell
docker login javitnas.ddns.net -u javi
```

If your NAS is behind a router, forward public port `8443` (or `443`) to the NAS internal IP and port `8443` to allow external access.

Pushing ARM64 images from a PC to the NAS
----------------------------------------
Use the PowerShell helper script to pull, save, transfer, and load ARM64 images in one step.

```powershell
.
\scripts\push-images-to-nas-registry.ps1 \
  -NASHost javitnas.ddns.net \
  -Port 9222 \
  -User admin \
  -Images @('registry:2', 'curlimages/curl:latest')
```

This will:
- pull each image for `linux/arm64`
- save it to a TAR file locally
- copy it to the NAS via `scp`
- load it into Docker on the NAS

If your NAS user requires sudo for Docker, the script now allocates a tty so the password prompt works correctly.

Deployment summary
------------------
1. Build or transfer ARM64 images for the NAS.
2. Run the registry on the NAS and ensure it is available to the proxy container.
3. Configure `Caddyfile` so `/v2*` routes to `registry:5000` and `/` routes to `odoo_local_odoo:8069`.
4. Ensure `odoo_local_proxy`, `registry`, and `odoo_local_odoo` are on the same Docker network (`odoo_local_net`).
5. Test locally from the proxy container:
   - `curl http://registry:5000/v2/`
   - `curl http://odoo_local_odoo:8069/`
6. Test external access from the client:
   - `docker login javitnas.ddns.net -u javi`
   - `curl https://javitnas.ddns.net/v2/`

NAS recovery
------------
If services stop or the NAS needs a restart, use these commands to recover the deployment:

```bash
# restart Docker if needed
sudo service docker restart

# restart or restart the proxy container
sudo docker restart odoo_local_proxy

# make sure the registry, Odoo, and proxy are on the same Docker network
sudo docker network connect --alias registry odoo_local_net registry
sudo docker network connect --alias odoo_local_odoo odoo_local_net odoo_local_odoo

# restart the backend containers
sudo docker restart odoo_local_odoo
sudo docker restart registry
sudo docker restart odoo_local_proxy

# verify from the proxy container
sudo docker exec odoo_local_proxy curl -v http://registry:5000/v2/
sudo docker exec odoo_local_proxy curl -v http://odoo_local_odoo:8069/
```

If the proxy still returns `502`, inspect the proxy logs and DNS resolution inside the proxy:

```bash
sudo docker logs odoo_local_proxy --tail 100
sudo docker exec odoo_local_proxy getent hosts odoo_local_odoo registry || true
```

