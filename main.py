import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import cv2
import os
from pymongo import MongoClient
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
import numpy as np

# Configuración de MongoDB
cliente = MongoClient("mongodb://localhost:27017/")
db = cliente["asistencia_escolar"]
personas = db["personas"]
asistencias = db["asistencias"]

# Configuración de correo
EMAIL = "domax434@gmail.com"
PASSWORD = "qbxr espf iftc qxnt"
DESTINATARIO = "om147824@gmail.com"

# Configuración de directorios
carpeta_fotos = "fotos_estudiantes"
os.makedirs(carpeta_fotos, exist_ok=True)

# Detección de rostros
haar_cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
face_cascade = cv2.CascadeClassifier(haar_cascade_path)

class SistemaAsistencia:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Asistencia")
        self.root.geometry("800x600")
        self.foto_path = ""
        self.recognizer = None
        self.label_to_name = {}
        self.crear_interfaz()
        
    def crear_interfaz(self):
        # Configuración del estilo para una apariencia futurista y profesional
        style = ttk.Style()
        style.theme_use("clam")
        
        # Colores futuristas: fondo oscuro, acentos cian/neón y texto claro.
        self.root.configure(bg="#1E1E2F")
        style.configure("TFrame", background="#1E1E2F")
        style.configure("TLabel", background="#1E1E2F", foreground="#E0E0E0", font=("Helvetica", 12))
        style.configure("Title.TLabel", font=("Helvetica", 18, "bold"), background="#1E1E2F", foreground="#00FFFF")
        style.configure("TButton", background="#252525", foreground="#00FFFF", font=("Helvetica", 12, "bold"))
        style.map("TButton",
                  background=[("active", "#00FFFF")],
                  foreground=[("active", "#252525")])
        style.configure("TLabelframe", background="#1E1E2F", foreground="#00FFFF", font=("Helvetica", 12, "bold"))
        style.configure("TLabelframe.Label", background="#1E1E2F", foreground="#00FFFF")
        
        main_frame = ttk.Frame(self.root, padding="20 20 20 20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Logo (opcional)
        logo_path = "imagenes/Imagen2.png"  
        if os.path.exists(logo_path):
            logo_img = Image.open(logo_path)
            logo_img = logo_img.resize((100, 100))
            logo_tk = ImageTk.PhotoImage(logo_img)
            logo_label = ttk.Label(main_frame, image=logo_tk)
            logo_label.image = logo_tk
            logo_label.pack(side="left", anchor="nw", pady=5, padx=5)
        else:
            print(f"No se encontró el archivo de logo: {logo_path}")
        
        # Título principal
        title_label = ttk.Label(main_frame, text="Sistema de Asistencia Inteligente", style="Title.TLabel")
        title_label.pack(pady=10)
        
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        content_frame.columnconfigure(0, weight=1)
        content_frame.columnconfigure(1, weight=1)
        
        # Formulario de registro en un LabelFrame
        form_frame = ttk.LabelFrame(content_frame, text="Registro de Estudiantes", padding="10 10 10 10")
        form_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        # Campos del formulario
        campos = [
            ("Nombre:", "nombre"),
            ("Apellido Paterno:", "paterno"),
            ("Apellido Materno:", "materno"),
            ("Carrera:", "carrera"),
            ("Grupo:", "grupo")
        ]
        self.entries = {}
        for i, (label_text, key) in enumerate(campos):
            lbl = ttk.Label(form_frame, text=label_text)
            lbl.grid(row=i, column=0, sticky="e", pady=5, padx=5)
            entry = ttk.Entry(form_frame, width=30)
            entry.grid(row=i, column=1, pady=5, padx=5)
            self.entries[key] = entry
        
        # Botones del formulario
        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=len(campos), column=0, columnspan=2, pady=10)
        
        self.btn_foto = ttk.Button(button_frame, text="📸 Tomar Foto", command=self.tomar_foto)
        self.btn_foto.grid(row=0, column=0, padx=5)
        
        self.btn_guardar = ttk.Button(button_frame, text="💾 Guardar Estudiante", command=self.guardar_estudiante)
        self.btn_guardar.grid(row=0, column=1, padx=5)
        
        # Botón para refrescar el formulario
        self.btn_refrescar = ttk.Button(button_frame, text="🔄 Refrescar", command=self.refrescar)
        self.btn_refrescar.grid(row=0, column=2, padx=5)
        
        # Vista previa de la foto
        photo_frame = ttk.LabelFrame(content_frame, text="Vista Previa", padding="10 10 10 10")
        photo_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        photo_frame.columnconfigure(0, weight=1)
        photo_frame.rowconfigure(0, weight=1)
        
        self.label_foto = ttk.Label(photo_frame)
        self.label_foto.grid(row=0, column=0, sticky="nsew")
        
        # Botones a nivel del main_frame
        self.btn_lista = ttk.Button(main_frame, text="📋 Iniciar Asistencia", command=self.iniciar_asistencia_thread)
        self.btn_lista.pack(pady=10)
        
        self.btn_reporte_manual = ttk.Button(main_frame, text="📧 Enviar Reporte", command=self.enviar_reporte_manual)
        self.btn_reporte_manual.pack(pady=10)
    
    def refrescar(self):
        """Función para limpiar los campos del formulario y reiniciar la vista previa."""
        for key in self.entries:
            self.entries[key].delete(0, tk.END)
        self.label_foto.config(image='')
        self.foto_path = ""
        messagebox.showinfo("Interfaz Refrescada", "Los campos han sido limpiados.")
    
    def tomar_foto(self):
        """Captura una foto desde la webcam."""
        nombre = self.entries["nombre"].get().strip()
        paterno = self.entries["paterno"].get().strip()
        
        if not nombre or not paterno:
            messagebox.showwarning("Error", "Nombre y apellido paterno son requeridos")
            return
            
        cap = cv2.VideoCapture(1)  
        if not cap.isOpened():
            messagebox.showerror("Error", "No se puede acceder a la cámara")
            return
            
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            cv2.imshow("Captura de Foto", frame)
            key = cv2.waitKey(1)
            # Tomar foto con la tecla espacio
            if key % 256 == 32:  
                self.foto_path = os.path.join(carpeta_fotos, f"{nombre}_{paterno}.jpg")
                cv2.imwrite(self.foto_path, frame)
                break
                
        cap.release()
        cv2.destroyAllWindows()
        
        if os.path.exists(self.foto_path):
            self.mostrar_foto()
    
    def mostrar_foto(self):
        imagen = Image.open(self.foto_path)
        imagen = imagen.resize((200, 200))
        img_tk = ImageTk.PhotoImage(imagen)
        self.label_foto.config(image=img_tk)
        self.label_foto.image = img_tk
    
    def guardar_estudiante(self):
        nombre = self.entries["nombre"].get().strip()
        paterno = self.entries["paterno"].get().strip()
        materno = self.entries["materno"].get().strip()
        carrera = self.entries["carrera"].get().strip()
        grupo = self.entries["grupo"].get().strip()
        
        campos = [nombre, paterno, materno, carrera, grupo, self.foto_path]
        if not all(campos):
            messagebox.showwarning("Error", "Todos los campos son obligatorios")
            return
        
        img = cv2.imread(self.foto_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
        
        if len(faces) == 0:
            messagebox.showerror("Error", "No se detectó ningún rostro en la foto")
            return
        
        (x, y, w, h) = faces[0]
        face_img = gray[y:y+h, x:x+w]
        face_path = self.foto_path.replace(".jpg", "_face.jpg")
        cv2.imwrite(face_path, face_img)
        
        estudiante = {
            "nombre": nombre,
            "apellido_paterno": paterno,
            "apellido_materno": materno,
            "carrera": carrera,
            "grupo": grupo,
            "foto": self.foto_path,
            "face_path": face_path
        }
        
        personas.insert_one(estudiante)
        messagebox.showinfo("Éxito", "Estudiante registrado correctamente")
    
    def train_recognizer(self):
        """Entrena el reconocedor LBPH con las imágenes de rostros almacenadas en la base de datos."""
        estudiantes = list(personas.find())
        if not estudiantes:
            return None
        
        faces = []
        labels = []
        self.label_to_name = {}
        label_id = 0
        for est in estudiantes:
            face_img_path = est.get("face_path")
            if face_img_path and os.path.exists(face_img_path):
                img = cv2.imread(face_img_path, cv2.IMREAD_GRAYSCALE)
                faces.append(img)
                labels.append(label_id)
                self.label_to_name[label_id] = f"{est['nombre']} {est['apellido_paterno']}"
                label_id += 1
        
        if faces and labels:
            recognizer = cv2.face.LBPHFaceRecognizer_create()
            recognizer.train(faces, np.array(labels))
            return recognizer
        else:
            return None
    
    def iniciar_asistencia_thread(self):
        thread = threading.Thread(target=self.iniciar_asistencia, daemon=True)
        thread.start()
    
    def iniciar_asistencia(self):
        grupo = self.entries["grupo"].get().strip()
        if not grupo:
            messagebox.showwarning("Error", "Debe especificar un grupo")
            return
        
        self.recognizer = self.train_recognizer()
        if self.recognizer is None:
            messagebox.showerror("Error", "No hay estudiantes registrados para entrenamiento")
            return
        
        cap = cv2.VideoCapture(1)
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
                
                label, confidence = self.recognizer.predict(face_roi_resized)
                
                if confidence < 70:
                    nombre = self.label_to_name.get(label, "Desconocido")
                    asistentes.add(nombre)
                    cv2.putText(frame, nombre, (x, y-10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                else:
                    cv2.putText(frame, "Desconocido", (x, y-10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
            
            cv2.imshow('Sistema de Asistencia', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cap.release()
        cv2.destroyAllWindows()
        
        if asistentes:
            # Registrar asistencia y enviar el reporte automáticamente al finalizar 1 minuto
            self.registrar_asistencia(asistentes, grupo)
            self.enviar_reporte(asistentes, grupo)
            messagebox.showinfo("Información", "El reporte se envió automáticamente. Si no lo has recibido, presiona el botón 'Enviar Reporte'.")
        else:
            messagebox.showinfo("Información", "No se detectó ningún asistente durante el periodo de asistencia.")
    
    def registrar_asistencia(self, asistentes, grupo):
        fecha = datetime.datetime.now()
        for asistente in asistentes:
            asistencias.insert_one({
                "nombre": asistente,
                "grupo": grupo,
                "fecha": fecha,
                "asistio": True
            })
        messagebox.showinfo("Asistencia Registrada", f"{len(asistentes)} estudiantes registrados")
    
    def enviar_reporte(self, asistentes, grupo):
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
                
            
            messagebox.showinfo("Éxito", "Reporte enviado al profesor. ")
        except Exception as e:
            messagebox.showerror("Error", f"Error enviando correo: {str(e)}")
    
    def enviar_reporte_manual(self):
        grupo = self.entries["grupo"].get().strip()
        if not grupo:
            messagebox.showwarning("Error", "Debe especificar un grupo para enviar el reporte")
            return
        
        start_of_day = datetime.datetime.combine(datetime.datetime.now().date(), datetime.time.min)
        registros = list(asistencias.find({
            "grupo": grupo,
            "fecha": {"$gte": start_of_day}
        }))
        if not registros:
            messagebox.showinfo("Información", "No se encontraron registros de asistencia para hoy en este grupo")
            return
      
        asistentes = set(reg["nombre"] for reg in registros)
        self.enviar_reporte(asistentes, grupo)

if __name__ == "__main__":
    root = tk.Tk()
    app = SistemaAsistencia(root)
    root.mainloop()
