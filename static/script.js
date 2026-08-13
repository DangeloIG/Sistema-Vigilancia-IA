// ==========================================
// MÓDULO DE AUTENTICACIÓN Y ROLES (RF6)
// ==========================================
let usuarioActual = "";
let rolActual = "";

function iniciarSesion() {
    const user = document.getElementById('login-user').value.toLowerCase();
    const pass = document.getElementById('login-pass').value;
    const errorMsg = document.getElementById('login-error');

    // Validación simulada de base de datos
    if (user === 'admin' && pass === '123') {
        rolActual = 'Administrador';
        usuarioActual = 'Admin D\'Angelo';
    } else if (user === 'guardia' && pass === '123') {
        rolActual = 'Trabajador';
        usuarioActual = 'Guardia Turno 1';
    } else {
        errorMsg.classList.remove('oculto');
        return; // Detener si falla
    }

    // Configurar interfaz según el rol
    document.getElementById('nombre-usuario').innerText = usuarioActual;
    document.getElementById('rol-usuario').innerText = `Rol: ${rolActual}`;
    
    if (rolActual === 'Trabajador') {
        document.getElementById('btn-vecinos').classList.add('oculto');
        document.getElementById('btn-config').classList.add('oculto');
    } else {
        document.getElementById('btn-vecinos').classList.remove('oculto');
        document.getElementById('btn-config').classList.remove('oculto');
    }

    // Ocultar login y limpiar
    document.getElementById('pantalla-login').classList.add('oculto');
    errorMsg.classList.add('oculto');
    document.getElementById('login-user').value = '';
    document.getElementById('login-pass').value = '';
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
function atenderAlerta(botonClickeado, accion) {
    const tarjeta = botonClickeado.closest('div.bg-gray-700');
    
    // Aquí en el futuro enviaremos la confirmación a SQLite.
    // Por ahora, removemos la alerta activa de la pantalla derecha.
    tarjeta.style.opacity = '0';
    setTimeout(() => {
        tarjeta.remove();
        console.log(`El usuario ${usuarioActual} marcó la alerta como: ${accion}`);
    }, 300);
}