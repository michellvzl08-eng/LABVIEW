"""
Servidor OPC UA para el SCADA Ball-on-Plate (asyncua).
Corre en un hilo aparte para no bloquear el lazo de vision/control.

Nodos (namespace "BallPlate", carpeta "Planta"):
  Escribe LabVIEW/cliente:  SetpointX, SetpointY (decimas de mm), Marcha, Emergencia (bool)
  Escribe Python:           BolaX, BolaY (decimas de mm), MotorX, MotorY (pasos), Estado (0/1/2)

Prueba solo el servidor:   python opc_server.py
Cliente de prueba gratis:  UaExpert -> opc.tcp://localhost:4840/ballplate
"""
import asyncio
import threading
import time

from asyncua import Server, ua

ENDPOINT = "opc.tcp://0.0.0.0:4840/ballplate"
NAMESPACE = "urn:ballplate:scada"

# Estado compartido (lo lee/escribe el lazo de control)
shared = {
    "SetpointX": 0, "SetpointY": 0, "Marcha": False, "Emergencia": False,   # vienen del SCADA
    "BolaX": 0, "BolaY": 0, "MotorX": 0, "MotorY": 0, "Estado": 0,          # los publica Python
}
_lock = threading.Lock()
_WRITABLE = ("SetpointX", "SetpointY", "Marcha", "Emergencia")
_PUBLISHED = ("BolaX", "BolaY", "MotorX", "MotorY", "Estado")


def get(name):
    with _lock:
        return shared[name]


def put(**kw):
    with _lock:
        shared.update(kw)


async def _run(stop_evt):
    server = Server()
    await server.init()
    server.set_endpoint(ENDPOINT)
    server.set_server_name("BallPlate OPC UA")
    idx = await server.register_namespace(NAMESPACE)
    folder = await server.nodes.objects.add_folder(idx, "Planta")

    nodes = {}
    for name, init in shared.items():
        nodes[name] = await folder.add_variable(idx, name, init)
        if name in _WRITABLE:
            await nodes[name].set_writable()

    async with server:
        while not stop_evt.is_set():
            # lo que escribio el SCADA -> estado compartido
            for name in _WRITABLE:
                v = await nodes[name].read_value()
                put(**{name: v})
            # lo que publica Python -> nodos
            for name in _PUBLISHED:
                await nodes[name].write_value(get(name))
            await asyncio.sleep(0.05)   # 20 Hz hacia el SCADA


_stop = threading.Event()
_thread = None


def start():
    global _thread

    def runner():
        asyncio.run(_run(_stop))

    _thread = threading.Thread(target=runner, daemon=True)
    _thread.start()


def stop():
    _stop.set()
    if _thread:
        _thread.join(timeout=2)


if __name__ == "__main__":
    start()
    print(f"Servidor OPC UA en {ENDPOINT}  (Ctrl+C para salir)")
    t = 0.0
    try:
        while True:
            # demo: bola simulada en circulo para probar el SCADA
            import math
            put(BolaX=int(300 * math.cos(t)), BolaY=int(300 * math.sin(t)), Estado=1 if get("Marcha") else 0)
            t += 0.1
            time.sleep(0.05)
    except KeyboardInterrupt:
        stop()
