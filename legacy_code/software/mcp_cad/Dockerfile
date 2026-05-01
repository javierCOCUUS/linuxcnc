FROM python:3.11-slim

# Evitar que python escriba *.pyc y forzar stdout inmediato sin buffers
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar las librerias optimizadas
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copiar el subproyecto en su ruta de paquete
RUN mkdir -p /app/software/mcp_cad
COPY . /app/software/mcp_cad/
# Nos aseguramos de inicializar las carpetas internas vac├¡as si Docker omite locales
RUN mkdir -p /app/software/mcp_cad/outputs /app/software/mcp_cad/libreria_dxf

# Exponer el puerto SSE hacia tu NGINX/Tailscale (p.ej. 8000)
EXPOSE 8000

# Lanzamiento Starlette via Uvicorn asincrono
CMD ["uvicorn", "software.mcp_cad.mcp_server:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
