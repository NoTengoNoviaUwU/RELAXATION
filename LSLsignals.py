from pylsl import resolve_streams

def detectar_senales_lsl():
    # Buscar todas las señales LSL disponibles en la red
    streams = resolve_streams()

    # Imprimir información sobre cada señal detectada
    for i, stream in enumerate(streams, start=1):
        print(f"Señal {i}:")
        print(f"  Nombre: {stream.name()}")
        print(f"  Tipo: {stream.type()}")
        print(f"  Canales: {stream.channel_count()}")
        print(f"  Frecuencia de muestreo: {stream.nominal_srate()}")
        print(f"  ID de dispositivo: {stream.source_id()}")

# Llamar a la función para detectar señales LSL
detectar_senales_lsl()
