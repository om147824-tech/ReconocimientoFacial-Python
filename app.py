from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
import os
import datetime
from pymongo import MongoClient
import cv2
import numpy as np
from PIL import Image
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = 'mi_clave_secreta'  # Cambia esta clave

# --- Configuración de MongoDB ---
cliente = MongoClient("mongodb://localhost:27017/")
db = cliente["asistencia_escolar"]
personas = db["personas"]
asistencias = db["asistencias"]

# --- Configuración de correo ---
EMAIL = "domax434@gmail.com"
PASSWORD = "qbxr espf iftc qxnt"
DESTINATARIO = "om147824@gmail.com"

# --- Configuración de directorios ---
UPLOAD_FOLDER = 'fotos_estudiantes'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Detección de rostros ---
haar_cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
face_cascade = cv2.CascadeClassifier(haar_cascade_path)

# --- Función para entrenar el reconocedor de rostros ---
def train_recognizer():
    estudiantes = list(personas.find())
    if not estudiantes:
        return None, {}
    
    faces = []
    labels = []
    label_to_name = {}
    label_id = 0
    for est in estudiantes:
        face_img_path = est.get("face_path")
        if face_img_path and os.path.exists(face_img_path):
            img = cv2.imread(face_img_path, cv2.IMREAD_GRAYSCALE)
            faces.append(img)
            labels.append(label_id)
            label_to_name[label_id] = f"{est['nombre']} {est['apellido_paterno']}"
            label_id += 1

    if faces and labels:
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.train(faces, np.array(labels))
        return recognizer, label_to_name
    else:
        return None, {}

# --- Rutas de la aplicación ---

# Página de inicio
@app.route('/')
def index():
    return render_template('index.html')

# Registro de estudiantes
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        paterno = request.form.get('paterno', '').strip()
        materno = request.form.get('materno', '').strip()
        carrera = request.form.get('carrera', '').strip()
        grupo = request.form.get('grupo', '').strip()
        photo = request.files.get('photo')

        if not all([nombre, paterno, materno, carrera, grupo, photo]):
            flash("Todos los campos son obligatorios y se requiere foto", "error")
            return redirect(url_for('register'))

        filename = secure_filename(f"{nombre}_{paterno}.jpg")
        photo_path = os.path.join(UPLOAD_FOLDER, filename)
        photo.save(photo_path)

        # Procesa la imagen para detectar rostro
        img = cv2.imread(photo_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)

        if len(faces) == 0:
            flash("No se detectó ningún rostro en la foto", "error")
            return redirect(url_for('register'))
        (x, y, w, h) = faces[0]
        face_img = gray[y:y+h, x:x+w]
        face_filename = filename.replace(".jpg", "_face.jpg")
        face_path = os.path.join(UPLOAD_FOLDER, face_filename)
        cv2.imwrite(face_path, face_img)

        estudiante = {
            "nombre": nombre,
            "apellido_paterno": paterno,
            "apellido_materno": materno,
            "carrera": carrera,
            "grupo": grupo,
            "foto": photo_path,
            "face_path": face_path
        }
        personas.insert_one(estudiante)
        flash("Estudiante registrado correctamente", "success")
        return redirect(url_for('index'))
    return render_template('register.html')

# Página para iniciar asistencia
@app.route('/attendance', methods=['GET', 'POST'])
def attendance():
    if request.method == 'POST':
        grupo = request.form.get('grupo', '').strip()
        if not grupo:
            flash("Debe especificar un grupo", "error")
            return redirect(url_for('attendance'))

        recognizer, label_to_name = train_recognizer()
        if recognizer is None:
            flash("No hay estudiantes registrados para entrenamiento", "error")
            return redirect(url_for('attendance'))

        cap = cv2.VideoCapture(0)  # Usa la cámara por defecto. Ajusta el índice si es necesario.
        asistentes = set()
        start_time = datetime.datetime.now()
        timeout = datetime.timedelta(minutes=2)

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if datetime.datetime.now() - start_time >= timeout:
                break
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
            
            for (x, y, w, h) in faces:
                face_roi = gray[y:y+h, x:x+w]
                try:
                    face_roi_resized = cv2.resize(face_roi, (100, 100))
                except Exception:
                    continue
                
                label, confidence = recognizer.predict(face_roi_resized)
                if confidence < 70:
                    nombre_completo = label_to_name.get(label, "Desconocido")
                    asistentes.add(nombre_completo)
                    
        cap.release()
        
        if asistentes:
            # Registrar asistencia en la base de datos
            fecha = datetime.datetime.now()
            for asistente in asistentes:
                asistencias.insert_one({
                    "nombre": asistente,
                    "grupo": grupo,
                    "fecha": fecha,
                    "asistio": True
                })
            # Enviar reporte por correo
            send_email_report(asistentes, grupo)
            flash(f"Asistencia registrada para {len(asistentes)} estudiantes. Reporte enviado.", "success")
            return render_template('attendance.html', asistentes=list(asistentes), grupo=grupo)
        else:
            flash("No se detectó ningún asistente durante el periodo de asistencia.", "info")
            return redirect(url_for('attendance'))
    return render_template('attendance.html')

# Envío manual del reporte
@app.route('/send_report', methods=['GET', 'POST'])
def send_report():
    if request.method == 'POST':
        grupo = request.form.get('grupo', '').strip()
        if not grupo:
            flash("Debe especificar un grupo para enviar el reporte", "error")
            return redirect(url_for('send_report'))
        start_of_day = datetime.datetime.combine(datetime.datetime.now().date(), datetime.time.min)
        registros = list(asistencias.find({
            "grupo": grupo,
            "fecha": {"$gte": start_of_day}
        }))
        if not registros:
            flash("No se encontraron registros de asistencia para hoy en este grupo", "info")
            return redirect(url_for('send_report'))
        asistentes = set(reg["nombre"] for reg in registros)
        send_email_report(asistentes, grupo)
        flash("Reporte enviado manualmente.", "success")
        return redirect(url_for('index'))
    return render_template('send_report.html')

# Función para enviar el reporte por correo
def send_email_report(asistentes, grupo):
    try:
        mensaje = MIMEMultipart()
        mensaje['Subject'] = f"Reporte de Asistencia - {grupo}"
        mensaje['From'] = EMAIL
        mensaje['To'] = DESTINATARIO
        
        cuerpo = f"""
        <h2>Reporte de Asistencia</h2>
        <p><strong>Grupo:</strong> {grupo}</p>
        <p><strong>Fecha:</strong> {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        <p><strong>Total de asistentes:</strong> {len(asistentes)}</p>
        <h3>Lista de Asistentes:</h3>
        <ul>
        {''.join(f'<li>{asistente}</li>' for asistente in asistentes)}
        </ul>
        """
        mensaje.attach(MIMEText(cuerpo, 'html'))
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL, PASSWORD)
            server.sendmail(EMAIL, DESTINATARIO, mensaje.as_string())
    except Exception as e:
        print("Error enviando correo:", str(e))

if __name__ == '__main__':
    app.run(debug=True)
