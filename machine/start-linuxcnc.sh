#!/bin/bash
export DISPLAY=:99

# Esperar a Mesa
until ping -c1 -W1 10.10.10.10 >/dev/null 2>&1; do
    echo "Waiting for Mesa 10.10.10.10..."
    sleep 2
done

# Iniciar Xvfb si no existe
if ! pgrep -f "Xvfb :99" >/dev/null; then
    /usr/bin/Xvfb :99 -screen 0 1024x768x24 -nolisten tcp >/dev/null 2>&1 &
    sleep 2
fi

# Iniciar LinuxCNC
/usr/bin/linuxcnc /home/linuxcnc/linuxcnc/configs/elefant/elefant.ini >/home/linuxcnc/linuxcnc_autostart.log 2>&1 &

# Mantener vivo
while true; do sleep 3600; done
