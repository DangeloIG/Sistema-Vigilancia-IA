// ==========================================
// MÓDULO DE AUTENTICACIÓN Y ROLES (RF6)
// ==========================================
let usuarioActual = "";
let rolActual = "";

async function iniciarSesion() {
    const user = document.getElementById('login-user').value;
    const pass = document.getElementById('login-pass').value;
    const errorMsg = document.getElementById('login-error');

    // Preparamos los datos del formulario para enviarlos a FastAPI
    const formData = new FormData();
    formData.append("username", user);
    formData.append("password", pass);

    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok && data.status === "ok") {
            rolActual = data.usuario.rol;
            usuarioActual = data.usuario.nombre;

            // Configurar interfaz según el rol obtenido de la BD
            document.getElementById('nombre-usuario').innerText = usuarioActual;
            document.getElementById('rol-usuario').innerText = `Rol: ${rolActual}`;
            
            if (rolActual === 'Trabajador') {
                document.getElementById('btn-vecinos').classList.add('oculto');
                document.getElementById('btn-config').classList.add('oculto');
            } else {
                document.getElementById('btn-vecinos').classList.remove('oculto');
                document.getElementById('btn-config').classList.remove('oculto');
            }

            // Ocultar login
            document.getElementById('pantalla-login').classList.add('oculto');
            errorMsg.classList.add('oculto');
            document.getElementById('login-user').value = '';
            document.getElementById('login-pass').value = '';
        } else {
            errorMsg.classList.remove('oculto');
        }
    } catch (error) {
        console.error("Error de conexión con el servidor:", error);
        errorMsg.innerText = "Error de conexión con el servidor.";
        errorMsg.classList.remove('oculto');
    }
}

function cerrarSesion() {
    usuarioActual = "";
    rolActual = "";
    document.getElementById('pantalla-login').classList.remove('oculto');
    
    // Simular clic en la pestaña de cámaras por defecto usando el ID
    const btnCamaras = document.querySelector('[onclick="cambiarVista(\'vista-camaras\', this)"]');
    cambiarVista('vista-camaras', btnCamaras); 
}

function cambiarVista(idVista, botonElement) {
    // 1. Ocultar todos los paneles
    const paneles = document.querySelectorAll('.vista-panel');
    paneles.forEach(panel => panel.classList.add('oculto'));

    // 2. Mostrar el solicitado
    document.getElementById(idVista).classList.remove('oculto');

    // 3. Resetear estilos de todos los botones si se pasó un elemento
    if(botonElement) {
        const botones = document.querySelectorAll('.tab-btn');
        botones.forEach(btn => {
            btn.classList.remove('bg-blue-600', 'text-white', 'shadow-lg', 'shadow-blue-500/30');
            btn.classList.add('text-gray-400');
        });

        // 4. Activar estilo en el botón clickeado
        botonElement.classList.remove('text-gray-400');
        botonElement.classList.add('bg-blue-600', 'text-white', 'shadow-lg', 'shadow-blue-500/30');
    }

    // Si entramos a la vista de historial, cargamos los datos de SQLite
    if (idVista === 'vista-historial') {
        cargarHistorial();
    }
}

// ==========================================
// MÓDULO DE ALERTAS Y ACCIONES DEL VIGILANTE
// ==========================================
const videoPanel = document.getElementById('main-camera');
const alertsLog = document.getElementById('alerts-log');

// Escuchar a Python (FastAPI)
const ws = new WebSocket("ws://localhost:8000/ws/alertas");

ws.onmessage = function(event) {
    const alerta = JSON.parse(event.data);
    registrarAlerta(alerta.tipo, alerta.amenaza, alerta.identidad, alerta.hora);
};

function registrarAlerta(tipo, amenaza, identidad, hora) {
    const nuevaAlerta = document.createElement('div');
    
    let colorBorde = 'border-yellow-500';
    let colorTexto = 'text-yellow-400';
    let icono = 'fa-triangle-exclamation';

    if (tipo === 'critica') {
        colorBorde = 'border-red-500';
        colorTexto = 'text-red-500';
        icono = 'fa-skull-crossbones';
    }

    // RF11: Se agregan botones para que el guardia atienda la alerta
    nuevaAlerta.className = `bg-gray-700 border-l-4 ${colorBorde} p-4 rounded-r shadow-lg transform transition-all`;
    nuevaAlerta.innerHTML = `
        <div class="flex justify-between items-start mb-2">
            <strong class="${colorTexto} text-sm uppercase font-bold"><i class="fa-solid ${icono} mr-1"></i> ${amenaza}</strong>
            <span class="text-xs bg-gray-800 px-2 py-1 rounded text-gray-400">${hora}</span>
        </div>
        <div class="text-xs text-gray-300 mb-3">
            Sujeto: <span class="font-bold text-white">${identidad}</span>
        </div>
        <div class="flex space-x-2 border-t border-gray-600 pt-2 mt-2">
            <button onclick="atenderAlerta(this, 'Confirmado')" class="flex-1 bg-red-600 hover:bg-red-500 text-white text-xs font-bold py-1.5 rounded transition">Confirmar</button>
            <button onclick="atenderAlerta(this, 'Falsa Alarma')" class="flex-1 bg-gray-600 hover:bg-gray-500 text-white text-xs font-bold py-1.5 rounded transition">Descartar</button>
        </div>
    `;
    
    alertsLog.prepend(nuevaAlerta);

    // Efectos de borde en el video
    videoPanel.classList.remove('border-gray-800', 'alerta-media', 'alerta-critica');
    if (tipo === 'media') videoPanel.classList.add('alerta-media');
    else if (tipo === 'critica') videoPanel.classList.add('alerta-critica');

    setTimeout(() => {
        videoPanel.classList.remove('alerta-media', 'alerta-critica');
        videoPanel.classList.add('border-gray-800');
    }, 5000);
}

// RF12: Registrar la acción tomada por el usuario
async function atenderAlerta(botonClickeado, accion) {
    const tarjeta = botonClickeado.closest('div.bg-gray-700');
    // Extraemos la hora exacta de la tarjeta visual
    const horaText = tarjeta.querySelector('span.text-xs.bg-gray-800').innerText;

    // Preparamos los datos
    const formData = new FormData();
    formData.append("hora", horaText);
    formData.append("estado", accion);
    formData.append("guardia", usuarioActual); // Usamos la variable global de tu login

    try {
        // Enviamos a Python
        await fetch('/api/atender_alerta', {
            method: 'POST',
            body: formData
        });
    } catch(e) {
        console.error("Error al atender alerta:", e);
    }

    // Animación de salida y actualización de tabla
    tarjeta.style.opacity = '0';
    setTimeout(() => {
        tarjeta.remove();
        // Si el panel de historial está abierto, lo recargamos para ver el cambio al instante
        if(!document.getElementById('vista-historial').classList.contains('oculto')) {
            cargarHistorial(); 
        }
    }, 300);
}

async function registrarNuevoGuardia() {
    const user = document.getElementById('nuevo-user').value;
    const pass = document.getElementById('nuevo-pass').value;
    const nombre = document.getElementById('nuevo-nombre').value;
    const rol = document.getElementById('nuevo-rol').value; // <-- Capturamos el rol

    if(!user || !pass || !nombre) {
        alert("⚠️ Por favor, completa todos los campos.");
        return;
    }

    const formData = new FormData();
    formData.append("username", user);
    formData.append("password", pass);
    formData.append("nombre", nombre);
    formData.append("rol", rol); // <-- Enviamos el rol a Python

    try {
        const response = await fetch('/api/registrar_guardia', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            alert("✅ " + data.mensaje);
            // Limpiamos todo
            document.getElementById('nuevo-user').value = "";
            document.getElementById('nuevo-pass').value = "";
            document.getElementById('nuevo-nombre').value = "";
            document.getElementById('nuevo-rol').value = "Trabajador"; 
        } else {
            alert("❌ Error: " + data.mensaje);
        }
    } catch (error) {
        console.error("Error:", error);
        alert("Error de conexión con el servidor.");
    }
}

async function cargarHistorial() {
    try {
        const response = await fetch('/api/historial');
        const data = await response.json();
        
        if (data.status === 'ok') {
            const tbody = document.getElementById('tabla-historial');
            tbody.innerHTML = ''; // Borra los datos falsos del HTML
            
            data.datos.forEach(registro => {
                // Adaptamos las variables según los nombres en tu BD
                const fecha = registro.fecha || registro.timestamp || 'Sin fecha';
                const amenaza = registro.amenaza || registro.tipo || 'Desconocida';
                const sujeto = registro.sujeto || registro.identidad || 'Desconocido';
                const estado = registro.estado || 'Pendiente';
                const guardia = registro.atendido_por || 'N/A';
                
                let colorAmenaza = amenaza.toLowerCase().includes('fuego') ? 'text-red-400 font-bold' : 'text-yellow-400 font-bold';
                let badgeEstado = estado === 'Pendiente' 
                    ? '<span class="bg-yellow-900/50 text-yellow-400 px-2 py-1 rounded text-xs">Pendiente</span>'
                    : `<span class="bg-green-900/50 text-green-400 px-2 py-1 rounded text-xs">${estado}</span>`;

                const fila = `
                    <tr class="border-b border-gray-700 hover:bg-gray-700/50 transition">
                        <td class="p-3 text-xs">${fecha}</td>
                        <td class="p-3 ${colorAmenaza}">${amenaza}</td>
                        <td class="p-3">${sujeto}</td>
                        <td class="p-3">${badgeEstado}</td>
                        <td class="p-3 text-gray-400 text-xs">${guardia}</td>
                    </tr>
                `;
                tbody.insertAdjacentHTML('beforeend', fila);
            });
        }
    } catch (error) {
        console.error("Error cargando historial:", error);
    }
}

async function registrarVecino() {
    const nombre = document.getElementById('vecino-nombre').value;
    const inputFotos = document.getElementById('vecino-fotos');

    if (!nombre || inputFotos.files.length === 0) {
        alert("⚠️ Ingresa el nombre y selecciona al menos una foto.");
        return;
    }

    const formData = new FormData();
    formData.append("nombre", nombre);
    for (let i = 0; i < inputFotos.files.length; i++) {
        formData.append("fotos", inputFotos.files[i]);
    }

    try {
        const response = await fetch('/api/registrar_vecino', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();

        if (response.ok) {
            alert("✅ " + data.mensaje);
            document.getElementById('vecino-nombre').value = '';
            inputFotos.value = '';
        } else {
            alert("❌ Error: " + data.mensaje);
        }
    } catch (e) {
        console.error("Error al registrar vecino:", e);
    }
}