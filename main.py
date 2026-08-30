# ==========================================
# IMPORTACIONES DEL SISTEMA Y LIBRERÍAS
# ==========================================
import pathlib            # Manejo de rutas del sistema operativo
import platform           # Detecta si estás en Windows, Linux, etc.
import os                 # Crear carpetas y leer variables de entorno
import cv2                # OpenCV: Procesamiento de imágenes y video RTSP
import face_recognition   # Modelo dlib para biometría facial
import time               # Manejo de tiempos y delays
import torch              # PyTorch: Motor de ejecución de YOLO
import numpy as np        # Operaciones matemáticas (arreglos)
import threading          # Permite ejecutar la cámara y la web al mismo tiempo sin trabarse
import asyncio            # Asincronía para WebSockets
from datetime import datetime # Para estampar hora y fecha en los registros
from typing import List   # Para tipar las listas de imágenes recibidas

# Herramientas de FastAPI (Servidor Web)
from fastapi import FastAPI, Request, WebSocket, Form, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn            # Servidor que levanta FastAPI
import warnings           # Para silenciar advertencias en la terminal
from ultralytics import YOLO # Modelo YOLOv8 oficial
import pywhatkit as pwk   # Para enviar alertas automatizadas vía WhatsApp
import uuid               # Para generar códigos únicos en las fotos de evidencia

from database import verificar_usuario, guardar_alerta_bd

# ==========================================
# 1. PARCHES DE COMPATIBILIDAD (Windows)
# ==========================================
# Windows usa "WindowsPath" pero YOLO a veces busca "PosixPath". Esto lo arregla.
if platform.system() == 'Windows':
    pathlib.PosixPath = pathlib.WindowsPath

# Configuramos OpenCV para usar el protocolo TCP al leer cámaras IP (evita caídas y glitches)
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|timeout;2000"
warnings.filterwarnings("ignore")

# ==========================================
# 2. VARIABLES GLOBALES DE CONFIGURACIÓN
# ==========================================
# ID de tu Grupo de WhatsApp de la Junta Vecinal
ID_GRUPO_WHATSAPP = "I7hlxHyE98FHgatC6TfVBZ" 

app = FastAPI(title="Sistema de Vigilancia IA")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

output_frame = None       # Aquí guardaremos el fotograma actual con las cajas dibujadas
lock = threading.Lock()   # Candado de seguridad para que dos hilos no sobreescriban el fotograma a la vez
alertas_recientes = []    # Lista que almacena alertas para enviarlas al HTML vía WebSockets

# ==========================================
# 3. CARGA DE MODELOS DE INTELIGENCIA ARTIFICIAL
# ==========================================
print("Cargando modelo YOLOv5 (Armas)...")
# Carga tu modelo entrenado a medida desde el archivo best.pt
model_armas = torch.hub.load('ultralytics/yolov5', 'custom', path='best.pt', force_reload=False)
model_armas.conf = 0.40   # Confianza mínima del 40%
model_armas.iou = 0.40    # Evita cajas dobles sobre la misma arma
model_armas.agnostic = False 

print("Cargando modelo YOLOv8 (Rostros)...")
# Carga un modelo ligero de detección facial
model_caras = YOLO('yolov8n-face-lindevs.pt')

print("Cargando base de datos de rostros...")
vecinos_encodings = []    # Aquí se guardarán los "vectores matemáticos" de las caras
if os.path.exists('vecinos'):
    for archivo in os.listdir('vecinos'):
        if archivo.endswith((".jpg", ".png", ".jpeg")):
            try:
                # Transforma la foto jpg en un vector de 128 números únicos
                img = face_recognition.load_image_file(f"vecinos/{archivo}")
                enc = face_recognition.face_encodings(img)
                if len(enc) > 0: 
                    vecinos_encodings.append(enc[0])
            except Exception:
                pass

# ==========================================
# 4. FUNCIÓN: ALERTA WHATSAPP
# ==========================================
def enviar_alerta_grupo(mensaje):
    """Abre WhatsApp Web invisiblemente y despacha el mensaje."""
    try:
        print(f"🚀 Iniciando envío de alerta al grupo de WhatsApp...")
        pwk.sendwhatmsg_to_group_instantly(
            group_id=ID_GRUPO_WHATSAPP, 
            message=mensaje, 
            wait_time=12, 
            tab_close=True,
            close_time=3
        )
        print("🚨 Alerta enviada con éxito al grupo de WhatsApp.")
    except Exception as e:
        print(f"Error al enviar mensaje al grupo: {e}")

# ==========================================
# 5. MOTOR DE INTELIGENCIA ARTIFICIAL PRINCIPAL
# ==========================================
def procesar_camara():
    global output_frame, lock, alertas_recientes
    
    # Credenciales RTSP de tu cámara IP (Dahua/Hikvision)
    usuario = "admin"
    password = "admin2021"  
    ip_dvr = "192.168.1.39"              
    canal = "4"                      
    ruta_camara = f"rtsp://{usuario}:{password}@{ip_dvr}:554/cam/realmonitor?channel={canal}&subtype=0"
    
    cap = cv2.VideoCapture(ruta_camara)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) # Reduce latencia al mínimo descartando frames viejos
    
    frame_count = 0
    ultima_alerta = 0
    
    while True:
        # Mecanismo de reconexión si la cámara IP se apaga o pierde Wi-Fi
        if not cap.isOpened():
            print("⚠️ Conexión perdida con el DVR. Reconectando...")
            cap = cv2.VideoCapture(ruta_camara)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            time.sleep(2)
            continue
            
        ret, frame = cap.read()
        if not ret:
            print("⚠️ Trama vacía. Reiniciando stream...")
            cap.release()
            continue
            
        frame_count += 1
        frame = cv2.resize(frame, (800, 450)) # Optimiza el tamaño para no saturar CPU/GPU
        frame_renderizado = frame.copy()
        
        # Procesar IA 1 de cada 3 frames para dar fluidez visual al frontend
        if frame_count % 3 == 0:
            
            # --- A) YOLOv5: DETECCIÓN DE ARMAS ---
            res_armas = model_armas(frame, size=640, augment=False)
            det_armas = res_armas.pandas().xyxy[0] 
            
            hay_fuego, hay_blanca = False, False
            cajas_dibujo = []
            
            for index, row in det_armas.iterrows():
                if row['confidence'] >= 0.40:
                    label = row['name']
                    if label == 'pistol': hay_fuego = True
                    if label == 'knife': hay_blanca = True
                    # Guardamos coordenadas para dibujarlas luego
                    cajas_dibujo.append((int(row['xmin']), int(row['ymin']), int(row['xmax']), int(row['ymax']), label, row['confidence']))
            
            # --- B) YOLOv8 + DLIB: RECONOCIMIENTO FACIAL ---
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) # dlib usa formato RGB, OpenCV BGR
            res_caras = model_caras(frame, conf=0.30, verbose=False)
            
            identidad_global = "Desconocido"
            
            for box in res_caras[0].boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                # Busca rasgos biométricos solo dentro del área donde YOLO encontró una cara (Ahorra RAM)
                face_encodings = face_recognition.face_encodings(rgb_frame, [(y1, x2, y2, x1)])
                
                nombre = "Desconocido"
                color_cara = (0, 0, 255) # Rojo = Alarma
                
                if face_encodings:
                    # Compara la cara detectada contra toda nuestra base de vecinos autorizados
                    matches = face_recognition.compare_faces(vecinos_encodings, face_encodings[0], tolerance=0.5)
                    if True in matches:
                        nombre = "Vecino"
                        identidad_global = "Vecino"
                        color_cara = (0, 255, 0) # Verde = Seguro
                
                # Dibuja la caja facial
                cv2.rectangle(frame_renderizado, (x1, y1), (x2, y2), color_cara, 2)
                cv2.putText(frame_renderizado, nombre, (x1, max(y1 - 10, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_cara, 2)
            
            # --- C) GESTOR DE ALERTAS ---
            # Si hay un arma y pasaron 15 segundos desde la última alerta para no hacer spam
            if (hay_fuego or hay_blanca) and (time.time() - ultima_alerta > 15):
                tipo_alerta = "critica" if hay_fuego else "media"
                amenaza = "Arma de Fuego" if hay_fuego else "Arma Blanca"
                hora = datetime.now().strftime('%H:%M:%S')
                
                if not os.path.exists("Registros_Seguridad"):
                    os.makedirs("Registros_Seguridad")
                
                # Toma la fotografía con código único
                nombre_foto = f"Registros_Seguridad/evidencia_{datetime.now().strftime('%H%M%S')}_{uuid.uuid4().hex[:6]}.jpg"
                cv2.imwrite(nombre_foto, frame_renderizado)
                
                # Guarda en la Base de Datos SQLite
                guardar_alerta_bd("Cámara Principal", amenaza, identidad_global, nombre_foto)
                
                # Prepara la alerta para el HTML
                alertas_recientes.append({
                    "tipo": tipo_alerta, 
                    "amenaza": amenaza, 
                    "identidad": identidad_global, 
                    "hora": hora
                })
                
                # Si es un arma de fuego (Crítico), despacha el mensaje a WhatsApp en un hilo paralelo
                if hay_fuego:
                    mensaje_ws = f"🚨 SOC ALERTA DE SEGURIDAD: {amenaza} detectada a las {hora}. Sujeto: {identidad_global}. Precaución en perímetro."
                    hilo_wp = threading.Thread(target=enviar_alerta_grupo, args=(mensaje_ws,))
                    hilo_wp.start()
                    
                ultima_alerta = time.time()
                
            # --- D) RENDERIZADO VISUAL ---
            for (x1, y1, x2, y2, label, conf) in cajas_dibujo:
                color_arma = (0, 165, 255) # Naranja de alerta
                cv2.rectangle(frame_renderizado, (x1, y1), (x2, y2), color_arma, 3)
                texto = "Pistola" if label == 'pistol' else "Cuchillo"
                cv2.putText(frame_renderizado, f"{texto} {conf*100:.0f}%", (x1, max(y1 - 10, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_arma, 2)
                
        # Protegemos el fotograma global para que FastAPI lo envíe al navegador
        with lock:
            output_frame = frame_renderizado.copy()

# Iniciamos el motor de la cámara en un proceso de fondo ("daemon")
thread = threading.Thread(target=procesar_camara, daemon=True)
thread.start()


# ==========================================
# 6. RUTAS WEB (ENDPOINTS FASTAPI)
# ==========================================

@app.get("/")
async def index(request: Request):
    """ Carga el panel principal de HTML """
    return templates.TemplateResponse(request=request, name="dashboard.html")

def generar_video():
    """ Función yield que convierte los fotogramas de OpenCV en formato web streaming """
    global output_frame, lock
    while True:
        with lock:
            if output_frame is None:
                continue
            (flag, encodedImage) = cv2.imencode(".jpg", output_frame)
            if not flag:
                continue
        yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encodedImage) + b'\r\n')

@app.get("/video_feed")
async def video_feed():
    """Endpoint consumido por el <img src="..."> en el HTML para ver el video"""
    return StreamingResponse(generar_video(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.websocket("/ws/alertas")
async def websocket_alertas(websocket: WebSocket):
    """ Canal bidireccional WebSockets que notifica al HTML instantáneamente al ver un arma """
    await websocket.accept()
    global alertas_recientes
    try:
        while True:
            if len(alertas_recientes) > 0:
                alerta = alertas_recientes.pop(0)
                await websocket.send_json(alerta)
            await asyncio.sleep(1) # Revisa el buffer de alertas cada segundo
    except:
        pass

# --- ENDPOINTS RESTful (APIs) ---

@app.post("/api/registrar_vecino")
async def registrar_vecino_api(nombre: str = Form(...), fotos: List[UploadFile] = File(...)):
    """ Recibe las fotos del vecino desde el Frontend, extrae biometría y la carga a la RAM en vivo """
    global vecinos_encodings
    try:
        if not os.path.exists('vecinos'): os.makedirs('vecinos')
        
        nombre_limpio = nombre.replace(" ", "_")
        for idx, foto in enumerate(fotos):
            ruta_foto = f"vecinos/{nombre_limpio}_{idx}.jpg"
            with open(ruta_foto, "wb") as f:
                f.write(await foto.read())
                
            img = face_recognition.load_image_file(ruta_foto)
            enc = face_recognition.face_encodings(img)
            if len(enc) > 0: vecinos_encodings.append(enc[0])
                
        return JSONResponse(content={"status": "ok", "mensaje": f"Biometría de {nombre} procesada con éxito."})
    except Exception as e:
        return JSONResponse(content={"status": "error", "mensaje": str(e)}, status_code=500)

@app.post("/api/registrar_guardia")
async def registrar_guardia_api(username: str = Form(...), password: str = Form(...), nombre: str = Form(...), rol: str = Form(...)):
    """ Inserta a un nuevo usuario cifrado en la base de datos SQLite """
    try:
        from database import registrar_usuario
        exito = registrar_usuario(username, password, nombre, rol)
        if exito:
            return JSONResponse(content={"status": "ok", "mensaje": f"Usuario {nombre} ({rol}) creado exitosamente."})
        return JSONResponse(content={"status": "error", "mensaje": "El usuario ya existe."}, status_code=400)
    except Exception as e:
        return JSONResponse(content={"status": "error", "mensaje": str(e)}, status_code=500)

@app.post("/api/login")
async def login(username: str = Form(...), password: str = Form(...)):
    """ Valida la contraseña y devuelve los datos del rol al frontend """
    resultado = verificar_usuario(username, password)
    if resultado["exito"]:
        return JSONResponse(content={"status": "ok", "usuario": resultado})
    return JSONResponse(content={"status": "error", "mensaje": "Credenciales inválidas"}, status_code=401)

@app.get("/api/historial")
async def api_historial():
    """ Extrae los últimos 50 eventos registrados en BD para la auditoría """
    try:
        from database import obtener_historial
        datos = obtener_historial()
        return JSONResponse(content={"status": "ok", "datos": datos})
    except Exception as e:
        return JSONResponse(content={"status": "error", "mensaje": str(e)}, status_code=500)

@app.post("/api/atender_alerta")
async def atender_alerta_api(hora: str = Form(...), estado: str = Form(...), guardia: str = Form(...)):
    """ Actualiza el estado de una amenaza a Confirmada/Falsa alarma """
    try:
        from database import actualizar_estado_alerta
        if actualizar_estado_alerta(hora, estado, guardia):
            return JSONResponse(content={"status": "ok"})
        return JSONResponse(content={"status": "error", "mensaje": "Fallo en BD"}, status_code=400)
    except Exception as e:
        return JSONResponse(content={"status": "error", "mensaje": str(e)}, status_code=500)

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8000)