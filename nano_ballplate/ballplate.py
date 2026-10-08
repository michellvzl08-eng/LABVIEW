"""
Ball-on-Plate - Vision + control (PC)
Proyecto Final Implementacion de Sistemas de Control (4666)

Webcam (C270) -> detecta la bola -> PID por eje -> Arduino Nano por USB serial,
y publica todo por OPC UA (opc_server.py) para el SCADA en LabVIEW.
Protocolo serial (115200, lineas terminadas en \\n):
  PC -> Nano : "M,<x>,<y>"  objetivo de motores en pasos
  Nano -> PC : "P,<x>,<y>"  posicion actual de motores en pasos
OPC UA: el SCADA escribe SetpointX/Y, Marcha, Emergencia; Python publica la posicion.

Uso:
  pip install opencv-python pyserial numpy
  python ballplate.py --port COM4            (ajusta el puerto)
  python ballplate.py --no-serial            (solo vision, sin Nano)

Calibracion (al abrir): clic 1 = CENTRO del plato, clic 2 = BORDE del plato.
Con eso se obtiene mm/px usando el diametro real (250 mm por defecto).
Teclas: q salir | c recalibrar | h ver mascara/deteccion | +/- ajustar sensibilidad
NO PROBADO en tu hardware: la deteccion de bola cromada depende de la luz; afina
los parametros de la seccion CONFIG viendo la imagen.
"""
import argparse
import sys
import time

import cv2
import numpy as np

import opc_server

try:
    import serial
except ImportError:
    serial = None

# ===================== CONFIG =====================
CAM_INDEX = 1            # 0 = camara de la laptop, 1 = C270 (cambia si hace falta)
FRAME_W, FRAME_H = 640, 480
PLATE_DIAM_MM = 250.0
BALL_DIAM_MM = 19.05     # 3/4"
MAX_STEPS = 40           # igual que en el .ino
KP, KI, KD = 0.08, 0.0, 0.05   # ganancias iniciales (pasos por 0.1 mm de error) -> AFINAR
SIGN_X, SIGN_Y = 1, 1    # cambia a -1 si el plato corrige al reves
SEND_HZ = 30
HOUGH_PARAM2 = 25        # menor = mas sensible (mas falsos positivos)
# ==================================================


class PID:
    def __init__(self, kp, ki, kd, limit):
        self.kp, self.ki, self.kd, self.limit = kp, ki, kd, limit
        self.i = 0.0
        self.prev = None

    def reset(self):
        self.i = 0.0
        self.prev = None

    def step(self, err, dt):
        self.i = float(np.clip(self.i + err * dt, -self.limit, self.limit))
        d = 0.0 if self.prev is None or dt <= 0 else (err - self.prev) / dt
        self.prev = err
        out = self.kp * err + self.ki * self.i + self.kd * d
        return float(np.clip(out, -self.limit, self.limit))


class Calib:
    def __init__(self):
        self.center = None
        self.mm_per_px = None
        self.clicks = []

    def on_mouse(self, event, x, y, flags, param):
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        self.clicks.append((x, y))
        if len(self.clicks) == 1:
            self.center = (x, y)
        elif len(self.clicks) == 2:
            r = np.hypot(x - self.center[0], y - self.center[1])
            if r > 10:
                self.mm_per_px = (PLATE_DIAM_MM / 2.0) / r

    @property
    def ready(self):
        return self.center is not None and self.mm_per_px is not None


def detect_ball(gray, mm_per_px, param2):
    """Devuelve (x, y, r) en pixeles o None. Hough sobre imagen suavizada."""
    r_px = (BALL_DIAM_MM / 2.0) / mm_per_px
    blur = cv2.GaussianBlur(gray, (9, 9), 2)
    circles = cv2.HoughCircles(
        blur, cv2.HOUGH_GRADIENT, dp=1.2, minDist=100,
        param1=100, param2=param2,
        minRadius=int(r_px * 0.7), maxRadius=int(r_px * 1.4))
    if circles is None:
        return None
    x, y, r = circles[0][0]
    return float(x), float(y), float(r)


def read_serial_lines(ser):
    while ser is not None and ser.in_waiting:
        try:
            line = ser.readline().decode("ascii", errors="ignore").strip()
        except Exception:
            return
        if line.startswith("P,"):
            parts = line.split(",")
            if len(parts) == 3:
                try:
                    opc_server.put(MotorX=int(parts[1]), MotorY=int(parts[2]))
                except ValueError:
                    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="COM4")
    ap.add_argument("--cam", type=int, default=CAM_INDEX)
    ap.add_argument("--no-serial", action="store_true")
    args = ap.parse_args()

    ser = None
    if not args.no_serial:
        if serial is None:
            sys.exit("Falta pyserial: pip install pyserial")
        ser = serial.Serial(args.port, 115200, timeout=0.01)
        time.sleep(2.0)  # el Nano se reinicia al abrir el puerto

    cap = cv2.VideoCapture(args.cam, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
    if not cap.isOpened():
        sys.exit("No se pudo abrir la camara (prueba --cam 0 o --cam 1)")

    win = "Ball-on-Plate"
    cv2.namedWindow(win)
    calib = Calib()
    cv2.setMouseCallback(win, calib.on_mouse)

    pid_x, pid_y = PID(KP, KI, KD, MAX_STEPS), PID(KP, KI, KD, MAX_STEPS)
    opc_server.start()
    param2 = HOUGH_PARAM2
    show_gray = False
    last_send = 0.0
    last_t = time.time()
    lost_frames = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Sin imagen de la camara")
            break
        read_serial_lines(ser)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        view = gray.copy() if show_gray else frame.copy()
        if show_gray:
            view = cv2.cvtColor(view, cv2.COLOR_GRAY2BGR)

        if not calib.ready:
            msg = "Clic 1: CENTRO del plato" if not calib.clicks else "Clic 2: BORDE del plato"
            cv2.putText(view, msg, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.imshow(win, view)
        else:
            cx, cy = calib.center
            mpp = calib.mm_per_px
            now = time.time()
            dt = now - last_t
            last_t = now

            ball = detect_ball(gray, mpp, param2)
            cv2.circle(view, (cx, cy), int(PLATE_DIAM_MM / 2 / mpp), (255, 200, 0), 1)
            cv2.drawMarker(view, (cx, cy), (255, 200, 0), cv2.MARKER_CROSS, 15, 1)

            if ball is not None:
                lost_frames = 0
                bx, by, br = ball
                # coordenadas en decimas de mm, y hacia arriba positivo
                x_dmm = int(round((bx - cx) * mpp * 10))
                y_dmm = int(round((cy - by) * mpp * 10))
                cv2.circle(view, (int(bx), int(by)), int(br), (0, 255, 0), 2)
                cv2.putText(view, f"x={x_dmm/10:.1f} y={y_dmm/10:.1f} mm", (10, 25),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

                if now - last_send >= 1.0 / SEND_HZ:
                    last_send = now
                    estop = opc_server.get("Emergencia")
                    run = opc_server.get("Marcha") and not estop
                    estado = 2 if estop else (1 if run else 0)
                    opc_server.put(BolaX=x_dmm, BolaY=y_dmm, Estado=estado)
                    if run:
                        ex = opc_server.get("SetpointX") - x_dmm
                        ey = opc_server.get("SetpointY") - y_dmm
                        mx = int(round(SIGN_X * pid_x.step(ex, dt)))
                        my = int(round(SIGN_Y * pid_y.step(ey, dt)))
                    else:
                        pid_x.reset(); pid_y.reset()
                        mx = my = 0
                    if ser is not None:
                        ser.write(f"M,{mx},{my}\n".encode())
                    cv2.putText(view, f"estado={estado} M=({mx},{my})", (10, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)
            else:
                lost_frames += 1
                cv2.putText(view, "bola no detectada", (10, 25),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                # Seguridad: si se pierde la bola, plato a nivel
                if lost_frames > 5 and ser is not None and now - last_send >= 1.0 / SEND_HZ:
                    last_send = now
                    pid_x.reset(); pid_y.reset()
                    ser.write(b"M,0,0\n")

            cv2.putText(view, f"sens={param2}", (10, FRAME_H - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            cv2.imshow(win, view)

        k = cv2.waitKey(1) & 0xFF
        if k == ord("q"):
            break
        elif k == ord("c"):
            calib = Calib()
            cv2.setMouseCallback(win, calib.on_mouse)
        elif k == ord("h"):
            show_gray = not show_gray
        elif k in (ord("+"), ord("=")):
            param2 = min(param2 + 2, 100)
        elif k == ord("-"):
            param2 = max(param2 - 2, 5)

    if ser is not None:
        ser.write(b"M,0,0\n")
        ser.close()
    opc_server.stop()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
