import serial
from pylsl import StreamInlet, resolve_stream
from threading import Lock, Thread
import time
import datetime
import io
import csv
import logging

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('device_controller.log'),
        logging.StreamHandler()
    ]
)

class MultisensoryDeviceController:
    def __init__(self, com_port='COM8', baud_rate=9600):
        self.com_port = com_port
        self.baud_rate = baud_rate
        self.serial_lock = Lock()
        self.ser = None
        self.last_ping_time = time.time()
        self.ping_interval = 5
        self.running = True
        
        # Configuración de archivo en memoria para logging
        self.memory_file = io.StringIO()
        self.csv_writer = csv.writer(self.memory_file)
        self.csv_writer.writerow(['Timestamp', 'Marker', 'Type', 'Response'])

        # Estado actual de los dispositivos
        self.current_led_state = None
        self.current_aroma_state = None

        # Inicializar conexiones
        if not self.setup_serial():
            logging.error("No se pudo establecer la conexión serial")
            raise ConnectionError("Fallo en la conexión serial")
        
        if not self.setup_lsl_streams():
            logging.error("No se pudieron establecer los streams LSL")
            raise ConnectionError("Fallo en la conexión LSL")

    def setup_serial(self):
        """Configura la conexión serial con reintentos."""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                self.ser = serial.Serial(self.com_port, self.baud_rate, timeout=1)
                logging.info(f"Conexión serial establecida en {self.com_port} a {self.baud_rate} baudios")
                return True
            except serial.SerialException as e:
                logging.error(f'Intento {attempt + 1}/{max_attempts} - Error al abrir el puerto serial: {e}')
                if attempt < max_attempts - 1:
                    time.sleep(2)
        return False

    def setup_lsl_streams(self):
        """Configura las conexiones LSL con reintentos."""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                logging.info("Buscando streams LSL...")
                eeg_streams = resolve_stream('name', 'eeg_stream')
                relaxation_streams = resolve_stream('name', 'relaxation_stream')

                if not eeg_streams or not relaxation_streams:
                    raise RuntimeError("No se encontraron todos los streams necesarios")

                self.eeg_inlet = StreamInlet(eeg_streams[0])
                self.relaxation_inlet = StreamInlet(relaxation_streams[0])
                logging.info("Conexión establecida con ambos streams LSL")
                return True
            except Exception as e:
                logging.error(f'Intento {attempt + 1}/{max_attempts} - Error al configurar streams LSL: {e}')
                if attempt < max_attempts - 1:
                    time.sleep(2)
        return False

    def send_to_arduino(self, trigger_value):
        """Envía comandos al Arduino con verificación de respuesta."""
        if not self.ser or not self.ser.is_open:
            logging.error("Error: El puerto serial no está abierto.")
            return False

        try:
            with self.serial_lock:
                mensaje = f'{trigger_value}\n'
                self.ser.write(mensaje.encode('utf-8'))
                logging.info(f'Comando enviado al Arduino: {mensaje.strip()}')

                # Esperar y verificar respuesta
                for _ in range(3):  # 3 intentos de lectura
                    if self.ser.in_waiting > 0:
                        respuesta = self.ser.readline().decode('utf-8').strip()
                        logging.info(f"Respuesta del Arduino: {respuesta}")
                        self.log_event(trigger_value, "Command", respuesta)
                        return True
                    time.sleep(0.5)

                logging.warning("No se recibió respuesta del Arduino")
                return False

        except serial.SerialException as e:
            logging.error(f'Error de comunicación serial: {e}')
            return False

    def log_event(self, marker, type_event, response):
        """Registra eventos en el archivo CSV en memoria."""
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        self.csv_writer.writerow([timestamp, marker, type_event, response])
        self.memory_file.flush()

    def process_led_trigger(self, trigger):
        """Procesa triggers para control de LEDs."""
        if trigger == self.current_led_state:
            return  # Evitar comandos redundantes

        if trigger in ["low_relaxation", "medium_relaxation", "high_relaxation", "very_high_relaxation"]:
            if self.send_to_arduino(trigger):
                self.current_led_state = trigger
                logging.info(f"Estado LED actualizado a: {trigger}")
        else:
            logging.warning(f"Trigger LED no reconocido: {trigger}")

    def process_aroma_trigger(self, trigger):
        """Procesa triggers para control de aromas."""
        if trigger == self.current_aroma_state:
            return  # Evitar comandos redundantes

        if trigger in ["neutral_scent", "sandalwood_scent", "marine_scent", "herbal_scent"]:
            if self.send_to_arduino(trigger):
                self.current_aroma_state = trigger
                logging.info(f"Estado de aroma actualizado a: {trigger}")
        else:
            logging.warning(f"Trigger de aroma no reconocido: {trigger}")

    def maintain_connection(self):
        """Mantiene la conexión con el Arduino mediante pings periódicos."""
        while self.running:
            try:
                current_time = time.time()
                if current_time - self.last_ping_time >= self.ping_interval:
                    if self.send_to_arduino("ping"):
                        self.last_ping_time = current_time
                    else:
                        logging.warning("Fallo en ping, intentando reconectar...")
                        self.setup_serial()
                time.sleep(1)
            except Exception as e:
                logging.error(f"Error en maintain_connection: {e}")

    def run(self):
        """Ejecuta el controlador principal."""
        # Iniciar thread para mantener la conexión
        ping_thread = Thread(target=self.maintain_connection)
        ping_thread.daemon = True
        ping_thread.start()

        logging.info("Iniciando procesamiento de streams...")
        try:
            while self.running:
                # Procesar stream de EEG para LEDs
                eeg_sample, _ = self.eeg_inlet.pull_sample(timeout=0.1)
                if eeg_sample:
                    self.process_led_trigger(eeg_sample[0])

                # Procesar stream de Relaxation para aromas
                relaxation_sample, _ = self.relaxation_inlet.pull_sample(timeout=0.1)
                if relaxation_sample:
                    self.process_aroma_trigger(relaxation_sample[0])

                time.sleep(0.1)

        except KeyboardInterrupt:
            logging.info("Sistema detenido manualmente")
        except Exception as e:
            logging.error(f"Error en el bucle principal: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        """Limpia y cierra las conexiones."""
        self.running = False
        if self.ser and self.ser.is_open:
            # Enviar comando de apagado a Arduino si es necesario
            self.send_to_arduino("shutdown")
            self.ser.close()
            
        logging.info("Guardando log de eventos...")
        try:
            # Guardar el log en un archivo
            with open('device_events.csv', 'w', newline='') as f:
                f.write(self.memory_file.getvalue())
            logging.info("Log de eventos guardado en 'device_events.csv'")
        except Exception as e:
            logging.error(f"Error al guardar el log: {e}")
        
        self.memory_file.close()
        logging.info("Sistema apagado correctamente")

def main():
    try:
        logging.info("Iniciando MultisensoryDeviceController...")
        controller = MultisensoryDeviceController()
        controller.run()
    except KeyboardInterrupt:
        logging.info("Inicio interrumpido por el usuario")
    except Exception as e:
        logging.error(f"Error durante la inicialización: {e}")

if __name__ == "__main__":
    main()