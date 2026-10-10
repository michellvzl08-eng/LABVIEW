"""Muestra SetpointX / SetpointY / Marcha del servidor OPC UA cada 0.5 s (solo lectura)."""
import asyncio
from asyncua import Client

URL = "opc.tcp://localhost:4840/ballplate"


async def main():
    async with Client(URL) as c:
        idx = await c.get_namespace_index("urn:ballplate:scada")
        planta = await c.nodes.objects.get_child([f"{idx}:Planta"])
        nodos = {n: await planta.get_child([f"{idx}:{n}"]) for n in ("SetpointX", "SetpointY", "Marcha")}
        print("Ctrl+C para salir")
        while True:
            v = {n: await nodo.read_value() for n, nodo in nodos.items()}
            print(f"SetpointX={v['SetpointX']:>8}  SetpointY={v['SetpointY']:>8}  Marcha={v['Marcha']}")
            await asyncio.sleep(0.5)


try:
    asyncio.run(main())
except KeyboardInterrupt:
    pass
