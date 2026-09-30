import sqlite3
import bcrypt
import os

DB_NAME = "seguridad.db"

def inicializar_bd():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Tabla Usuarios
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            nombre TEXT,
            rol TEXT
        )
    """)
    
    # Tabla Historial (Unificamos fecha_hora para que el calendario filtre bien)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial_alertas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora TEXT,
            camara TEXT,
            amenaza TEXT,
            sujeto TEXT,
            estado TEXT DEFAULT 'Pendiente',
            atendido_por TEXT DEFAULT 'N/A',
            foto TEXT
        )
    """)
    
    # Inserción de prueba solo si la tabla usuarios está vacía
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        salt = bcrypt.gensalt()
        hash_pass = bcrypt.hashpw("123".encode('utf-8'), salt).decode('utf-8')
        cursor.execute("INSERT INTO usuarios (username, password_hash, nombre, rol) VALUES (?, ?, ?, ?)",
                       ("admin", hash_pass, "D'Angelo (Admin)", "Administrador"))
        cursor.execute("INSERT INTO usuarios (username, password_hash, nombre, rol) VALUES (?, ?, ?, ?)",
                       ("guardia", hash_pass, "Guardia Turno 1", "Trabajador"))
    
    conn.commit()
    conn.close()

# Disparamos la creación al cargar
inicializar_bd()

def guardar_alerta_bd(hora, camara, amenaza, sujeto, foto):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO historial_alertas (fecha_hora, camara, amenaza, sujeto, estado, atendido_por, foto)
            VALUES (?, ?, ?, ?, 'Pendiente', 'N/A', ?)
        """, (hora, camara, amenaza, sujeto, foto))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error al guardar alerta: {e}")

def obtener_historial(fecha_filtro=None):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        if fecha_filtro:
            cursor.execute("SELECT * FROM historial_alertas WHERE fecha_hora LIKE ? ORDER BY id DESC LIMIT 50", (f"{fecha_filtro}%",))
        else:
            cursor.execute("SELECT * FROM historial_alertas ORDER BY id DESC LIMIT 50")
        
        columnas = [desc[0] for desc in cursor.description]
        filas = cursor.fetchall()
        conn.close()
        
        return [dict(zip(columnas, fila)) for fila in filas]
    except Exception as e:
        print(f"Error obtener historial: {e}")
        return []

def actualizar_estado_alerta(hora, estado, guardia):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        # Truco infalible: Usamos el ID más reciente pendiente. Evita errores de milisegundos.
        cursor.execute("""
            UPDATE historial_alertas 
            SET estado = ?, atendido_por = ? 
            WHERE id = (SELECT id FROM historial_alertas WHERE estado = 'Pendiente' ORDER BY id DESC LIMIT 1)
        """, (estado, guardia))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error actualizar alerta: {e}")
        return False

def registrar_usuario(username, password, nombre, rol="Guardia"):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        cursor.execute("INSERT INTO usuarios (username, password_hash, nombre, rol) VALUES (?, ?, ?, ?)", 
                       (username, password_hash, nombre, rol))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        print(f"Error al registrar: {e}")
        return False

def verificar_usuario(username, password_intento):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash, nombre, rol FROM usuarios WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        if row and bcrypt.checkpw(password_intento.encode('utf-8'), row[0].encode('utf-8')):
            return {"exito": True, "nombre": row[1], "rol": row[2]}
        return {"exito": False}
    except Exception as e:
        print(f"Error login: {e}")
        return {"exito": False}