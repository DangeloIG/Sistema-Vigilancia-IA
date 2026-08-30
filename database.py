import sqlite3
import bcrypt
from datetime import datetime
import os

# Nombre del archivo de la base de datos local
DB_NAME = "seguridad.db"

def get_db_connection():
    """Establece y retorna la conexión a la base de datos SQLite"""
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row # Permite acceder a las columnas por su nombre
    return conn

def init_db():
    """Inicializa las tablas y crea los usuarios por defecto si no existen"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Tabla de Usuarios (Cumple RF6 y Seguridad)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nombre_completo TEXT NOT NULL,
            rol TEXT NOT NULL
        )
    ''')
    
    # 2. Tabla de Historial (Cumple RF9 y RF10)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historial_alertas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            hora TEXT NOT NULL,
            camara TEXT NOT NULL,
            tipo_amenaza TEXT NOT NULL,
            sujeto TEXT NOT NULL,
            accion TEXT,
            ruta_imagen TEXT
        )
    ''')
    
    # 3. Inyección segura de usuarios iniciales (Evita texto plano)
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        print("Generando base de datos y encriptando credenciales por primera vez...")
        
        # Encriptamos la contraseña "123" para las pruebas iniciales
        salt = bcrypt.gensalt()
        hash_pass = bcrypt.hashpw("123".encode('utf-8'), salt).decode('utf-8')
        
        # Insertamos Administrador
        cursor.execute("INSERT INTO usuarios (username, password_hash, nombre_completo, rol) VALUES (?, ?, ?, ?)",
                       ("admin", hash_pass, "D'Angelo (Admin)", "Administrador"))
        # Insertamos Guardia
        cursor.execute("INSERT INTO usuarios (username, password_hash, nombre_completo, rol) VALUES (?, ?, ?, ?)",
                       ("guardia", hash_pass, "Guardia Turno 1", "Trabajador"))
        
    conn.commit()
    conn.close()
    print("Base de datos conectada y operativa.")

def verificar_usuario(username, password_intento):
    """Verifica si el usuario existe y si la contraseña coincide con el Hash"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Buscamos al usuario de forma segura (Previene SQL Injection)
    cursor.execute("SELECT * FROM usuarios WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    
    # Verificamos la contraseña encriptada
    if user and bcrypt.checkpw(password_intento.encode('utf-8'), user['password_hash'].encode('utf-8')):
        return {
            "exito": True, 
            "username": user['username'], 
            "nombre": user['nombre_completo'], 
            "rol": user['rol']
        }
    return {"exito": False}

def guardar_alerta_bd(camara, tipo_amenaza, sujeto, ruta_imagen):
    """Guarda el evento de amenaza en el historial"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    fecha = datetime.now().strftime('%Y-%m-%d')
    hora = datetime.now().strftime('%H:%M:%S')
    
    cursor.execute('''
        INSERT INTO historial_alertas (fecha, hora, camara, tipo_amenaza, sujeto, accion, ruta_imagen)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (fecha, hora, camara, tipo_amenaza, sujeto, "Pendiente de revisión", ruta_imagen))
    
    conn.commit()
    conn.close()

def registrar_usuario(username, password, nombre, rol="Guardia"):
    try:
        conn = sqlite3.connect("seguridad.db")
        cursor = conn.cursor()
        
        # Encriptar la contraseña (hash)
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        
        # Insertar en la tabla usuarios
        cursor.execute("""
            INSERT INTO usuarios (username, password_hash, nombre_completo, rol)
            VALUES (?, ?, ?, ?)
        """, (username, password_hash, nombre, rol))
        
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False # El usuario ya existe
    except Exception as e:
        print(f"Error al registrar usuario en BD: {e}")
        return False

# --- 5. MOTOR DE INTELIGENCIA ARTIFICIAL (HILO EN SEGUNDO PLANO) ---
def procesar_camara():
    global output_frame, lock, alertas_recientes
    
    usuario = "admin"
    password = "admin2021"  
    ip_dvr = "192.168.1.39"              
    canal = "4"                      
    ruta_camara = f"rtsp://{usuario}:{password}@{ip_dvr}:554/cam/realmonitor?channel={canal}&subtype=0"
    
    cap = cv2.VideoCapture(ruta_camara)
    # Reducimos el buffer a 1 para evitar retrasos (lag) en la transmisión en vivo
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) 
    
    frame_count = 0
    ultima_alerta = 0
    
    while True:
        # Sistema de reconexión automática anti-crasheos
        if not cap.isOpened():
            print("⚠️ Conexión perdida con el DVR. Reconectando...")
            cap = cv2.VideoCapture(ruta_camara)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            time.sleep(2)
            continue
            
        ret, frame = cap.read()
        
        if not ret:
            print("⚠️ Trama de video vacía o timeout. Reiniciando stream...")
            cap.release() # Liberar y forzar al loop a reconectar
            continue
            
        frame_count += 1
        frame = cv2.resize(frame, (800, 450))
        frame_renderizado = frame.copy()
        
        # AUMENTO DE FLUIDEZ: Procesar 1 de cada 3 fotogramas (en vez de 10)
        if frame_count % 3 == 0:
            
            # A) DETECCIÓN DE ARMAS
            res_armas = model_armas(frame, size=640, augment=False)
            det_armas = res_armas.pandas().xyxy[0] 
            
            hay_fuego, hay_blanca = False, False
            cajas_dibujo = []
            
            for index, row in det_armas.iterrows():
                if row['confidence'] >= 0.40:
                    label = row['name']
                    if label == 'pistol': hay_fuego = True
                    if label == 'knife': hay_blanca = True
                    cajas_dibujo.append((int(row['xmin']), int(row['ymin']), int(row['xmax']), int(row['ymax']), label, row['confidence']))
            
            # B) DETECCIÓN Y RECONOCIMIENTO FACIAL
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res_caras = model_caras(frame, conf=0.30, verbose=False)
            
            identidad_global = "Desconocido"
            
            for box in res_caras[0].boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                face_encodings = face_recognition.face_encodings(rgb_frame, [(y1, x2, y2, x1)])
                
                nombre = "Desconocido"
                color_cara = (0, 0, 255) # Rojo
                
                if face_encodings:
                    matches = face_recognition.compare_faces(vecinos_encodings, face_encodings[0], tolerance=0.5)
                    if True in matches:
                        nombre = "Vecino"
                        identidad_global = "Vecino"
                        color_cara = (0, 255, 0) # Verde
                
                cv2.rectangle(frame_renderizado, (x1, y1), (x2, y2), color_cara, 2)
                cv2.putText(frame_renderizado, nombre, (x1, max(y1 - 10, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_cara, 2)
            
            # C) GESTIÓN DE ALERTAS 
            if (hay_fuego or hay_blanca) and (time.time() - ultima_alerta > 15):
                tipo_alerta = "critica" if hay_fuego else "media"
                amenaza = "Arma de Fuego" if hay_fuego else "Arma Blanca"
                hora = datetime.now().strftime('%H:%M:%S')
                
                if not os.path.exists("Registros_Seguridad"):
                    os.makedirs("Registros_Seguridad")
                
                nombre_foto = f"Registros_Seguridad/evidencia_{datetime.now().strftime('%H%M%S')}_{uuid.uuid4().hex[:6]}.jpg"
                cv2.imwrite(nombre_foto, frame_renderizado)
                
                guardar_alerta_bd("Cámara Principal", amenaza, identidad_global, nombre_foto)
                
                alertas_recientes.append({
                    "tipo": tipo_alerta, 
                    "amenaza": amenaza, 
                    "identidad": identidad_global, 
                    "hora": hora
                })
                
                if hay_fuego:
                    mensaje_ws = f"🚨 SOC ALERTA DE SEGURIDAD: {amenaza} detectada a las {hora}. Sujeto: {identidad_global}. Por favor, precaución en el acceso perimetral."
                    hilo_wp = threading.Thread(target=enviar_alerta_grupo, args=(mensaje_ws,))
                    hilo_wp.start()
                    
                ultima_alerta = time.time()
                
            # D) DIBUJAR CAJAS DE ARMAS CON PORCENTAJES
            for (x1, y1, x2, y2, label, conf) in cajas_dibujo:
                color_arma = (0, 165, 255)
                cv2.rectangle(frame_renderizado, (x1, y1), (x2, y2), color_arma, 3)
                texto = "Pistola" if label == 'pistol' else "Cuchillo"
                cv2.putText(frame_renderizado, f"{texto} {conf*100:.0f}%", (x1, max(y1 - 10, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_arma, 2)
                
        # Actualizamos el frame global
        with lock:
            output_frame = frame_renderizado.copy()

def obtener_historial():
    import sqlite3
    try:
        conn = sqlite3.connect("seguridad.db")
        cursor = conn.cursor()
        
        # Asumimos que tu tabla se llama "historial_alertas"
        cursor.execute("SELECT * FROM historial_alertas ORDER BY id DESC LIMIT 50")
        
        # Extraer los nombres de las columnas automáticamente
        columnas = [desc[0] for desc in cursor.description]
        filas = cursor.fetchall()
        conn.close()
        
        # Convertir las filas en diccionarios para enviarlos al Frontend
        resultados = []
        for fila in filas:
            resultados.append(dict(zip(columnas, fila)))
        return resultados
    except Exception as e:
        print(f"Error al obtener historial: {e}")
        return []

def actualizar_estado_alerta(hora, estado, guardia):
    import sqlite3
    try:
        conn = sqlite3.connect("seguridad.db")
        cursor = conn.cursor()
        
        # Asumimos que tus columnas se llaman estado, atendido_por y hora
        cursor.execute("""
            UPDATE historial_alertas 
            SET estado = ?, atendido_por = ? 
            WHERE hora = ?
        """, (estado, guardia, hora))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error actualizando estado de alerta: {e}")
        return False
    
# Si ejecutas este archivo directamente, se inicializará la base de datos
if __name__ == "__main__":
    init_db()