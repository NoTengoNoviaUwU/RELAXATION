import tkinter as tk
from tkinter import ttk
from datetime import datetime
from PIL import Image, ImageTk  # Necesita instalar Pillow: pip install pillow
import serial  # Biblioteca para comunicación serial

# Configuración de la conexión serial
arduino = None
try:
    arduino = serial.Serial('COM8', 9600)  # Configuración de conexión en COM8 a 9600 baudios
    print("Conexión con Arduino establecida.")
except serial.SerialException:
    print("No se pudo conectar al Arduino. Verifica el puerto COM y la conexión.")

# Configuración de la ventana principal
root = tk.Tk()
root.title("Sistema de Monitoreo Completo")
root.geometry("1000x700")
root.configure(bg="black")  # Fondo negro

# Fuentes y configuración visual
heading_font = ("Staatliches", 18)
subheading_font = ("Montserrat", 10, "bold")
hover_heading_font = ("Staatliches", 20)
click_heading_font = ("Staatliches", 16)
log_title_font = ("Staatliches", 12)
log_subtitle_font = ("Montserrat", 8, "italic")
timer_subtitle_font = ("Staatliches", 10)
timer_font = ("Staatliches", 24, "bold")
text_color = "white"

# Variables y temporizadores
last_trigger_time = None
trigger_difference_var = tk.StringVar(value="0.00")

# Función para enviar un trigger al Arduino y actualizar el registro
def send_trigger(trigger):
    global last_trigger_time
    last_trigger_time = datetime.now()
    timestamp = last_trigger_time.strftime('%Y-%m-%d %H:%M:%S')

    # Enviar el trigger al Arduino solo si la conexión se estableció
    if arduino and arduino.is_open:
        arduino.write((trigger + '\n').encode())  # Enviar el trigger con salto de línea
        print(f"Trigger '{trigger}' enviado a Arduino.")  # Para depuración
    else:
        print("No se pudo enviar el trigger. Arduino no está conectado.")
    
    # Restaurar texto y colores originales en el cronómetro
    timer_subtitle_label.config(text="Tiempo desde el último trigger", fg="gray")
    timer_label.config(fg="white", text=trigger_difference_var.get())  # Mostrar los segundos

    # Actualizar el registro en la interfaz
    triggers_log_box.insert(tk.END, f"{trigger}\n", "title")
    triggers_log_box.insert(tk.END, f"Hora de envío: {timestamp}\n\n", "subtitle")
    triggers_log_box.see(tk.END)

# Función para actualizar el cronómetro de tiempo entre triggers
def update_trigger_difference():
    if last_trigger_time:
        elapsed_time = (datetime.now() - last_trigger_time).total_seconds()
        trigger_difference_var.set(f"{elapsed_time:.2f}")

        # Activar "Modo Intermitente" si han pasado más de 10 segundos
        if elapsed_time > 10:
            timer_subtitle_label.config(text="Han pasado 10 segundos desde el último trigger", fg="brown")
            timer_label.config(text="MODO INTERMITENTE ACTIVADO", fg="red")
        else:
            # Mostrar tiempo desde el último trigger si es menor a 10 segundos
            timer_label.config(text=trigger_difference_var.get(), fg="white")
    else:
        trigger_difference_var.set("0.00")  # Reinicia el tiempo a 0 si no hay trigger
    root.after(200, update_trigger_difference)  # Llamar a esta función cada 200 ms para una actualización más fluida

# Función para crear un "botón" personalizado con efectos de hover y clic, con tamaño fijo
def create_trigger_button(frame, display_name, trigger_name):
    # Crear un Frame que actúa como un botón con un tamaño fijo
    button_frame = tk.Frame(frame, bg="black", bd=0, relief="flat", width=200, height=60)
    button_frame.pack_propagate(False)  # Evitar que el frame cambie de tamaño con el contenido
    button_frame.pack(fill="x", padx=10, pady=(10, 0))

    # Nombre principal en Staatliches
    title_label = tk.Label(button_frame, text=display_name, font=heading_font, fg=text_color, bg="black")
    title_label.pack(anchor="center")

    # Subtítulo (trigger_name) en Montserrat
    subtitle_label = tk.Label(button_frame, text=trigger_name, font=subheading_font, fg="gray", bg="black")
    subtitle_label.pack(anchor="center")

    # Función para simular el comportamiento de un botón
    def on_click(event=None):
        send_trigger(trigger_name)

    # Efecto hover
    def on_enter(event):
        title_label.config(font=hover_heading_font)

    def on_leave(event):
        title_label.config(font=heading_font)

    # Efecto de clic
    def on_press(event):
        title_label.config(font=click_heading_font)

    def on_release(event):
        title_label.config(font=hover_heading_font)
        send_trigger(trigger_name)

    # Vincular eventos para el efecto hover y clic
    button_frame.bind("<Enter>", on_enter)
    button_frame.bind("<Leave>", on_leave)
    button_frame.bind("<ButtonPress-1>", on_press)
    button_frame.bind("<ButtonRelease-1>", on_release)
    title_label.bind("<Enter>", on_enter)
    title_label.bind("<Leave>", on_leave)
    title_label.bind("<ButtonPress-1>", on_press)
    title_label.bind("<ButtonRelease-1>", on_release)
    subtitle_label.bind("<Enter>", on_enter)
    subtitle_label.bind("<Leave>", on_leave)
    subtitle_label.bind("<ButtonPress-1>", on_press)
    subtitle_label.bind("<ButtonRelease-1>", on_release)

# Estilos de ttk
style = ttk.Style()
style.theme_use("default")
style.configure("TNotebook", background="black", borderwidth=0)
style.configure("TNotebook.Tab", background="black", foreground=text_color)
style.map("TNotebook.Tab", background=[("selected", "black")])
style.configure("TFrame", background="black")
style.configure("TLabelFrame", background="black", foreground=text_color)

# Frame principal para la estructura de las columnas
main_frame = tk.Frame(root, bg="black")
main_frame.pack(fill="both", expand=True, padx=10, pady=10)

# Frame de Esencias (columna izquierda)
esencias_frame = tk.LabelFrame(main_frame, text="ESENCIAS", font=heading_font, bg="black", fg=text_color)
esencias_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

# Crear "botones" para las esencias
create_trigger_button(esencias_frame, "ESENCIA NATURAL", "neutral_scent")
create_trigger_button(esencias_frame, "SÁNDALO", "sandalwood_scent")
create_trigger_button(esencias_frame, "MARINO", "marine_scent")

# Frame de LEDs (columna derecha)
leds_frame = tk.LabelFrame(main_frame, text="LEDS ESTADOS DE RELAJACIÓN", font=heading_font, bg="black", fg=text_color)
leds_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

# Crear "botones" para los estados de relajación de los LEDs
create_trigger_button(leds_frame, "RELAX BAJO", "low_relaxation")
create_trigger_button(leds_frame, "RELAX MEDIO", "medium_relaxation")
create_trigger_button(leds_frame, "RELAX ALTO", "high_relaxation")
create_trigger_button(leds_frame, "RELAX MÁXIMO", "very_high_relaxation")

# Configurar el grid para que las columnas se expandan uniformemente
main_frame.grid_columnconfigure(0, weight=1)
main_frame.grid_columnconfigure(1, weight=1)

# Sección del cronómetro de tiempo entre triggers
cronometro_frame = tk.LabelFrame(root, text="Cronómetro entre Triggers", font=heading_font, bg="black", fg=text_color)
cronometro_frame.pack(fill="x", padx=10, pady=10)

# Subtítulo "Tiempo desde el último trigger" y temporizador
timer_subtitle_label = tk.Label(cronometro_frame, text="Tiempo desde el último trigger", font=timer_subtitle_font, fg="gray", bg="black")
timer_subtitle_label.pack()

# Temporizador
timer_label = tk.Label(cronometro_frame, textvariable=trigger_difference_var, font=timer_font, fg=text_color, bg="black")
timer_label.pack()

# Registro de triggers enviados con fondo negro
triggers_log_frame = tk.LabelFrame(root, text="Registro de Triggers", font=heading_font, fg=text_color, bg="black", labelanchor="n")
triggers_log_frame.pack(fill="both", expand=True, padx=10, pady=10)

# Caja de texto para registro de triggers
triggers_log_box = tk.Text(triggers_log_frame, height=10, font=log_title_font, wrap="word", bg="black", fg=text_color, bd=0, relief="flat")
triggers_log_box.pack(fill="both", expand=True, padx=5, pady=5)

# Configurar estilos de texto en el registro de triggers
triggers_log_box.tag_configure("title", font=log_title_font, foreground=text_color, justify="center")
triggers_log_box.tag_configure("subtitle", font=log_subtitle_font, foreground="gray", justify="center")

# Iniciar el cronómetro de tiempo entre triggers
update_trigger_difference()

# Configurar para cerrar la conexión serial al salir
root.protocol("WM_DELETE_WINDOW", lambda: (arduino.close(), root.destroy()) if arduino and arduino.is_open else root.destroy())

root.mainloop()
