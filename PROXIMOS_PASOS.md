# Próximos Desarrollos - MCP-CNC 🚀

Este documento detalla la hoja de ruta y las ideas para la evolución del ecosistema **MCP-CNC**.

---

## ✅ Estado Actual
El proyecto cuenta con una arquitectura de microservicios sólida:
- **Orquestador (MCP):** Centraliza las peticiones y expone herramientas a ChatGPT.
- **DXF-Engine:** Capacidad avanzada de diseño paramétrico, anidamiento (nesting) y operaciones booleanas.
- **CAM-Engine:** Generación de G-code con soporte para perfiles, cajeras (pockets), taladros y grabado, incluyendo lógica de pestañas (tabs) y rampas de entrada.
- **LinuxCNC Bridge:** Interfaz (actualmente stub) para la comunicación con la máquina real.
- **Visualizador:** Herramientas para previsualización de diseños.

---

## 🛠️ Corto Plazo (Inmediato)
1.  **Implementación Real de LinuxCNC Bridge:**
    - Reemplazar el `stub` por una conexión real vía `linuxcnc-python` o sockets (HAL/NML).
    - Reporte de estado en tiempo real (coordenadas, velocidad real, estado del spindle).
2.  **Optimización de Trayectorias:**
    - Algoritmo de "ordenación de entidades" para minimizar los movimientos rápidos (G0) entre cortes.
    - Soporte para cambios de herramienta automáticos (M6) si el G-code incluye múltiples operaciones.
3.  **Base de Datos de Herramientas Dinámica:**
    - Integración con una base de datos real (o archivo JSON persistente) para gestionar diámetros, avances y velocidades recomendadas por material.
4.  **Feedback Visual en ChatGPT:**
    - Mejorar la integración del visualizador para que el agente pueda mostrar una imagen del diseño generado antes de confirmar el mecanizado.

---

## 🏗️ Medio Plazo (Expansión)
1.  **Panel de Control Web (Dashboard):**
    - Interfaz React/Next.js para monitorizar la máquina, ver el progreso del trabajo y controlar ejes manualmente (Jog).
2.  **Estrategias de Mecanizado Avanzadas:**
    - **Entradas helicoidales:** Para evitar estrés en la herramienta al entrar en material duro.
    - **Trocoidal:** Para desbaste de alta eficiencia.
    - **Compensación de radio de herramienta (G41/G42):** Implementada en el motor CAM.
3.  **Gestión de Inventario (Odoo Integration):**
    - Sincronizar el uso de materiales y herramientas con Odoo para control de stock automático tras cada trabajo.
4.  **Anidamiento Automático Inteligente:**
    - Mejorar el `nesting` para aprovechar retales de material y piezas de formas irregulares.
5.  **Motor CAD Inteligente (Alineación y Referencias):**
    - **`dxf_get_bounds`**: Lectura automática de bounding box y dimensiones reales de cualquier DXF.
    - **`dxf_align`**: Sistema de alineación relacional (ej: "alinear derecha de B con derecha de A") sin cálculos manuales.
    - **`dxf_center`**: Centrado automático de piezas dentro de otras o en el tablero.
    - **`dxf_snap`**: Capacidad de referenciar puntos clave (vértices, centros) para ensambles precisos.
6.  **Soberanía de Datos y LLM Local:**
    - Integración con **Ollama** o **LocalAI** para ejecutar el cerebro del agente en local (ej: Llama 3 o Mistral).
    - Configuración de `OPENAI_API_URL` para apuntar a un servicio local, permitiendo el funcionamiento 100% offline.
7.  **Módulo de Carpintería CNC Profesional:**
    - **Uniones Paramétricas:** Generación de encajes (*finger joints*, caja y espiga, *tab-slot*) directamente en la geometría.
    - **Compensación de Radio (Dogbones):** Inserción automática de "huesos de perro" en esquinas interiores para permitir el encaje perfecto de piezas rectangulares con fresas cilíndricas.
    - **Generador de Ensamblajes Paramétricos:** Capacidad de pedir estructuras completas (ej: "hazme una caja de 400x300x250 en tablero de 18mm") y que el sistema genere automáticamente todas las piezas planas necesarias (base, laterales, etc.) con sus uniones correspondientes listas para el nesting.
    - **Parámetros Técnicos:** Configuración de tolerancias de ajuste, espesor de material y diámetro de fresa integrados en el diseño.
    - **Evolución del Boolean:** Mejora del motor para preservar arcos reales (no segmentados) en operaciones de unión/resta de piezas complejas.

---

## 🌟 Largo Plazo (Visión)
1.  **Simulación 3D de Toolpath:**
    - Renderizado en el navegador de la trayectoria exacta de la herramienta con detección de colisiones.
2.  **Asistente IA de Taller:**
    - Capacidad de diagnóstico de errores basado en logs de LinuxCNC usando LLMs.
    - Recomendación automática de parámetros de corte basada en sensores (vibración, temperatura si están disponibles).
3.  **Multi-máquina:**
    - Soporte para gestionar varias máquinas CNC desde un mismo orquestador.
4.  **Seguridad y Auditoría:**
    - Sistema de permisos para evitar operaciones peligrosas sin supervisión física (Dead man's switch digital).

---

## 📝 Notas de Diseño
- Mantener la **independencia de microservicios** para facilitar el despliegue en diferentes nodos (NAS, RPi, PC Control).
- Priorizar la **seguridad operativa**: Siempre requerir confirmación explícita para movimientos físicos.
