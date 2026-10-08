"""
Cliente OPC UA de prueba (sustituto de UaExpert).
Con opc_server.py corriendo en otra terminal, ejecuta:  python opc_cliente_prueba.py
Muestra los nodos de la carpeta Planta y, a los 3 s, escribe Marcha=True y SetpointX=100.
"""
import asyncio

from asyncua import Client

URL = "opc.tcp://localhost:4840/ballplate"
NS = "urn:ballplate:scada"
NODOS = ("BolaX", "BolaY", "MotorX", "MotorY", "Estado",
         "SetpointX", "SetpointY", "Marcha", "Emergencia")


async def main():
    async with Client(URL) as c:
        idx = await c.get_namespace_index(NS)
        carpeta = await c.nodes.objects.get_child([f"{idx}:Planta"])
        n = {k: await carpeta.get_child([f"{idx}:{k}"]) for k in NODOS}
        print("Conectado a", URL)
        for i in range(30):
            if i == 15:
                await n["Marcha"].write_value(True)
                await n["SetpointX"].write_value(100)
                print(">>> Escribi Marcha=True y SetpointX=100")
            vals = {k: await n[k].read_value() for k in NODOS}
            print(" | ".join(f"{k}={v}" for k, v in vals.items()))
            await asyncio.sleep(0.2)


asyncio.run(main())
