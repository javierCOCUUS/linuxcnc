import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader";

// --- REFERENCIAS UI ---
const estadoEl = document.getElementById("estado");
const lineaEl = document.getElementById("linea");
const xyzEl = document.getElementById("xyz");
const xyzMachEl = document.getElementById("xyzMach");
const toolEl = document.getElementById("tool");
const speedEl = document.getElementById("speed");
const speedValEl = document.getElementById("speedVal");
const originXEl = document.getElementById("originX");
const originYEl = document.getElementById("originY");
const originZEl = document.getElementById("originZ");

// --- ESCENA Y CÁMARA ---
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x10151c);

const camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 10000);
camera.position.set(1200, -1200, 800);
camera.up.set(0, 0, 1);

const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById("view"), antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.toneMapping = THREE.ReinhardToneMapping;
renderer.toneMappingExposure = 1.2;

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(200, 0, 100);
controls.enableDamping = true;
controls.dampingFactor = 0.05;
controls.update();

const isoView = {
    pos: new THREE.Vector3(1200, -1200, 800),
    target: new THREE.Vector3(200, 0, 100),
};
const topView = {
    pos: new THREE.Vector3(200, 0, 1800),
    target: new THREE.Vector3(200, 0, 0),
};

// --- LUCES Y ENTORNO MEJORADO ---
scene.add(new THREE.AmbientLight(0xffffff, 0.8));

const hemiLight = new THREE.HemisphereLight(0xffffff, 0x444444, 0.6);
hemiLight.position.set(0, 0, 500);
scene.add(hemiLight);

const sun = new THREE.DirectionalLight(0xffffff, 1.0);
sun.position.set(1000, -500, 1500);
scene.add(sun);

const rimLight = new THREE.PointLight(0x32f0f0, 1.0, 3000);
rimLight.position.set(-500, 500, 1000);
scene.add(rimLight);

const grid = new THREE.GridHelper(4000, 80, 0x335577, 0x111821);
grid.rotation.x = Math.PI / 2;
grid.position.z = -0.1; // Justo debajo del suelo
scene.add(grid);

// --- SUELO REFLECTANTE ---
const floorGeom = new THREE.PlaneGeometry(4000, 4000);
const floorMat = new THREE.MeshStandardMaterial({ 
    color: 0x0a0e14, 
    metalness: 0.7, 
    roughness: 0.2 
});
const floor = new THREE.Mesh(floorGeom, floorMat);
scene.add(floor);

scene.fog = new THREE.Fog(0x0a0e14, 2000, 8000);
scene.add(new THREE.AxesHelper(200));

// --- VARIABLES CNC PRO ---
const machine = {};
const machineBasePos = {};
const spindleTipRef = {};
const traceBias = {};

const toolOffsetsX = { 1: 0.0, 2: -163.9, 3: -329.9 };
const spindleDrop = -100.0;
const origin = { x: 0, y: 0, z: 0 };

let gSegments = [];
let segIndex = 0;
let play = false;
let segmentAccumulator = 0;
let pathObj = null;
let beamMesh = null;
let traceMode = "gcode";
let currentProg = { x: 0, y: 0, z: 0, line: 0, raw: "" };
let currentPhys = { x: 0, y: 0, z: 0 };
let currentTool = 1;

// --- NUEVO: LÓGICA DE CARGA AUTOMÁTICA ---
function encodePathPreservingSlashes(value) {
    return String(value || "")
        .replace(/^\/+/, "")
        .split("/")
        .filter(Boolean)
        .map((segment) => encodeURIComponent(segment))
        .join("/");
}

async function fetchTextFromCandidates(urls) {
    let lastError = null;

    for (const url of urls) {
        try {
            const response = await fetch(url);
            if (response.ok) return { text: await response.text(), url };
            lastError = new Error(`HTTP ${response.status} en ${url}`);
        } catch (error) {
            lastError = error;
        }
    }

    throw lastError || new Error("No se pudo cargar el recurso");
}

async function loadGcodeFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const gcodeUrl = params.get('gcodeUrl');
    const gcodeFile = params.get('gcode');
    if (!gcodeUrl && !gcodeFile) return;

    const candidates = gcodeUrl
        ? [gcodeUrl]
        : [
            `/mcp-cnc/files/${encodePathPreservingSlashes(gcodeFile)}`,
            `../mcp-cnc/files/${encodePathPreservingSlashes(gcodeFile)}`,
        ];

    const label = gcodeFile || gcodeUrl;

    setStatus(`CARGANDO G-CODE: ${label}...`);
    try {
        const { text } = await fetchTextFromCandidates(candidates);
        setSegments(parseGcode(text));
        setStatus(`VISTA: ${label}`);
    } catch (e) {
        console.error("Error cargando G-code remoto:", e);
        setStatus(`ERROR CARGANDO: ${label}`, true);
    }
}

// --- FUNCIONES BÁSICAS ---
function setStatus(msg, isError = false) {
    if(!estadoEl) return;
    estadoEl.textContent = msg;
    estadoEl.style.color = isError ? "#ff6b6b" : "#43d654";
}

function addOrigin(p) { return { x: p.x + origin.x, y: p.y + origin.y, z: p.z + origin.z }; }
function physFromProg(p, tool) { return { x: p.x + (toolOffsetsX[tool] ?? 0), y: p.y, z: p.z }; }

function materialFor(name) {
    const colors = { 
        base: 0x2a2a2a, 
        portico_x: 0x1a3a5a, 
        portico_y: 0x1a4a2a, 
        portico_z: 0x5a1a1a, 
        spindle_1: 0xffd700, 
        spindle_2: 0xff8c00, 
        spindle_3: 0xff4500 
    };
    return new THREE.MeshStandardMaterial({ 
        color: colors[name] || 0x888888, 
        metalness: 0.4, 
        roughness: 0.3,
        envMapIntensity: 1.0
    });
}

// --- CARGA DE MÁQUINA (AUTOMÁTICA) ---
async function loadStlMesh(name, relPath) {
    try {
        const geom = await new STLLoader().loadAsync(relPath);
        geom.computeVertexNormals();
        const mesh = new THREE.Mesh(geom, materialFor(name));
        scene.add(mesh);
        machine[name] = mesh;
        machineBasePos[name] = mesh.position.clone();
        
        if (name.startsWith("spindle_")) {
            geom.computeBoundingBox();
            const b = geom.boundingBox;
            spindleTipRef[name] = { x: 0.5 * (b.min.x + b.max.x), y: 0.5 * (b.min.y + b.max.y), z: b.min.z };
        }
        return true;
    } catch (e) {
        console.error("Fallo cargando", relPath, e);
        return false;
    }
}

async function loadMachine() {
    const ok = await Promise.all([
        loadStlMesh("base", "./simulador/base.stl"),
        loadStlMesh("portico_x", "./simulador/portico_x.stl"),
        loadStlMesh("portico_y", "./simulador/portico_y.stl"),
        loadStlMesh("portico_z", "./simulador/portico_z.stl"),
        loadStlMesh("spindle_1", "./simulador/spindle_1.stl"),
        loadStlMesh("spindle_2", "./simulador/spindle_2.stl"),
        loadStlMesh("spindle_3", "./simulador/spindle_3.stl"),
    ]);

    if (!ok.some(Boolean)) setStatus("ESTADO: ERROR CARGANDO STL MÁQUINA", true);
    else setStatus(play ? "ESTADO: EJECUTANDO" : "ESTADO: PARADO");

    for (const t of [1, 2, 3]) {
        const key = `spindle_${t}`;
        if (machineBasePos[key] && spindleTipRef[key]) {
            traceBias[t] = { 
                x: machineBasePos[key].x + spindleTipRef[key].x, 
                y: machineBasePos[key].y + spindleTipRef[key].y, 
                z: machineBasePos[key].z + spindleTipRef[key].z 
            };
        }
    }

    buildPath();
    updateMachine(currentPhys, currentTool);
}

// --- G-CODE PARSER ---
function stripComments(line) {
    let s = line.replace(/\([^)]*\)/g, "");
    const semicolon = s.indexOf(";");
    if (semicolon >= 0) s = s.slice(0, semicolon);
    return s.trim();
}

function parseWords(line) {
    const out = [];
    const re = /([A-Z])\s*([-+]?\d*\.?\d+)/gi;
    let m; while ((m = re.exec(line)) !== null) out.push({ k: m[1].toUpperCase(), v: parseFloat(m[2]) });
    return out;
}

function interpArc(start, end, i, j, cw, steps = 24) {
    const cx = start.x + i, cy = start.y + j;
    const r0 = Math.atan2(start.y - cy, start.x - cx);
    let r1 = Math.atan2(end.y - cy, end.x - cx);
    let sweep = r1 - r0;
    if (cw && sweep >= 0) sweep -= Math.PI * 2;
    if (!cw && sweep <= 0) sweep += Math.PI * 2;

    const pts = [], radius = Math.hypot(start.x - cx, start.y - cy);
    for (let s = 1; s <= steps; s++) {
        const t = s / steps, a = r0 + sweep * t;
        pts.push({ x: cx + Math.cos(a) * radius, y: cy + Math.sin(a) * radius, z: start.z + (end.z - start.z) * t });
    }
    return pts;
}

function parseGcode(text) {
    const lines = text.split(/\r?\n/);
    const segs = [];
    let abs = true, motion = "G0", progPos = { x: 0, y: 0, z: 0 }, tool = 1, pendingTool = null;

    for (let idx = 0; idx < lines.length; idx++) {
        const raw = lines[idx] || "";
        const clean = stripComments(raw).toUpperCase();
        if (!clean) continue;

        const words = parseWords(clean);
        if (!words.length) continue;

        let x = null, y = null, z = null, i = 0, j = 0;
        let toolOnLine = null, hasM6 = false;

        for (const w of words) {
            if (w.k === "G") {
                const gInt = Math.round(w.v);
                const isIntegerG = Math.abs(w.v - gInt) < 1e-6;
                if (isIntegerG && gInt === 90) abs = true;
                else if (isIntegerG && gInt === 91) abs = false;
                else if (isIntegerG && [0, 1, 2, 3].includes(gInt)) motion = `G${gInt}`;
            }
            if (w.k === "T") toolOnLine = Math.round(w.v);
            if (w.k === "M" && Math.round(w.v) === 6) hasM6 = true;
            if (w.k === "X") x = w.v; if (w.k === "Y") y = w.v; if (w.k === "Z") z = w.v;
            if (w.k === "I") i = w.v; if (w.k === "J") j = w.v;
        }
        
        if (toolOnLine !== null) pendingTool = toolOnLine;
        if (hasM6 && pendingTool) tool = pendingTool;

        const targetProg = {
            x: x === null ? progPos.x : (abs ? x : progPos.x + x),
            y: y === null ? progPos.y : (abs ? y : progPos.y + y),
            z: z === null ? progPos.z : (abs ? z : progPos.z + z),
        };

        if (targetProg.x === progPos.x && targetProg.y === progPos.y && targetProg.z === progPos.z) continue;

        const rapid = motion === "G0";
        if (motion === "G2" || motion === "G3") {
            const pts = interpArc(progPos, targetProg, i, j, motion === "G2", 24);
            let prevProg = { ...progPos };
            for (const p of pts) {
                segs.push({ fromProg: prevProg, toProg: p, fromPhys: physFromProg(prevProg, tool), toPhys: physFromProg(p, tool), rapid, tool, line: idx + 1, raw });
                prevProg = p;
            }
        } else {
            segs.push({ fromProg: { ...progPos }, toProg: targetProg, fromPhys: physFromProg(progPos, tool), toPhys: physFromProg(targetProg, tool), rapid, tool, line: idx + 1, raw });
        }
        progPos = targetProg;
    }
    return segs;
}

// --- DIBUJADO DE TRAYECTORIA (¡Corregido el eje Z!) ---
function buildPath() {
    if (pathObj) scene.remove(pathObj);
    const cutPts = [], rapPts = [];
    
    for (const s of gSegments) {
        let aM, bM;
        if (traceMode === "machine") {
            const bias = traceBias[s.tool] || { x: 0, y: 0, z: 0 };
            aM = addOrigin({ x: s.fromPhys.x + bias.x, y: s.fromPhys.y + bias.y, z: s.fromPhys.z + bias.z + spindleDrop });
            bM = addOrigin({ x: s.toPhys.x + bias.x, y: s.toPhys.y + bias.y, z: s.toPhys.z + bias.z + spindleDrop });
        } else {
            aM = addOrigin(s.fromProg);
            bM = addOrigin(s.toProg);
        }
        
        // CORRECCIÓN CLAVE: Ahora usa la coordenada Z real de cada punto (aM.z) en lugar de forzarla a la mesa.
        const a = new THREE.Vector3(aM.x, aM.y, aM.z);
        const b = new THREE.Vector3(bM.x, bM.y, bM.z);
        
        if (s.rapid) rapPts.push(a, b); else cutPts.push(a, b);
    }

    pathObj = new THREE.Group();
    if (rapPts.length > 1) pathObj.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(rapPts), new THREE.LineBasicMaterial({ color: 0xffaa00, transparent: true, opacity: 0.6 })));
    if (cutPts.length > 1) pathObj.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(cutPts), new THREE.LineBasicMaterial({ color: 0x00ffff })));
    scene.add(pathObj);
}

// --- ACTUALIZACIÓN DE MÁQUINA Y UI ---
function updateMachine(phys, activeTool) {
    const m = addOrigin(phys);

    if (machine.portico_y && machineBasePos.portico_y) machine.portico_y.position.set(machineBasePos.portico_y.x, machineBasePos.portico_y.y + m.y, machineBasePos.portico_y.z);
    if (machine.portico_x && machineBasePos.portico_x) machine.portico_x.position.set(machineBasePos.portico_x.x + m.x, machineBasePos.portico_x.y + m.y, machineBasePos.portico_x.z);
    if (machine.portico_z && machineBasePos.portico_z) machine.portico_z.position.set(machineBasePos.portico_z.x + m.x, machineBasePos.portico_z.y + m.y, machineBasePos.portico_z.z + m.z);

    for (let t = 1; t <= 3; t++) {
        const key = `spindle_${t}`;
        if (machine[key] && machineBasePos[key]) {
            const drop = activeTool === t ? spindleDrop : 0;
            machine[key].position.set(machineBasePos[key].x + m.x, machineBasePos[key].y + m.y, machineBasePos[key].z + m.z + drop);
        }
    }
}

function updateHud() {
    const m = addOrigin(currentPhys);
    if (estadoEl && !estadoEl.textContent.startsWith("ESTADO: ERROR")) setStatus(play ? "ESTADO: EJECUTANDO" : "ESTADO: PARADO");
    if (lineaEl) lineaEl.textContent = `Línea: ${currentProg.line || "-"}`;
    if (xyzEl) xyzEl.textContent = `XYZ prog: ${currentProg.x.toFixed(2)}, ${currentProg.y.toFixed(2)}, ${currentProg.z.toFixed(2)}`;
    if (xyzMachEl) xyzMachEl.textContent = `XYZ maq: ${m.x.toFixed(2)}, ${m.y.toFixed(2)}, ${m.z.toFixed(2)}`;
    if (toolEl) toolEl.textContent = `T: ${currentTool}`;
}

// --- CONTROLES DE REPRODUCCIÓN ---
function stepOnce() {
    if (segIndex >= gSegments.length) { play = false; return; }
    const s = gSegments[segIndex];
    currentProg = { x: s.toProg.x, y: s.toProg.y, z: s.toProg.z, line: s.line, raw: s.raw };
    currentPhys = { ...s.toPhys };
    currentTool = s.tool;
    updateMachine(currentPhys, currentTool);
    segIndex++;
    updateHud();
}

function resetPlayback() {
    segIndex = 0; segmentAccumulator = 0; play = false;
    currentProg = { x: 0, y: 0, z: 0, line: 0, raw: "" };
    currentTool = 1; currentPhys = physFromProg(currentProg, currentTool);
    updateMachine(currentPhys, currentTool);
    updateHud();
}

function setSegments(segs) {
    gSegments = segs;
    buildPath();
    resetPlayback();
}

// --- ORIGEN (¡Corregido!) ---
function applyOriginFromInputs() {
    origin.x = Number(originXEl?.value) || 0;
    origin.y = Number(originYEl?.value) || 0;
    origin.z = Number(originZEl?.value) || 0;
    
    // Al aplicar el origen, reconstruimos la línea del G-Code
    buildPath();
    
    // Y movemos la viga al origen SIN sumarle la altura de la mesa
    if(beamMesh) beamMesh.position.set(origin.x, origin.y, origin.z);
    
    updateMachine(currentPhys, currentTool);
    updateHud();
}

// --- EVENTOS DEL DOM ---
const safeAddListener = (id, event, handler) => { const el = document.getElementById(id); if (el) el.addEventListener(event, handler); };

safeAddListener("btnPlay", "click", () => { play = true; updateHud(); });
safeAddListener("btnPause", "click", () => { play = false; updateHud(); });
safeAddListener("btnStep", "click", () => stepOnce());
safeAddListener("btnReset", "click", () => resetPlayback());
safeAddListener("btnTraceMode", "click", (e) => {
    traceMode = traceMode === "gcode" ? "machine" : "gcode";
    e.currentTarget.textContent = traceMode === "gcode" ? "Traza: GCode" : "Traza: Máquina";
    buildPath();
});
safeAddListener("btnViewIso", "click", () => { camera.position.copy(isoView.pos); camera.up.set(0, 0, 1); controls.target.copy(isoView.target); controls.update(); });
safeAddListener("btnViewTop", "click", () => { camera.position.copy(topView.pos); camera.up.set(0, 1, 0); controls.target.copy(topView.target); controls.update(); });
safeAddListener("btnOriginApply", "click", applyOriginFromInputs);
safeAddListener("btnOriginZero", "click", () => { if(originXEl) originXEl.value="0"; if(originYEl) originYEl.value="0"; if(originZEl) originZEl.value="0"; applyOriginFromInputs(); });

if (speedEl && speedValEl) speedEl.addEventListener("input", () => { speedValEl.textContent = `${speedEl.value} seg/s`; });

safeAddListener("fileInput", "change", async (e) => {
    const f = e.target.files?.[0]; if (!f) return;
    setSegments(parseGcode(await f.text()));
});

safeAddListener("btnEjemplo", "click", async () => {
    setStatus("CARGANDO EJEMPLO...");
    try {
        const { text } = await fetchTextFromCandidates(["./simulador/prueba.gcode"]);
        setSegments(parseGcode(text));
        setStatus("ESTADO: EJEMPLO CARGADO");
    } catch (error) {
        console.error("Error cargando ejemplo:", error);
        setStatus("ERROR CARGANDO EJEMPLO", true);
    }
});

// NUEVO: CARGAR LA VIGA DE GRASSHOPPER (¡Corregido el Z!)
safeAddListener("beamInput", "change", async (e) => {
    const f = e.target.files?.[0]; if (!f) return;
    const geom = new STLLoader().parse(await f.arrayBuffer());
    if (beamMesh) scene.remove(beamMesh);
    beamMesh = new THREE.Mesh(geom, new THREE.MeshStandardMaterial({ color: 0xdeb887, roughness: 0.8 }));
    
    // La colocamos directamente en el origen de la máquina (0,0,0) o lo que marque el input
    beamMesh.position.set(origin.x, origin.y, origin.z); 
    
    scene.add(beamMesh);
    setStatus("ESTADO: VIGA CARGADA");
});

window.addEventListener("keydown", (e) => {
    if (e.key.toLowerCase() === "p") { play = !play; updateHud(); }
    else if (e.key.toLowerCase() === "n") stepOnce();
});

window.addEventListener("resize", () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});

// --- RENDER LOOP ---
const clock = new THREE.Clock();
function tick() {
    const dt = clock.getDelta();
    if (play && gSegments.length > 0) {
        segmentAccumulator += dt * (speedEl ? Number(speedEl.value) : 60);
        while (segmentAccumulator >= 1) { stepOnce(); segmentAccumulator -= 1; if (!play) break; }
    }
    controls.update();
    renderer.render(scene, camera);
    requestAnimationFrame(tick);
}

// INICIALIZACIÓN
loadMachine().then(() => {
    loadGcodeFromUrl();
});
updateHud();
tick();