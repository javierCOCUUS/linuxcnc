# machine/

Configuración real de la máquina (LinuxCNC 2.9.8, Debian 13 PREEMPT_RT, Mesa 7i95 por Ethernet en 10.10.10.10).

- `elefant/`: `elefant.ini`, `main.hal`, `io.hal`, `tool.tbl`, `parameters.var` (generados con Mesa Config Tool 2.1.8 el 2026-05-31).
- `tools/`: `hal_bridge.py` (HTTP en :8010, expone `halcmd show pin`) y `start-linuxcnc.sh` (autoarranque con Xvfb).

Notas:
- `elefant.ini` declara `SPINDLES = 1`, y `[OUTPUTS]` está vacío; las macros M101-M103 de `linuxcnc-bridge/` asumen 3 spindles con `M64/M65 P3-P5`.
- `SUBROUTINE_PATH` apunta a `/home/linuxcnc/linuxcnc/subroutines`, que no existe en la máquina.
- No se incluyen los zips de `backups/` ni los `.bak`.
