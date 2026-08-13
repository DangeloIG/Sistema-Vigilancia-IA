// Referencias a los elementos del DOM
const videoPanel = document.getElementById('main-camera');
const alertsLog = document.getElementById('alerts-log');

// Función principal para registrar una amenaza y cambiar la interfaz
function registrarAlerta(tipo, amenaza, identidad, hora) {
    // 1. Crear la nueva tarjeta de alerta
    const nuevaAlerta = document.createElement('div');
    nuevaAlerta.className = `alert-card ${tipo}`; // 'precaucion', 'media', 'critica'
    
    nuevaAlerta.innerHTML = `
        <strong>${amenaza} Detectada</strong>
        <span>Sujeto: ${identidad}</span>
        <small style="color: #888; margin-top: 5px;">${hora}</small>
    `;
    
    // Añadirla al principio de la lista
    alertsLog.prepend(nuevaAlerta);

    // 2. Cambiar el borde del video según el peligro
    videoPanel.className = 'video-feed'; // Resetear clases
    
    if (tipo === 'media') {
        videoPanel.classList.add('alerta-media');
    } else if (tipo === 'critica') {
        videoPanel.classList.add('alerta-critica');
    }

    // Si es crítico, hacer que vuelva a la normalidad después de unos segundos
    // (Esto se ajustará cuando conectemos Python)
    setTimeout(() => {
        videoPanel.className = 'video-feed';
    }, 5000);
}

// Ejemplo: Descomenta la siguiente línea para ver cómo se vería un arma de fuego
// registrarAlerta('critica', 'Arma de Fuego', 'Desconocido', '14:35:22');