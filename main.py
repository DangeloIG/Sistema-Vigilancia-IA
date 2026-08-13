import pathlib
import platform
import os
import cv2
import face_recognition
import time
import torch
import numpy as np
import threading
from datetime import datetime
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
import warnings
import gc 

# --- 1. PARCHES DE COMPATIBILIDAD ---
if platform.system() == 'Windows':
    pathlib.PosixPath = pathlib.WindowsPath

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|timeout;2000"
warnings.filterwarnings("ignore")

# --- 2. CONFIGURACIÓN DE FASTAPI ---
app = FastAPI(title="Sistema de Vigilancia IA")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Variables globales para compartir entre la IA y el Servidor Web
output_frame = None
lock = threading.Lock()
alertas_recientes = []

# --- 3. INICIALIZACIÓN DE MODELOS ---
print("Cargando modelo YOLOv5 (Armas)...")
model_armas = torch.hub.load('ultralytics/yolov5', 'custom', path='best.pt', force_reload=False)
model_armas.conf = 0.40  # UMBRAL AJUSTADO AL 40%
model_armas.iou = 0.40       
model_armas.agnostic = False 

print("Cargando base de datos de rostros...")
vecinos_encodings = []
if os.path.exists('vecinos'):
    for archivo in os.listdir('vecinos'):
        if archivo.endswith((".jpg", ".png", ".jpeg")):
            try:
                img = face_recognition.load_image_file(f"vecinos/{archivo}")
                enc = face_recognition.face_encodings(img)
                if len(enc) > 0: 
                    vecinos_encodings.append(enc[0])
            except Exception as e:
                pass

# --- 4. MOTOR DE INTELIGENCIA ARTIFICIAL (HILO EN SEGUNDO PLANO) ---
def procesar_camara():
    global output_frame, lock, alertas_recientes
    
    usuario = "admin"
    password = "admin2021"  
    ip_dvr = "192.168.1.39"              
    canal = "4"                      
    ruta_camara = 0
    
    cap = cv2.VideoCapture(ruta_camara)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
    
    frame_count = 0
    ultima_alerta = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1)
            continue
            
        frame_count += 1
        frame = cv2.resize(frame, (800, 450))
        frame_renderizado = frame.copy()
        
        # Procesamos IA 1 de cada 10 fotogramas para máxima fluidez
        if frame_count % 10 == 0:
            res_armas = model_armas(frame, size=640, augment=False)
            det_armas = res_armas.pandas().xyxy[0] 
            
            hay_fuego, hay_blanca = False, False
            cajas_dibujo = []
            
            for index, row in det_armas.iterrows():
                if row['confidence'] >= 0.40: # Umbral 40%
                    label = row['name']
                    if label == 'pistol': hay_fuego = True
                    if label == 'knife': hay_blanca = True
                    cajas_dibujo.append((int(row['xmin']), int(row['ymin']), int(row['xmax']), int(row['ymax']), label, row['confidence']))
            
            identificado = False
            # Lógica de Reconocimiento Facial Simplificada aquí...
            # (Se asume la validación contra vecinos_encodings)
            
            # Gestión de Alertas Web
            if (hay_fuego or hay_blanca) and (time.time() - ultima_alerta > 5):
                tipo_alerta = "critica" if hay_fuego else "media"
                amenaza = "Arma de Fuego" if hay_fuego else "Arma Blanca"
                identidad = "Vecino" if identificado else "Desconocido"
                hora = datetime.now().strftime('%H:%M:%S')
                
                # Guardamos la alerta para enviarla al Frontend
                alertas_recientes.append({
                    "tipo": tipo_alerta, 
                    "amenaza": amenaza, 
                    "identidad": identidad, 
                    "hora": hora
                })
                ultima_alerta = time.time()
                
            # Dibujar cajas (Solo como referencia visual rápida)
            for (x1, y1, x2, y2, label, conf) in cajas_dibujo:
                cv2.rectangle(frame_renderizado, (x1, y1), (x2, y2), (0, 165, 255), 2)
                
        # Actualizamos el frame global de forma segura
        with lock:
            output_frame = frame_renderizado.copy()

# Iniciamos el motor de IA en un hilo separado
thread = threading.Thread(target=procesar_camara, daemon=True)
thread.start()

# --- 5. RUTAS WEB (ENDPOINTS) ---

# Ruta principal: Carga el HTML
@app.get("/")
async def index(request: Request):
    # Formato actualizado con nombres explícitos de variables
    return templates.TemplateResponse(request=request, name="dashboard.html")

# Generador de Video (Transforma frames a formato web)
def generar_video():
    global output_frame, lock
    while True:
        with lock:
            if output_frame is None:
                continue
            (flag, encodedImage) = cv2.imencode(".jpg", output_frame)
            if not flag:
                continue
        
        yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encodedImage) + b'\r\n')

# Ruta del Video: El HTML lee esto para el streaming
@app.get("/video_feed")
async def video_feed():
    return StreamingResponse(generar_video(), media_type="multipart/x-mixed-replace; boundary=frame")

# WebSockets: Envía alertas al HTML en tiempo real
@app.websocket("/ws/alertas")
async def websocket_alertas(websocket: WebSocket):
    await websocket.accept()
    global alertas_recientes
    try:
        while True:
            if len(alertas_recientes) > 0:
                alerta = alertas_recientes.pop(0)
                await websocket.send_json(alerta)
            await asyncio.sleep(1) # Revisa alertas cada segundo
    except:
        pass

if __name__ == '__main__':
    # Arrancamos el servidor local
    uvicorn.run(app, host="0.0.0.0", port=8000)