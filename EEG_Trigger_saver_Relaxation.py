import pylsl
import csv
import os
from datetime import datetime
import pandas as pd

# Parámetros para los cálculos de engagement
CURRENT_ENGAGEMENT_THRESHOLD = 0.5
AVG_ENGAGEMENT_THRESHOLD = 0.5

def is_colon_trigger(string):
    """Verifica si un trigger contiene dos puntos (:) para identificar comandos específicos."""
    return ':' in string

def initialize_keyboard_stream():
    """Inicializa y conecta con el stream 'relaxation_stream'."""
    print("Connecting to relaxation and unity streams...")
    stream_markers = pylsl.resolve_stream('name', 'relaxation_stream')
    unity_streams = pylsl.resolve_stream('name', 'unity_stream')

    if not stream_markers:
        print("No se encontró el stream 'relaxation_stream'. Asegúrate de que esté activo.")
        return None
    if not unity_streams:
        print("No se encontró el stream 'unity_stream'. Asegúrate de que esté activo.")
        return None

    inlet_markers = pylsl.StreamInlet(stream_markers[0])
    unity_inlet = pylsl.StreamInlet(unity_streams[0])
    print("Connected to both relaxation and unity streams!")
    return inlet_markers, unity_inlet

def calcular_cognitive_engagement(df_real_time):
    """Calcula el compromiso cognitivo usando las bandas de Alpha y Theta."""
    alphas = df_real_time.iloc[:, 6:8].mean(axis=1)
    thetas = df_real_time.iloc[:, 3:5].mean(axis=1)
    df_real_time['CEng'] = thetas / alphas
    return df_real_time

def esperar_stream():
    """Monitorea los streams y guarda los datos junto con triggers y engagement en sesiones activas."""
    canales = pylsl.resolve_stream('name', 'AURAKalmanFilteredEEG')
    canales_EEG = pylsl.resolve_stream('name', 'AURAPSD')
    canales_triggers = pylsl.resolve_stream('name', 'relaxation_stream')
    canales_eeg_stream = pylsl.resolve_stream('name', 'eeg_stream')

    if not (canales and canales_EEG and canales_triggers and canales_eeg_stream):
        print("Error: Asegúrate de que todos los streams necesarios estén activos.")
        return

    entrada = pylsl.StreamInlet(canales[0])
    entrada_EEG = pylsl.StreamInlet(canales_EEG[0])
    entrada_triggers = pylsl.StreamInlet(canales_triggers[0])
    entrada_eeg_stream = pylsl.StreamInlet(canales_eeg_stream[0])

    inlet_markers, unity_inlet = initialize_keyboard_stream()
    print("Esperando datos desde los streams.")

    grabando = False
    archivo_csv = None
    writer = None
    participant_id = ""
    folder_path = "participants"
    session_name = ""
    archivo_csv = None
    archivo_eeg_csv = None
    writer_eeg = None
    df_real_time = pd.DataFrame()
    engagement_values = []

    while True:
        sample, timestamp = entrada.pull_sample()
        sample_EEG, timestamp_EEG = entrada_EEG.pull_sample()        
        triggers, _ = entrada_triggers.pull_sample(0)
        eeg_triggers, _ = entrada_eeg_stream.pull_sample(0)

        if unity_inlet:
            markers, _ = unity_inlet.pull_sample(0)
            marker_label = markers[0] if markers else "0"
        else:
            marker_label = "0"

        # Procesar comandos de sesión desde los triggers
        if triggers:
            trigger_text = str(triggers[0])
            if is_colon_trigger(trigger_text):
                command, value = trigger_text.split(":")

                if command == "participant_id":
                    participant_id = value
                    folder_path = os.path.join("participants", participant_id)
                    os.makedirs(folder_path, exist_ok=True)
                    print(f"Directorio '{folder_path}' creado o encontrado.")
                    unity_inlet = initialize_keyboard_stream()
                
                elif command == "start_session" and not grabando:
                    session_name = value
                    grabando = True
                    now_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    csv_path = os.path.join(folder_path, f"{session_name}_{now_str}.csv")
                    archivo_csv = open(csv_path, "w", newline="")
                    writer = csv.writer(archivo_csv)
                    writer.writerow(['Timestamp'] + [f"Sample{i}" for i in range(len(sample))] + 
                                    ['Trigger', 'Marker', 'EEG_Trigger', 'Current Engagement', 'Avg Engagement', 'Relaxed'])
                    print(f"Grabación iniciada: {session_name}")

                elif command == "end_session" and grabando:
                    grabando = False
                    archivo_csv.close()
                    print(f"Grabación terminada: {session_name}")
                
        if grabando:
            df_real_time = pd.concat([df_real_time, pd.DataFrame([sample])], ignore_index=True)
            if len(df_real_time) > 2:
                df_engagement = calcular_cognitive_engagement(df_real_time)
                current_engagement = df_engagement['CEng'].iloc[-1]
                engagement_values.append(current_engagement)
                avg_engagement = sum(engagement_values) / len(engagement_values)
                relaxed = avg_engagement < AVG_ENGAGEMENT_THRESHOLD
                writer.writerow([timestamp] + sample + [str(triggers), marker_label, str(eeg_triggers), 
                              current_engagement, avg_engagement, relaxed])

esperar_stream()
