# Odoo / cnc_bench.js — unversioned production patches (2026-05-25)

These changes were applied directly on the NAS. The Odoo addon directory is
not a git repo, so they are documented here for traceability.

## Root cause

`cnc_bench.js checkServices()` called `/cnc/bench/api/pins?filter=estop`.
That route had `auth="user"` (303 redirect for anonymous visitors) and, even
when authenticated, proxied to `mcp_base_url/hal/pins` which did not exist in
the MCP orchestrator (now fixed in commit `7683597`).
Result: hal_bridge and Mesa HAL pins always showed DOWN on the bench web.

---

## Patch 1 — new Odoo controller route `/cnc/bench/api/health`

**File:** `controllers/main.py`  
**NAS path (Docker bind-mount):** `/opt/cnc/odoo-addons/cnc_dashboard/controllers/main.py`  
**Backup created:** `main.py.bak-2026-05-24` (same directory, before edit)

Function added immediately after `cnc_bench_health`:

```python
@http.route("/cnc/bench/api/health", type="http", auth="public", methods=["GET"], csrf=False)
def cnc_bench_api_health(self, **kwargs):
    payload, status = self._proxy_json("GET", "machine/health")
    return self._json_response(payload, status=status)
```

Proxies to `mcp_base_url/machine/health` with the same Bearer token mechanism
as all other `_proxy_json()` calls. `auth="public"` so the bench page can poll
it without an Odoo session.

---

## Patch 2 — `/cnc/bench/api/pins` auth changed to `public`

**File:** `controllers/main.py` (same file as above)  
**Change:** decorator `auth="user"` → `auth="public"` on the `/cnc/bench/api/pins` route only.

This unblocks unauthenticated bench visitors from reaching the pins proxy.
The downstream route (`mcp /hal/pins` → bridge `/hal/pins`) is now implemented
(commit `7683597`), so the full chain is operational.

Patch applied with:
```bash
python3 -c "
import pathlib
p = pathlib.Path('/opt/cnc/odoo-addons/cnc_dashboard/controllers/main.py')
t = p.read_text()
t = t.replace(
    '@http.route(\"/cnc/bench/api/pins\", type=\"http\", auth=\"user\"',
    '@http.route(\"/cnc/bench/api/pins\", type=\"http\", auth=\"public\"',
    1)
p.write_text(t)
print('done')
"
```

---

## Patch 3 — `cnc_bench.js` rewritten `checkServices()`

**File:** `static/src/js/cnc_bench.js`  
**NAS path:** `/opt/cnc/odoo-addons/cnc_dashboard/static/src/js/cnc_bench.js`  
**Backup created:** `cnc_bench.js.bak-2026-05-24` (same directory, before edit)

`checkServices()` was rewritten to call `/cnc/bench/api/health` (Patch 1)
instead of `/cnc/bench/api/pins?filter=estop`.

Old logic (broken):
```js
fetch('/cnc/bench/api/pins?filter=estop')
  .then(r => r.json())
  .then(data => {
      setService('hal',  data.ok ? 'ok' : 'down');
      setService('mesa', data.ok ? 'ok' : 'down');
  })
  .catch(() => { setService('hal','down'); setService('mesa','down'); });
```

New logic:
```js
fetch('/cnc/bench/api/health')
  .then(r => r.json())
  .then(data => {
      setService('hal',  data.hal_bridge?.status === 'ok' ? 'ok' : 'down');
      setService('mesa', data.mesa_pins?.status  === 'ok' ? 'ok' : 'down');
  })
  .catch(() => { setService('hal','down'); setService('mesa','down'); });
```

`refreshPins()` and `refreshMesaInputs()` had their `setService('hal'/'mesa')`
side-effects removed so service indicators are driven only by `checkServices()`.

---

## Restart after patching

```bash
# On NAS:
docker compose restart odoo
```

## Verification

```bash
# Should return JSON (not 303):
curl -s https://<nas>/cnc/bench/api/health | python3 -m json.tool
curl -s https://<nas>/cnc/bench/api/pins   | python3 -m json.tool

# Bench page: hal_bridge and Mesa HAL pins indicators should reflect
# /machine/health values instead of always showing DOWN.
```
