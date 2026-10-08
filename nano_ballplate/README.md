# Ball-on-Plate SCADA

Proyecto Final de Implementación de Sistemas de Control (Clave 4666), UNISON.
Control de la posición de una bola sobre un plato basculante con 2 motores NEMA 17.

```
Webcam C270 ──► ballplate.py (OpenCV + PID) ──USB serial──► Arduino Nano ──► 2x A4988 ──► 2x NEMA 17
                     │
                     └──► servidor OPC UA (opc_server.py, puerto 4840)
                                   ▲
                                   │ cliente OPC UA
                            lv_gateway.py ──TCP 5020──► LabVIEW (SCADA)
```

Todos los datos del SCADA pasan por OPC UA. LabVIEW 2016 no trae cliente OPC UA, por eso
`lv_gateway.py` hace de puente: habla OPC UA hacia el servidor y TCP de texto hacia LabVIEW.

---

## Archivos de esta carpeta

| Archivo | Qué hace |
|---|---|
| `ballplate.py` | Programa principal. Lee la cámara, detecta la bola, calcula el PID, manda los pasos al Nano y publica todo por OPC UA. **Arranca el servidor OPC UA por dentro.** |
| `opc_server.py` | Servidor OPC UA (asyncua). Se puede correr solo para pruebas: simula una bola girando en círculo. |
| `opc_cliente_prueba.py` | Cliente OPC UA de prueba (sustituye a UaExpert). Lee los nodos y escribe `Marcha` y `SetpointX`. |
| `lv_gateway.py` | Puente LabVIEW ↔ OPC UA (TCP puerto 5020). Necesita un servidor OPC UA corriendo. |
| `nano_ballplate.ino` | Firmware del Arduino Nano: recibe pasos por serial y mueve los motores con AccelStepper. |
| `*.hex` | Compilados del `.ino` para cargar en Proteus. Usar el `.eightanaloginputs.hex`, **no** el `with_bootloader`. |
| `__pycache__/` | Carpeta que crea Python sola. Se puede ignorar. |

---

## Requisitos

- Python 3.12 o superior (instalado con "Add python.exe to PATH").
- Librerías: `python -m pip install asyncua opencv-python pyserial numpy`
- Arduino IDE con la librería **AccelStepper** (para cargar el firmware).
- Webcam Logitech C270.
- LabVIEW 2016 (solo para la pantalla SCADA).

---

## Cómo abrir una terminal en esta carpeta

En el Explorador de archivos, clic en la barra de direcciones, escribir `cmd` y Enter.
Verifica con `dir *.py`.

---

## Pruebas, de la más simple a la completa

### 1. Servidor OPC UA solo (sin cámara ni Nano)
Ventana 1:
```
python opc_server.py
```
Ventana 2:
```
python opc_cliente_prueba.py
```
Debe verse `BolaX` y `BolaY` cambiando solos. A la mitad, el cliente escribe `Marcha=True` y
`SetpointX=100`, y `Estado` pasa de 0 a 1. Para cerrar el servidor: `Ctrl+C`.

También se puede usar UaExpert con la dirección `opc.tcp://localhost:4840/ballplate`
(Objects → Planta, seguridad: None).

### 2. Cámara y OPC UA (sin Nano)
Cerrar antes cualquier `opc_server.py` abierto (si no, el puerto 4840 está ocupado).
```
python ballplate.py --no-serial --cam 1
```
- Clic 1 en el **centro** del plato, clic 2 en el **borde** (el plato mide 250 mm de diámetro).
- Aparece un círculo verde sobre la bola y `x=… y=… mm`.
- Con `opc_cliente_prueba.py` en otra ventana se ven los valores reales por OPC UA.

Teclas en la ventana de video:

| Tecla | Acción |
|---|---|
| `q` | salir |
| `c` | recalibrar |
| `h` | ver imagen en gris |
| `+` / `-` | bajar / subir la sensibilidad de detección |

Si no abre la cámara, probar `--cam 0`. Si abre la de la laptop en vez de la C270, usar `--cam 1`.

### 3. Sistema completo (cámara + Nano + motores)
```
python ballplate.py --port COM4
```
Cambiar `COM4` por el puerto del Nano (Administrador de dispositivos → Puertos COM).
Antes, cargar `nano_ballplate.ino` con `#define SIMULACION 0`.

### 4. SCADA en LabVIEW
Con `ballplate.py` (o `opc_server.py`) corriendo, en otra ventana:
```
python lv_gateway.py
```
LabVIEW se conecta por TCP a `localhost:5020` (TCP Open Connection / Read / Write).

Protocolo de texto, líneas terminadas en CRLF:

| Sentido | Mensaje |
|---|---|
| Gateway → LabVIEW (20 Hz) | `D,<BolaX>,<BolaY>,<MotorX>,<MotorY>,<Estado>` |
| LabVIEW → Gateway | `W,<SetpointX>,<SetpointY>,<Marcha 0/1>,<Emergencia 0/1>` |

Si LabVIEW se desconecta, el gateway pone `Marcha = False` por seguridad.

---

## Nodos OPC UA

Dirección: `opc.tcp://localhost:4840/ballplate`, namespace `urn:ballplate:scada`, carpeta `Planta`.

| Nodo | Quién escribe | Unidad |
|---|---|---|
| `SetpointX`, `SetpointY` | SCADA | décimas de mm |
| `Marcha` | SCADA | bool |
| `Emergencia` | SCADA | bool |
| `BolaX`, `BolaY` | Python (cámara) | décimas de mm |
| `MotorX`, `MotorY` | Python (lee del Nano) | pasos |
| `Estado` | Python | 0 = paro, 1 = marcha, 2 = emergencia |

---

## Protocolo serial PC ↔ Nano

Líneas terminadas en `\n`. Baudios: 115200 en real, 9600 en simulación.

| Sentido | Mensaje | Significado |
|---|---|---|
| PC → Nano | `M,<x>,<y>` | objetivo de cada motor en pasos |
| PC → Nano | `Z` | poner la posición actual como cero |
| Nano → PC | `P,<x>,<y>` | posición actual en pasos |

Seguridad del Nano:
- Limita el objetivo a ±40 pasos (`MAX_STEPS`). Subir con cuidado según el recorrido mecánico.
- Si no recibe `M` en 500 ms (real) vuelve a 0 y deja el plato a nivel.
- Sin `delay()`: usa AccelStepper de forma no bloqueante.

Pines: motor X → STEP D2, DIR D3. Motor Y → STEP D5, DIR D6.

---

## Simulación en Proteus

1. En `nano_ballplate.ino` dejar `#define SIMULACION 1` y compilar.
2. Cargar el `.hex` `*.eightanaloginputs.hex` en el Arduino Nano del esquema.
3. Abrir el Virtual Terminal (9600 baudios) y escribir, por ejemplo, `M,20,0` + Enter.
   La respuesta debe ser `P,20,0`.
4. En simulación el motor va lento (máx. 20 pasos/s) porque la CPU de Proteus no aguanta más.

---

## Hardware real (cuando llegue el material)

1. Cambiar a `#define SIMULACION 0` y volver a cargar el `.ino`.
2. A4988: VDD a 5 V, 100 µF entre VMOT y GND, RESET unido a SLEEP, Vref aprox. 0.8 V.
3. Fuente de motores de 12 V, 2 A.
4. Afinar en `ballplate.py` (sección CONFIG): `KP`, `KI`, `KD`, `SIGN_X`, `SIGN_Y`,
   `HOUGH_PARAM2` y `MAX_STEPS`.

---

## Estado del proyecto

| Parte | Estado |
|---|---|
| Servidor OPC UA, lectura y escritura | Probado con cliente de prueba |
| Firmware del Nano, ambos ejes | Probado en Proteus |
| Gateway LabVIEW ↔ OPC UA | Probado con un cliente TCP en Python |
| `ballplate.py` con cámara | Abre la cámara y arranca el servidor; falta afinar con la bola cromada |
| PID y lazo cerrado | Sin probar (necesita plato y motores) |
| Pantalla SCADA en LabVIEW | Pendiente |

---

## Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| `'pip' is not recognized` / `No installed Python found` | Python no está en el PATH. Reinstalar marcando "Add python.exe to PATH" y abrir una terminal nueva. |
| `can't open file 'ballplate.py'` | La terminal está en otra carpeta. Hacer `cd` a la carpeta donde están los `.py`. |
| `OSError: [Errno 10048] ... 4840` | Ya hay un servidor OPC UA corriendo. Cerrar la otra ventana (`Ctrl+C`). Con `ballplate.py` no se corre `opc_server.py` aparte. |
| "No se pudo abrir la cámara" | Probar `--cam 0` o `--cam 1`. Cerrar otras apps que usen la cámara. |
| "bola no detectada" | Ajustar la sensibilidad con `+` / `-`, revisar la luz. La bola cromada refleja mucho. |
| El plato corrige al revés | Cambiar `SIGN_X` o `SIGN_Y` a `-1`. |
| Proteus: el terminal no deja escribir | Dar clic dentro del Virtual Terminal y activar el eco. |

---

## Nota para el reporte

LabVIEW 2016 no incluye cliente OPC UA nativo. Por eso la arquitectura usa un puente
(`lv_gateway.py`) que actúa como cliente OPC UA del servidor y expone los datos a LabVIEW por
TCP/IP. Cualquier otro cliente OPC UA (como UaExpert) ve exactamente los mismos datos.
