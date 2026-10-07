// ============================================================
// Ball-on-Plate - Arduino Nano + 2x A4988 + 2x NEMA17
// Proyecto Final Implementacion de Sistemas de Control (4666)
//
// El Nano solo mueve los motores: recibe el objetivo en pasos por serial
// desde Python (OpenCV + PID + servidor OPC UA). Nada de delay().
//
// Libreria: AccelStepper (v1.64 ya instalada)
// Placa: Arduino Nano (ATmega328P). Hex para Proteus: usa el
//        ".ino.eightanaloginputs.hex", NO el "with_bootloader".
//
// Pines (los mismos de tu simulacion):
//   X: STEP D2, DIR D3      Y: STEP D5, DIR D6
//
// PROTOCOLO SERIAL (115200, lineas terminadas en \n):
//   PC -> Nano : "M,<x>,<y>"   objetivo en pasos (enteros con signo)
//                "Z"           poner posicion actual como cero
//   Nano -> PC : "P,<x>,<y>"   posicion actual en pasos, a 20 Hz
//
// Seguridad: si pasan 500 ms sin recibir "M", vuelve a 0 (plato a nivel).
// NO PROBADO en tu hardware.
// ============================================================
#include <AccelStepper.h>

#define X_STEP_PIN 2
#define X_DIR_PIN  3
#define Y_STEP_PIN 5
#define Y_DIR_PIN  6

// 1 = para Proteus (la CPU solo aguanta ~20 pasos/s), 0 = hardware real
#define SIMULACION 1

const long  MAX_STEPS = 40;      // limite mecanico: sube con cuidado
#if SIMULACION
const float MAX_SPEED = 20.0;    // pasos/s
const float ACCEL     = 40.0;    // pasos/s^2
#else
const float MAX_SPEED = 600.0;   // pasos/s
const float ACCEL     = 1500.0;  // pasos/s^2
#endif
#if SIMULACION
const unsigned long BAUD = 9600;          // menos carga de CPU en Proteus
const unsigned long REPORT_MS = 250;
const unsigned long WATCHDOG_MS = 60000;  // en simulacion escribes a mano, sin prisa
#else
const unsigned long BAUD = 115200;
const unsigned long REPORT_MS = 50;
const unsigned long WATCHDOG_MS = 500;
#endif

AccelStepper motX(AccelStepper::DRIVER, X_STEP_PIN, X_DIR_PIN);
AccelStepper motY(AccelStepper::DRIVER, Y_STEP_PIN, Y_DIR_PIN);

char rxBuf[32];
uint8_t rxLen = 0;
unsigned long lastCmd = 0, lastReport = 0;

void handleLine(char *line) {
  if (line[0] == 'Z') {
    motX.setCurrentPosition(0);
    motY.setCurrentPosition(0);
    return;
  }
  if (line[0] == 'M') {
    long a, b;
    if (sscanf(line + 2, "%ld,%ld", &a, &b) == 2) {
      motX.moveTo(constrain(a, -MAX_STEPS, MAX_STEPS));
      motY.moveTo(constrain(b, -MAX_STEPS, MAX_STEPS));
      lastCmd = millis();
    }
  }
}

void readSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (rxLen > 0) { rxBuf[rxLen] = 0; handleLine(rxBuf); }
      rxLen = 0;
    } else if (rxLen < sizeof(rxBuf) - 1) {
      rxBuf[rxLen++] = c;
    } else {
      rxLen = 0;
    }
  }
}

void setup() {
  Serial.begin(BAUD);
  motX.setMaxSpeed(MAX_SPEED); motX.setAcceleration(ACCEL);
  motY.setMaxSpeed(MAX_SPEED); motY.setAcceleration(ACCEL);
  lastCmd = millis();
}

void loop() {
  readSerial();

  // Watchdog: sin comandos recientes -> plato a nivel
  if (millis() - lastCmd > WATCHDOG_MS) {
    motX.moveTo(0);
    motY.moveTo(0);
  }

  motX.run();
  motY.run();

  if (millis() - lastReport >= REPORT_MS) {
    lastReport = millis();
    Serial.print("P,");
    Serial.print(motX.currentPosition());
    Serial.print(',');
    Serial.println(motY.currentPosition());
  }
}
