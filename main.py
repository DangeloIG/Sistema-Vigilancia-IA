# ==========================================
# IMPORTACIONES DEL SISTEMA Y LIBRERÍAS
# ==========================================
import pathlib            
import platform           
import os                 
import cv2                
import face_recognition   
import time               
import torch              
import numpy as np        
import threading          
import asyncio            
from datetime import datetime 
from typing import List   

from fastapi import FastAPI, Request, WebSocket, Form, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
import warnings
from ultralytics import YOLO
import pywhatkit as pwk
import uuid 

from database import verificar_usuario, guardar_alerta_bd

# ==========================================
# 1. PARCHES DE COMPATIBILIDAD Y OPTIMIZACIÓN
# ==========================================
if platform.system() == 'Windows':
    pathlib.PosixPath = pathlib.WindowsPath

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay"
warnings.filterwarnings("ignore")

ID_GRUPO_WHATSAPP = "I7hlxHyE98FHgatC6TfVBZ" 

app = FastAPI(title="Sistema de Vigilancia IA")
app.mount("/static", StaticFiles(directory="static"), name="static")

if not os.path.exists("Registros_Seguridad"):
    os.makedirs("Registros_Seguridad")
app.mount("/Registros_Seguridad", StaticFiles(directory="Registros_Seguridad"), name="registros")

templates = Jinja2Templates(directory="templates")

# ==========================================
# 2. VARIABLES GLOBALES Y AJUSTES
# ==========================================
output_frame = None
lock = threading.Lock()
alertas_recientes = []
estado_camara_global = "normal" 
ultimo_frame_raw = None 

# Variables configurables desde la web
TOLERANCIA_FACIAL = 0.5 

# ==========================================
# 3. CARGA DE MODELOS (IA)
# ==========================================
print("Cargando modelo YOLOv5 (Armas)...")
model_armas = torch.hub.load('ultralytics/yolov5', 'custom', path='best.pt', force_reload=False)
model_armas.conf = 0.78 
model_armas.iou = 0.40
model_armas.agnostic = False 

print("Cargando modelo YOLOv8 (Rostros)...")
model_caras = YOLO('yolov8n-face-lindevs.pt')

print("Cargando base de datos de rostros...")
vecinos_encodings = []
vecinos_nombres = []

def cargar_rostros():
    """ Escanea la carpeta y carga los rostros y nombres en memoria (Persistencia) """
    global vecinos_encodings, vecinos_nombres
    vecinos_encodings.clear()
    vecinos_nombres.clear()
    if not os.path.exists('vecinos'):
        os.makedirs('vecinos')
    for archivo in os.listdir('vecinos'):
        if archivo.endswith((".jpg", ".png", ".jpeg")):
            try:
                img = face_recognition.load_image_file(f"vecinos/{archivo}")
                enc = face_recognition.face_encodings(img)
                if len(enc) > 0:
                    vecinos_encodings.append(enc[0])
                    nombre_real = archivo.rsplit('_', 1)[0].replace("_", " ")
                    vecinos_nombres.append(nombre_real)
            except Exception:
                pass

cargar_rostros()

def enviar_alerta_grupo(mensaje):
    try:
        pwk.sendwhatmsg_to_group_instantly(
            group_id=ID_GRUPO_WHATSAPP, message=mensaje, wait_time=12, tab_close=True, close_time=3
        )
    except Exception as e:
        print(f"Error al enviar mensaje: {e}")

# ==========================================
# 4. HILO 1: LECTOR DE CÁMARA
# ==========================================
def capturar_video_rtsp():
    global ultimo_frame_raw
    usuario = "admin"
    password = "admin2021"  
    ip_dvr = "192.168.1.39"              
    canal = "1"                      
    ruta_camara = f"rtsp://{usuario}:{password}@{ip_dvr}:554/cam/realmonitor?channel={canal}&subtype=0"
    
    cap = cv2.VideoCapture(ruta_camara, cv2.CAP_FFMPEG)
    while True:
        if not cap.isOpened():
            time.sleep(1)
            cap = cv2.VideoCapture(ruta_camara, cv2.CAP_FFMPEG)
            continue
            
        ret, frame = cap.read()
        if ret:
            ultimo_frame_raw = cv2.resize(frame, (800, 450))
        else:
            cap.release()
            time.sleep(1)

# ==========================================
# 5. HILO 2: MOTOR DE INTELIGENCIA ARTIFICIAL
# ==========================================
def procesar_ia():
    global output_frame, lock, alertas_recientes, estado_camara_global, ultimo_frame_raw, TOLERANCIA_FACIAL
    ultima_alerta = 0
    estado_borde_actual = "normal" 
    
    while True:
        if ultimo_frame_raw is None:
            time.sleep(0.05)
            continue
            
        frame = ultimo_frame_raw.copy()
        frame_renderizado = frame.copy()
        
        # --- A) DETECCIÓN DE ARMAS ---
        res_armas = model_armas(frame, size=640, augment=False)
        det_armas = res_armas.pandas().xyxy[0] 
        hay_fuego, hay_blanca = False, False
        cajas_dibujo = []
        
        for index, row in det_armas.iterrows():
            if row['confidence'] >= model_armas.conf:
                label = row['name']
                if label == 'pistol': hay_fuego = True
                if label == 'knife': hay_blanca = True
                cajas_dibujo.append((int(row['xmin']), int(row['ymin']), int(row['xmax']), int(row['ymax']), label, row['confidence']))
        
        # --- B) RECONOCIMIENTO FACIAL ---
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res_caras = model_caras(frame, conf=0.30, verbose=False)
        
        identidad_global = "Desconocido"
        rostro_detectado = False 
        
        for box in res_caras[0].boxes:
            rostro_detectado = True 
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            face_encodings = face_recognition.face_encodings(rgb_frame, [(y1, x2, y2, x1)])
            
            nombre_pantalla = "Desconocido"
            color_cara = (0, 0, 255)
            
            if face_encodings:
                matches = face_recognition.compare_faces(vecinos_encodings, face_encodings[0], tolerance=TOLERANCIA_FACIAL)
                if True in matches:
                    primer_match = matches.index(True)
                    nombre_real = vecinos_nombres[primer_match].title()
                    
                    nombre_pantalla = "Vecino"         # Lo que se ve en el video
                    identidad_global = nombre_real     # Lo que se guarda en BD / WhatsApp
                    color_cara = (0, 255, 0)
            
            cv2.rectangle(frame_renderizado, (x1, y1), (x2, y2), color_cara, 2)
            cv2.putText(frame_renderizado, nombre_pantalla, (x1, max(y1 - 10, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_cara, 2)
        
        # --- C) SEMÁFORO DE ALERTAS ---
        nivel_alerta = None
        amenaza_texto = ""

        if hay_fuego:
            estado_borde_actual = "critica"
            nivel_alerta = "critica"
            amenaza_texto = "Arma de Fuego"
        elif hay_blanca:
            if identidad_global == "Desconocido":
                estado_borde_actual = "alta"
                nivel_alerta = "alta"
                amenaza_texto = "Arma Blanca"
            else:
                estado_borde_actual = "media"
                nivel_alerta = "media"
                amenaza_texto = "Arma Blanca"
        elif rostro_detectado and identidad_global == "Desconocido":
            estado_borde_actual = "precaucion"
        else:
            estado_borde_actual = "normal"

        # --- D) GESTIÓN BASE DE DATOS Y WHATSAPP ---
        if nivel_alerta and (time.time() - ultima_alerta > 15):
            hora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            nombre_foto = f"Registros_Seguridad/evidencia_{datetime.now().strftime('%H%M%S')}_{uuid.uuid4().hex[:6]}.jpg"
            cv2.imwrite(nombre_foto, frame_renderizado)
            
            # Se guarda la identidad real en la Base de Datos
            guardar_alerta_bd(hora, "Cámara Principal", amenaza_texto, identidad_global, nombre_foto)
            
            alertas_recientes.append({
                "tipo": nivel_alerta, 
                "amenaza": amenaza_texto, 
                "identidad": identidad_global, 
                "hora": hora
            })
            
            if hay_fuego:
                if identidad_global != "Desconocido":
                    txt_sospechoso = f"El posible sospechoso es: {identidad_global}"
                else:
                    txt_sospechoso = "Sujeto: Desconocido"
                    
                mensaje_ws = f"🚨 SOC ALERTA CRÍTICA: Pistola detectada a las {hora}. {txt_sospechoso}. Precaución inmediata."
                hilo_wp = threading.Thread(target=enviar_alerta_grupo, args=(mensaje_ws,))
                hilo_wp.start()
                
            ultima_alerta = time.time()
            
        for (x1, y1, x2, y2, label, conf) in cajas_dibujo:
            color_arma = (0, 165, 255)
            cv2.rectangle(frame_renderizado, (x1, y1), (x2, y2), color_arma, 3)
            texto = "Pistola" if label == 'pistol' else "Cuchillo"
            cv2.putText(frame_renderizado, f"{texto} {conf*100:.0f}%", (x1, max(y1 - 10, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_arma, 2)
            
        with lock:
            output_frame = frame_renderizado.copy()
            estado_camara_global = estado_borde_actual
            
        time.sleep(0.01)

threading.Thread(target=capturar_video_rtsp, daemon=True).start()
threading.Thread(target=procesar_ia, daemon=True).start()

# ==========================================
# 6. RUTAS WEB (ENDPOINTS FASTAPI)
# ==========================================
@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html")

def generar_video():
    global output_frame, lock
    while True:
        frame_to_encode = None
        # Solo entramos al bloqueo una fracción de milisegundo para copiar el frame
        with lock:
            if output_frame is not None:
                frame_to_encode = output_frame.copy()
        
        # Si hay frame, lo codificamos y lo enviamos a la web sin bloquear a la IA
        if frame_to_encode is not None:
            (flag, encodedImage) = cv2.imencode(".jpg", frame_to_encode)
            if flag:
                yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encodedImage) + b'\r\n')
        
        # Limitamos la transmisión web a ~30 FPS para darle respiro al procesador
        time.sleep(0.033) 

@app.get("/video_feed")
async def video_feed():
    return StreamingResponse(generar_video(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.websocket("/ws/alertas")
async def websocket_alertas(websocket: WebSocket):
    await websocket.accept()
    global alertas_recientes, estado_camara_global
    try:
        while True:
            payload = {"borde": estado_camara_global}
            if len(alertas_recientes) > 0:
                payload["alerta"] = alertas_recientes.pop(0)
            await websocket.send_json(payload)
            await asyncio.sleep(1)
    except:
        pass

# =======================
# endpoints de biometria
# =======================
@app.get("/api/vecinos")
async def obtener_vecinos():
    nombres = list(set(vecinos_nombres))
    return JSONResponse(content={"status": "ok", "vecinos": nombres})

@app.delete("/api/vecinos/{nombre}")
async def eliminar_vecino(nombre: str):
    try:
        nombre_limpio = nombre.replace(" ", "_").lower()
        if not os.path.exists('vecinos'):
            return JSONResponse(content={"status": "error", "mensaje": "Directorio vacío"})
        for archivo in os.listdir('vecinos'):
            if archivo.startswith(nombre_limpio + "_"):
                os.remove(f"vecinos/{archivo}")
        
        cargar_rostros() 
        return JSONResponse(content={"status": "ok", "mensaje": f"Biometría de {nombre} eliminada correctamente."})
    except Exception as e:
        return JSONResponse(content={"status": "error", "mensaje": str(e)}, status_code=500)

@app.post("/api/registrar_vecino")
async def registrar_vecino_api(nombre: str = Form(...), fotos: List[UploadFile] = File(...)):
    try:
        if not os.path.exists('vecinos'): os.makedirs('vecinos')
        nombre_limpio = nombre.strip().lower().replace(" ", "_")
        for idx, foto in enumerate(fotos):
            ruta_foto = f"vecinos/{nombre_limpio}_{idx}.jpg"
            with open(ruta_foto, "wb") as f:
                f.write(await foto.read())
        
        cargar_rostros() 
        return JSONResponse(content={"status": "ok", "mensaje": f"Biometría de {nombre} procesada."})
    except Exception as e:
        return JSONResponse(content={"status": "error", "mensaje": str(e)}, status_code=500)

# =======================
# Endpoint configuración
# =======================
@app.post("/api/configuracion")
async def actualizar_configuracion(conf_yolo: float = Form(...), tol_facial: float = Form(...)):
    global TOLERANCIA_FACIAL, model_armas
    try:
        model_armas.conf = conf_yolo
        TOLERANCIA_FACIAL = tol_facial
        return JSONResponse(content={"status": "ok", "mensaje": "Parámetros actualizados y aplicados a la IA."})
    except Exception as e:
        return JSONResponse(content={"status": "error", "mensaje": str(e)}, status_code=500)

@app.post("/api/registrar_guardia")
async def registrar_guardia_api(username: str = Form(...), password: str = Form(...), nombre: str = Form(...), rol: str = Form(...)):
    try:
        from database import registrar_usuario
        exito = registrar_usuario(username, password, nombre, rol)
        if exito: return JSONResponse(content={"status": "ok", "mensaje": f"Usuario creado."})
        return JSONResponse(content={"status": "error", "mensaje": "El usuario ya existe."}, status_code=400)
    except Exception as e: return JSONResponse(content={"status": "error", "mensaje": str(e)}, status_code=500)

@app.post("/api/login")
async def login(username: str = Form(...), password: str = Form(...)):
    resultado = verificar_usuario(username, password)
    if resultado["exito"]: return JSONResponse(content={"status": "ok", "usuario": resultado})
    return JSONResponse(content={"status": "error", "mensaje": "Credenciales inválidas"}, status_code=401)

@app.get("/api/historial")
async def api_historial(fecha: str = None):
    try:
        from database import obtener_historial
        datos = obtener_historial(fecha)
        return JSONResponse(content={"status": "ok", "datos": datos})
    except Exception as e: return JSONResponse(content={"status": "error", "mensaje": str(e)}, status_code=500)

@app.post("/api/atender_alerta")
async def atender_alerta_api(hora: str = Form(...), estado: str = Form(...), guardia: str = Form(...)):
    try:
        from database import actualizar_estado_alerta
        if actualizar_estado_alerta(hora, estado, guardia): return JSONResponse(content={"status": "ok"})
        return JSONResponse(content={"status": "error", "mensaje": "Fallo en BD"}, status_code=400)
    except Exception as e: return JSONResponse(content={"status": "error", "mensaje": str(e)}, status_code=500)

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8000)