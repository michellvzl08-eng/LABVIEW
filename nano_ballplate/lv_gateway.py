"""
Pasarela LabVIEW <-> OPC UA (LabVIEW 2016 no trae cliente OPC UA).

  LabVIEW --TCP (texto, puerto 5020)--> lv_gateway.py --cliente OPC UA--> opc_server.py

Asi los datos del SCADA pasan realmente por el servidor OPC UA, y cualquier otro cliente
OPC UA (UaExpert, etc.) ve exactamente lo mismo que LabVIEW.

Mensajes (texto ASCII, terminados en CRLF):
  Gateway -> LabVIEW (20 Hz):  D,<BolaX>,<BolaY>,<MotorX>,<MotorY>,<Estado>
  LabVIEW -> Gateway:          W,<SetpointX>,<SetpointY>,<Marcha 0/1>,<Emergencia 0/1>
Unidades: posiciones en decimas de mm, motores en pasos, Estado 0=paro 1=marcha 2=emergencia.

Uso (con opc_server.py o ballplate.py ya corriendo):  python lv_gateway.py
"""
import asyncio

from asyncua import Client

OPC_URL = "opc.tcp://localhost:4840/ballplate"
NS_URI = "urn:ballplate:scada"
TCP_PORT = 5020
READ_NODES = ("BolaX", "BolaY", "MotorX", "MotorY", "Estado")


async def main():
    async with Client(OPC_URL) as ua:
        idx = await ua.get_namespace_index(NS_URI)
        folder = await ua.nodes.objects.get_child([f"{idx}:Planta"])
        n = {k: await folder.get_child([f"{idx}:{k}"]) for k in
             READ_NODES + ("SetpointX", "SetpointY", "Marcha", "Emergencia")}

        async def handle(reader, writer):
            peer = writer.get_extra_info("peername")
            print("LabVIEW conectado:", peer)

            async def sender():
                while True:
                    vals = [int(await n[k].read_value()) for k in READ_NODES]
                    writer.write(("D," + ",".join(map(str, vals)) + "\r\n").encode())
                    await writer.drain()
                    await asyncio.sleep(0.05)

            task = asyncio.create_task(sender())
            try:
                while True:
                    line = await reader.readline()
                    if not line:
                        break
                    p = line.decode("ascii", errors="ignore").strip().split(",")
                    if p[0] == "W" and len(p) == 5:
                        try:
                            await n["SetpointX"].write_value(int(float(p[1])))
                            await n["SetpointY"].write_value(int(float(p[2])))
                            await n["Marcha"].write_value(p[3].strip() == "1")
                            await n["Emergencia"].write_value(p[4].strip() == "1")
                        except ValueError:
                            pass
            except (ConnectionError, asyncio.CancelledError):
                pass
            finally:
                task.cancel()
                # Seguridad: si LabVIEW se desconecta, paro
                try:
                    await n["Marcha"].write_value(False)
                except Exception:
                    pass
                writer.close()
                print("LabVIEW desconectado")

        server = await asyncio.start_server(handle, "0.0.0.0", TCP_PORT)
        print(f"Pasarela lista: TCP {TCP_PORT} <-> {OPC_URL}")
        async with server:
            await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
