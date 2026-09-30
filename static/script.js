let usuarioActual = "";
let rolActual = "";
const audioCtx = new (window.AudioContext || window.webkitAudioContext)(); 

async function iniciarSesion() {
    const user = document.getElementById('login-user').value;
    const pass = document.getElementById('login-pass').value;
    const errorMsg = document.getElementById('login-error');

    const formData = new FormData();
    formData.append("username", user);
    formData.append("password", pass);

    try {
        const response = await fetch('/api/login', { method: 'POST', body: formData });
        const data = await response.json();

        if (response.ok && data.status === "ok") {
            rolActual = data.usuario.rol;
            usuarioActual = data.usuario.nombre;
            localStorage.setItem('nombreGuardia', usuarioActual);

            document.getElementById('nombre-usuario').innerText = usuarioActual;
            document.getElementById('rol-usuario').innerText = `Rol: ${rolActual}`;
            
            if (rolActual === 'Trabajador') {
                document.getElementById('btn-vecinos').classList.add('oculto');
                document.getElementById('btn-config').classList.add('oculto');
            } else {
                document.getElementById('btn-vecinos').classList.remove('oculto');
                document.getElementById('btn-config').classList.remove('oculto');
            }

            document.getElementById('pantalla-login').classList.add('oculto');
            errorMsg.classList.add('oculto');
            document.getElementById('login-user').value = '';
            document.getElementById('login-pass').value = '';
            
            if (audioCtx.state === 'suspended') audioCtx.resume();
        } else {
            errorMsg.classList.remove('oculto');
        }
    } catch (error) {
        errorMsg.classList.remove('oculto');
    }
}

function cerrarSesion() {
    usuarioActual = "";
    rolActual = "";
    localStorage.removeItem('nombreGuardia');
    document.getElementById('pantalla-login').classList.remove('oculto');
    const btnCamaras = document.querySelector('[onclick="cambiarVista(\'vista-camaras\', this)"]');
    cambiarVista('vista-camaras', btnCamaras); 
}

function cambiarVista(idVista, botonElement) {
    const paneles = document.querySelectorAll('.vista-panel');
    paneles.forEach(panel => panel.classList.add('oculto'));
    document.getElementById(idVista).classList.remove('oculto');

    if(botonElement) {
        const botones = document.querySelectorAll('.tab-btn');
        botones.forEach(btn => {
            btn.classList.remove('bg-blue-600', 'text-white', 'shadow-lg', 'shadow-blue-500/30');
            btn.classList.add('text-gray-400');
        });
        botonElement.classList.remove('text-gray-400');
        botonElement.classList.add('bg-blue-600', 'text-white', 'shadow-lg', 'shadow-blue-500/30');
    }
    
    if (idVista === 'vista-historial') cargarHistorial();
    if (idVista === 'vista-vecinos') cargarDirectorioVecinos();
}

// ==========================================
// MÓDULO DE ALERTAS, COLORES Y SONIDO
// ==========================================
const videoPanel = document.getElementById('main-camera');
const alertsLog = document.getElementById('alerts-log');
const ws = new WebSocket("ws://localhost:8000/ws/alertas");

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    actualizarBordeCamara(data.borde);
    if (data.alerta) {
        registrarAlerta(data.alerta.tipo, data.alerta.amenaza, data.alerta.identidad, data.alerta.hora);
        reproducirSonido(data.alerta.tipo);
    }
};

function actualizarBordeCamara(borde) {
    videoPanel.className = "flex-1 bg-black rounded-xl border-4 overflow-hidden relative transition-all duration-300 flex items-center justify-center";
    switch(borde) {
        case 'normal': 
            videoPanel.classList.add('border-green-500', 'shadow-[0_0_15px_#22c55e]'); break;
        case 'precaucion':  
            videoPanel.classList.add('border-yellow-500', 'shadow-[0_0_20px_#eab308]'); break;
        case 'media':       
            videoPanel.classList.add('border-orange-400', 'shadow-[0_0_25px_#fb923c]'); break;
        case 'alta':        
            videoPanel.classList.add('border-orange-600', 'shadow-[0_0_35px_#ea580c]'); break;
        case 'critica':     
            videoPanel.classList.add('border-red-600', 'shadow-[0_0_50px_#dc2626]', 'animate-pulse'); break;
    }
}

function reproducirSonido(tipo) {
    if (audioCtx.state === 'suspended') audioCtx.resume();
    if (tipo === 'media' || tipo === 'alta') {
        for(let i=0; i<4; i++) setTimeout(() => beep(600, 150, 'square', 0.1), i * 300);
    } else if (tipo === 'critica') {
        for(let i=0; i<15; i++) {
            setTimeout(() => beep(900, 400, 'sawtooth', 0.2), i * 800);
            setTimeout(() => beep(700, 400, 'sawtooth', 0.2), (i * 800) + 400);
        }
    }
}

function beep(freq, duration, type, vol) {
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = type; osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
    gain.gain.setValueAtTime(vol, audioCtx.currentTime);
    osc.connect(gain); gain.connect(audioCtx.destination);
    osc.start(); setTimeout(() => { osc.stop(); osc.disconnect(); }, duration);
}

function registrarAlerta(tipo, amenaza, identidad, hora) {
    const nuevaAlerta = document.createElement('div');
    let colorBorde = (tipo === 'critica') ? 'border-red-500' : 'border-yellow-500';
    let colorTexto = (tipo === 'critica') ? 'text-red-500' : 'text-yellow-400';
    let icono = (tipo === 'critica') ? 'fa-skull-crossbones' : 'fa-triangle-exclamation';

    nuevaAlerta.className = `bg-gray-700 border-l-4 ${colorBorde} p-4 rounded-r shadow-lg transform transition-all`;
    nuevaAlerta.innerHTML = `
        <div class="flex justify-between items-start mb-2">
            <strong class="${colorTexto} text-sm uppercase font-bold"><i class="fa-solid ${icono} mr-1"></i> ${amenaza}</strong>
            <span class="text-xs bg-gray-800 px-2 py-1 rounded text-gray-400">${hora}</span>
        </div>
        <div class="text-xs text-gray-300 mb-3">Sujeto: <span class="font-bold text-white capitalize">${identidad}</span></div>
        <div class="flex space-x-2 border-t border-gray-600 pt-2 mt-2">
            <button onclick="atenderAlerta(this, 'Confirmado')" class="flex-1 bg-red-600 hover:bg-red-500 text-white text-xs font-bold py-1.5 rounded transition">Confirmar</button>
            <button onclick="atenderAlerta(this, 'Falsa Alarma')" class="flex-1 bg-gray-600 hover:bg-gray-500 text-white text-xs font-bold py-1.5 rounded transition">Descartar</button>
        </div>
    `;
    alertsLog.prepend(nuevaAlerta);
}

async function atenderAlerta(botonClickeado, accion) {
    const tarjeta = botonClickeado.closest('div.bg-gray-700');
    const horaText = tarjeta.querySelector('span.text-xs.bg-gray-800').innerText;

    const formData = new FormData();
    formData.append("hora", horaText);
    formData.append("estado", accion);
    formData.append("guardia", localStorage.getItem('nombreGuardia') || 'Administrador'); 

    try { await fetch('/api/atender_alerta', { method: 'POST', body: formData }); } catch(e) {}

    tarjeta.style.opacity = '0';
    setTimeout(() => {
        tarjeta.remove();
        if(!document.getElementById('vista-historial').classList.contains('oculto')) cargarHistorial();
    }, 300);
}

// ==========================================
// MÓDULO DE HISTORIAL
// ==========================================
async function cargarHistorial() {
    try {
        const fechaFiltro = document.getElementById('filtro-fecha').value;
        let url = '/api/historial';
        if (fechaFiltro) url += `?fecha=${fechaFiltro}`;

        const response = await fetch(url);
        const data = await response.json();
        
        if (data.status === 'ok') {
            const tbody = document.getElementById('tabla-historial');
            tbody.innerHTML = ''; 
            
            data.datos.forEach(registro => {
                const fecha = registro.fecha_hora || 'Sin fecha';
                const amenaza = registro.amenaza || 'Desconocida';
                const sujeto = registro.sujeto || 'Desconocido';
                const estado = registro.estado || 'Pendiente';
                const guardia = registro.atendido_por || 'N/A';
                const foto = registro.foto || '';
                
                let colorAmenaza = amenaza.toLowerCase().includes('fuego') ? 'text-red-400 font-bold' : 'text-yellow-400 font-bold';
                let badgeEstado = estado === 'Pendiente' 
                    ? '<span class="bg-yellow-900/50 text-yellow-400 px-2 py-1 rounded text-xs">Pendiente</span>'
                    : `<span class="bg-green-900/50 text-green-400 px-2 py-1 rounded text-xs">${estado}</span>`;
                let linkFoto = foto ? `<a href="/${foto}" target="_blank" class="text-blue-400 hover:text-blue-300 underline"><i class="fa-solid fa-image"></i> Ver</a>` : '-';

                const fila = `
                    <tr class="border-b border-gray-700 hover:bg-gray-700/50 transition">
                        <td class="p-3 text-xs">${fecha}</td>
                        <td class="p-3 ${colorAmenaza}">${amenaza}</td>
                        <td class="p-3 capitalize">${sujeto}</td>
                        <td class="p-3">${badgeEstado}</td>
                        <td class="p-3 text-gray-400 text-xs">${guardia}</td>
                        <td class="p-3 text-xs text-center">${linkFoto}</td>
                    </tr>
                `;
                tbody.insertAdjacentHTML('beforeend', fila);
            });
        }
    } catch (error) {}
}

function exportarCSV() {
    let tabla = document.getElementById("tabla-historial");
    let filas = tabla.querySelectorAll("tr");
    let csv = ["Fecha/Hora,Amenaza,Sujeto,Estado,Atendido Por,Evidencia"];
    
    for (let i = 0; i < filas.length; i++) {
        let fila = [], cols = filas[i].querySelectorAll("td");
        if(cols.length > 0) {
            for (let j = 0; j < cols.length; j++) fila.push('"' + cols[j].innerText.trim() + '"');
            csv.push(fila.join(","));
        }
    }
    
    let csvFile = new Blob([csv.join("\n")], {type: "text/csv;charset=utf-8;"});
    let downloadLink = document.createElement("a");
    downloadLink.download = "Auditoria_Eventos_SOC.csv";
    downloadLink.href = window.URL.createObjectURL(csvFile);
    downloadLink.style.display = "none";
    document.body.appendChild(downloadLink);
    downloadLink.click();
}

// ==========================================
// CONFIGURACIÓN Y SLIDERS
// ==========================================
const sliderYolo = document.getElementById('slider-yolo');
const sliderRostros = document.getElementById('slider-rostros');
const valYolo = document.getElementById('val-yolo');
const valRostros = document.getElementById('val-rostros');

if(sliderYolo) {
    sliderYolo.addEventListener('input', (e) => { valYolo.innerText = e.target.value + '%'; });
}
if(sliderRostros) {
    sliderRostros.addEventListener('input', (e) => { valRostros.innerText = (e.target.value / 10).toFixed(1); });
}

async function guardarAjustes() {
    const confYolo = document.getElementById('slider-yolo').value / 100.0;
    const tolFacial = document.getElementById('slider-rostros').value / 10.0;
    const formData = new FormData();
    formData.append("conf_yolo", confYolo);
    formData.append("tol_facial", tolFacial);

    try {
        const res = await fetch('/api/configuracion', { method: 'POST', body: formData });
        const data = await res.json();
        if(res.ok) alert("✅ " + data.mensaje);
    } catch (e) {
        alert("❌ Error de red al guardar ajustes.");
    }
}

async function registrarNuevoGuardia() {
    const user = document.getElementById('nuevo-user').value;
    const pass = document.getElementById('nuevo-pass').value;
    const nombre = document.getElementById('nuevo-nombre').value;
    const rol = document.getElementById('nuevo-rol').value;

    if(!user || !pass || !nombre) { alert("⚠️ Completa los campos."); return; }
    const formData = new FormData();
    formData.append("username", user); formData.append("password", pass);
    formData.append("nombre", nombre); formData.append("rol", rol);

    try {
        const response = await fetch('/api/registrar_guardia', { method: 'POST', body: formData });
        const data = await response.json();
        if (response.ok) {
            alert("✅ " + data.mensaje);
            document.getElementById('nuevo-user').value = ""; document.getElementById('nuevo-pass').value = "";
            document.getElementById('nuevo-nombre').value = ""; document.getElementById('nuevo-rol').value = "Trabajador"; 
        } else alert("❌ Error: " + data.mensaje);
    } catch (error) {}
}

// ==========================================
// REGISTRO Y GESTIÓN DE VECINOS (BIOMETRÍA)
// ==========================================
async function cargarDirectorioVecinos() {
    try {
        const res = await fetch('/api/vecinos');
        const data = await res.json();
        if (res.ok) {
            const lista = document.getElementById('lista-vecinos');
            lista.innerHTML = '';
            
            if (data.vecinos.length === 0) {
                lista.innerHTML = '<p class="text-gray-500 text-sm col-span-3 text-center">No hay vecinos registrados.</p>';
                return;
            }
            
            data.vecinos.forEach(nombre => {
                lista.insertAdjacentHTML('beforeend', `
                    <div class="bg-gray-800 p-3 rounded text-center border border-gray-600 relative group">
                        <button onclick="eliminarVecino('${nombre}')" title="Eliminar residente" class="absolute top-1 right-2 text-red-500 opacity-0 group-hover:opacity-100 transition duration-300">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                        <i class="fa-solid fa-user-check text-3xl text-blue-500 mb-2"></i>
                        <p class="text-sm font-semibold capitalize">${nombre}</p>
                        <p class="text-xs text-blue-400">Registrado</p>
                    </div>
                `);
            });
        }
    } catch(e) {}
}

async function eliminarVecino(nombre) {
    if(!confirm(`¿Estás seguro de eliminar los datos biométricos de ${nombre}?`)) return;
    try {
        const res = await fetch(`/api/vecinos/${nombre}`, { method: 'DELETE' });
        const data = await res.json();
        if (res.ok) {
            alert("✅ " + data.mensaje);
            cargarDirectorioVecinos(); // Recargar la lista
        } else alert("❌ Error: " + data.mensaje);
    } catch(e) {}
}

async function registrarVecino() {
    const nombre = document.getElementById('vecino-nombre').value.trim();
    const inputFotos = document.getElementById('vecino-fotos');
    const btn = document.getElementById('btn-procesar-vecino');

    if (!nombre || inputFotos.files.length === 0) { 
        alert("⚠️ Por favor, ingrese el nombre y seleccione al menos una fotografía."); return; 
    }

    btn.disabled = true;
    btn.textContent = "Procesando...";

    const formData = new FormData();
    formData.append("nombre", nombre);
    for (let i = 0; i < inputFotos.files.length; i++) { formData.append("fotos", inputFotos.files[i]); }

    try {
        const response = await fetch('/api/registrar_vecino', { method: 'POST', body: formData });
        const data = await response.json();
        if (response.ok) {
            alert("✅ " + data.mensaje);
            document.getElementById('vecino-nombre').value = ''; 
            inputFotos.value = '';
            cargarDirectorioVecinos(); // Refrescar la tabla real
        } else {
            alert("❌ Error: " + data.mensaje);
        }
    } catch (e) {
        alert("❌ Ocurrió un error de conexión.");
    } finally {
        btn.disabled = false;
        btn.textContent = "Procesar Biometría";
    }
}