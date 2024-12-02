from pylsl import StreamInlet, resolve_stream, StreamInfo, StreamOutlet
import time
import os
import numpy as np
from scipy.signal import welch
import matplotlib.pyplot as plt

# Configura matplotlib para el modo interactivo
plt.ion()
ruta_codigo1 = "LSL_filter_raw_data.py"
fs = 100  # Frecuencia de muestreo en Hz
nperseg = 100  # Número de puntos por segmento para Welch's method
buffer_size = fs * 0.4  # Tamaño del buffer (0.4 segundos de datos)
buffer = np.empty((0, 8))  # Asumiendo 8 electrodos

# Resolver el stream de EEG
os.system(f"start cmd /c python {ruta_codigo1}")
time.sleep(5)
print("AURAFilteredEEG")
print("looking for an EEG stream...")
streams = resolve_stream('name', 'AURAKalmanFilteredEEG')
inlet = StreamInlet(streams[0])

# Crear un nuevo stream para enviar los valores de PSD
info_psd = StreamInfo('AURAPSD', 'PSD', 5 * buffer.shape[1], fs, 'float32', 'myuid34234')
outlet_psd = StreamOutlet(info_psd)

# Captura de datos
print("Iniciando captura...")
while True:
    sample, timestamp = inlet.pull_sample()
    buffer = np.vstack([buffer, sample])

    if len(buffer) >= buffer_size:
        psd_values = []

        # Calcular PSD para cada electrodo
        for i in range(buffer.shape[1]):
            nperseg_adjusted = min(len(buffer[:, i]), nperseg)  # Adjust nperseg to be the minimum of input length or specified nperseg
            freqs, psd = welch(buffer[:, i], fs, nperseg=nperseg_adjusted)
            psd_values.append(np.mean(psd[(freqs >= 1) & (freqs <= 4)]))  # Delta
            psd_values.append(np.mean(psd[(freqs >= 4) & (freqs <= 8)]))  # Theta
            psd_values.append(np.mean(psd[(freqs >= 8) & (freqs <= 13)]))  # Alpha
            psd_values.append(np.mean(psd[(freqs >= 13) & (freqs <= 30)]))  # Beta
            psd_values.append(np.mean(psd[(freqs >= 30) & (freqs <= 100)]))  # Gamma

        # Envía los valores de PSD a través del outlet LSL
        outlet_psd.push_sample(psd_values)
        time.sleep(0.05)

        # Limpiar el buffer para la siguiente captura
        buffer = np.empty((0, 8))

        # Imprimir los valores de PSD (opcional)
        print("PSD values sent:", psd_values)
