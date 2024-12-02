import numpy as np
from scipy.signal import butter, lfilter
from pylsl import StreamInlet, resolve_stream, StreamOutlet, StreamInfo
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Input
from tensorflow.keras.optimizers import Adam
import tensorflow as tf
import time

# Configuración para reducir mensajes de TensorFlow
tf.get_logger().setLevel('ERROR')

class RealTimeRelaxationExperiment:
    def __init__(self, participant_id, num_videos, fs=100):
        self.participant_id = participant_id
        self.num_videos = num_videos
        self.video_scores = {}
        self.fs = fs
        
        # Stream original para marcadores de video
        self.marker_outlet = self.setup_marker_stream()
        
        # Stream para enviar estados de LEDs
        self.eeg_outlet = self.setup_eeg_stream()
        
        # Stream para enviar estados de aromas
        self.relaxation_outlet = self.setup_relaxation_stream()
        
        # Stream para Unity (si es necesario)
        self.unity_outlet = self.setup_unity_stream()
        
        # Inlet para datos EEG
        self.inlet = self.setup_power_inlet()
        
        self.model = self.create_model()
        self.current_aroma = None
        self.current_led_state = None

    def setup_marker_stream(self):
        info = StreamInfo('bWell.Markers', 'Markers', 1, 0, 'string', 'unique_id')
        return StreamOutlet(info)

    def setup_eeg_stream(self):
        info = StreamInfo('eeg_stream', 'Markers', 1, 0, 'string', 'eeg_id')
        return StreamOutlet(info)

    def setup_relaxation_stream(self):
        info = StreamInfo('relaxation_stream', 'Markers', 1, 0, 'string', 'relaxation_id')
        return StreamOutlet(info)

    def setup_unity_stream(self):
        info = StreamInfo('unity_stream', 'Markers', 1, 0, 'string', 'unity_id')
        return StreamOutlet(info)

    def setup_power_inlet(self):
        streams = resolve_stream('name', 'AURA_Power')
        if streams:
            inlet = StreamInlet(streams[0])
            return inlet
        else:
            raise RuntimeError("No EEG power stream found with name 'AURA_Power'.")

    def create_model(self):
        model = Sequential([
            Input(shape=(16,)),
            Dense(32, activation='relu'),
            Dense(16, activation='relu'),
            Dense(1, activation='sigmoid')
        ])
        model.compile(optimizer=Adam(learning_rate=0.001), loss='binary_crossentropy', metrics=['accuracy'])
        return model

    def reset_model(self):
        self.model = self.create_model()

    def send_trigger(self, trigger_name):
        """Envía triggers a todos los streams relevantes."""
        # Enviar al stream de marcadores de video
        self.marker_outlet.push_sample([trigger_name])
        print(f"Video marker sent: {trigger_name}")

        # Si el trigger contiene un score, actualizar LED y aroma
        if "score:" in trigger_name:
            try:
                score = float(trigger_name.split(":")[-1])
                self.send_relaxation_state(score)
            except ValueError:
                print(f"No se pudo extraer score del trigger: {trigger_name}")

    def send_relaxation_state(self, relaxation_score):
        """Envía el estado de relajación para LEDs y aromas."""
        # Determinar y enviar estado de LED
        if relaxation_score > 0.9:
            led_state = "very_high_relaxation"
        elif relaxation_score > 0.8:
            led_state = "high_relaxation"
        elif relaxation_score > 0.5:
            led_state = "medium_relaxation"
        else:
            led_state = "low_relaxation"

        if led_state != self.current_led_state:
            self.current_led_state = led_state
            self.eeg_outlet.push_sample([led_state])
            print(f"LED state sent: {led_state}")
            
            # También enviar al stream de Unity
            self.unity_outlet.push_sample([led_state])

        # Determinar y enviar estado de aroma
        if relaxation_score > 0.9:
            aroma = "sandalwood_scent"
        elif relaxation_score > 0.7:
            aroma = "marine_scent"
        else:
            aroma = "neutral_scent"

        if aroma != self.current_aroma:
            self.current_aroma = aroma
            self.relaxation_outlet.push_sample([aroma])
            print(f"Aroma state sent: {aroma}")

    def run_trial(self, video_index, duration=30):
        self.reset_model()
        time.sleep(1)

        # Enviar trigger para el inicio del video y el fade_in
        self.send_trigger(f"start_video_{video_index}")
        time.sleep(1)  # Espera breve antes de enviar fade_in
        self.send_trigger("fade_in")

        # Recolectar datos de EEG durante la duración del video menos tiempo para fade_out
        fade_out_time = 2  # Segundos antes de que termine el video para enviar fade_out
        eeg_data = self.collect_power_data(duration=duration - fade_out_time)

        # Calcular puntaje de relajación y almacenar resultado
        relaxation_score = self.calculate_interval_based_relaxation(eeg_data)
        self.video_scores[video_index] = relaxation_score
        print(f"Video {video_index} relaxation score (Alpha & Theta in Parietal/Frontal): {relaxation_score}")

        # Enviar estados de relajación para LEDs y aromas
        self.send_relaxation_state(relaxation_score)

        # Enviar trigger fade_out antes de que termine el video
        self.send_trigger("fade_out")
        time.sleep(fade_out_time)  # Espera para que termine el video después del fade_out

        # Enviar el resultado del puntaje de relajación de este video como trigger
        self.send_trigger(f"video_{video_index}_score:{relaxation_score}")

    def collect_power_data(self, duration=30):
        samples = []
        start_time = time.time()

        print(f"Collecting EEG data for {duration} seconds...")
        while time.time() - start_time < duration:
            sample, timestamp = self.inlet.pull_sample()
            if sample:
                alpha_theta_data = sample[16:24] + sample[8:16]
                if not np.isnan(alpha_theta_data).any() and np.all(np.isfinite(alpha_theta_data)):
                    samples.append(alpha_theta_data)
        return np.array(samples) if samples else np.zeros((1, 16))

    def calculate_bandpower(self, data, lowcut, highcut):
        nyquist = 0.5 * self.fs
        low = lowcut / nyquist
        high = highcut / nyquist
        b, a = butter(4, [low, high], btype='band')
        filtered_data = lfilter(b, a, data)
        bandpower = np.mean(filtered_data ** 2, axis=0)
        return bandpower

    def calculate_weighted_relaxation_score(self, eeg_data):
        frontal_indices = [0, 1, 2]
        central_indices = [3, 4]
        parietal_indices = [5, 6, 7]

        frontal_data = eeg_data[:, frontal_indices] * 1.0
        central_data = eeg_data[:, central_indices] * 1.2
        parietal_data = eeg_data[:, parietal_indices] * 1.5

        weighted_data = np.concatenate([frontal_data, central_data, parietal_data], axis=1)
        return weighted_data.mean(axis=1)

    def calculate_interval_based_relaxation(self, eeg_data):
        interval_duration = 5
        num_intervals = eeg_data.shape[0] // (interval_duration * self.fs)
        interval_scores = []

        for i in range(num_intervals):
            start = i * interval_duration * self.fs
            end = (i + 1) * interval_duration * self.fs
            interval_data = eeg_data[start:end, :16]
            interval_data = interval_data.mean(axis=0).reshape(1, -1)

            labels = np.ones((interval_data.shape[0], 1))
            history = self.model.fit(interval_data, labels, epochs=1, batch_size=5, verbose=0)
            loss = history.history['loss'][0]
            accuracy = history.history['accuracy'][0]
            print(f"Interval {i + 1}/{num_intervals} - Loss: {loss:.4f}, Accuracy: {accuracy:.4f}")

            score = self.model.predict(interval_data)
            interval_scores.append(np.mean(score))

        return np.median(interval_scores)

    def calculate_relaxation_score(self, eeg_data):
        weighted_data = self.calculate_weighted_relaxation_score(eeg_data)
        theta_power = self.calculate_bandpower(weighted_data, 4, 8)
        alpha_power = self.calculate_bandpower(weighted_data, 8, 12)
        relaxation_score = 0.5 * theta_power + 0.5 * alpha_power
        return relaxation_score

    def select_best_video(self):
        best_video = max(self.video_scores, key=self.video_scores.get)
        best_score = self.video_scores[best_video]
        print(f"Best video selected: {best_video} with score {best_score}")
        
        # Enviar el resultado final del mejor video seleccionado
        self.send_trigger(f"best_video_{best_video}_score:{best_score}")
        return best_video

    def play_best_video(self, video_index, duration=90):
        """Reproduce el mejor video con todos los triggers necesarios."""
        time.sleep(1)

        # Activar LED y aroma correspondientes al mejor video
        best_score = self.video_scores[video_index]
        self.send_relaxation_state(best_score)

        # Enviar trigger para el inicio del video y el fade_in
        self.send_trigger(f"start_video_{video_index}")
        time.sleep(1)
        self.send_trigger("fade_in")

        # Duración del video menos el tiempo para enviar fade_out
        fade_out_time = 2
        time.sleep(duration - fade_out_time)

        # Enviar trigger fade_out antes de que termine el video
        self.send_trigger("fade_out")
        time.sleep(fade_out_time)

    def start_experiment(self):
        input("Presiona Enter para comenzar el experimento...")
        for i in range(1, self.num_videos + 1):
            self.run_trial(i, duration=30)
            if i < self.num_videos:
                print("Taking a short break before the next video...")
                time.sleep(2)
        best_video = self.select_best_video()
        self.play_best_video(best_video, duration=90)

# Ejecución del sistema
if __name__ == "__main__":
    try:
        experiment = RealTimeRelaxationExperiment(participant_id='P001', num_videos=5)
        experiment.start_experiment()
    except KeyboardInterrupt:
        print("\nExperimento interrumpido por el usuario.")
    except Exception as e:
        print(f"\nError durante el experimento: {e}")
    finally:
        print("\nFinalizando experimento...")
