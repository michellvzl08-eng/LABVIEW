#include <AccelStepper.h>

// Eje X: STEP en D2, DIR en D3
#define X_STEP_PIN 2
#define X_DIR_PIN  3
// Eje Y: STEP en D5, DIR en D6
#define Y_STEP_PIN 5
#define Y_DIR_PIN  6

AccelStepper stepperX(AccelStepper::DRIVER, X_STEP_PIN, X_DIR_PIN);
AccelStepper stepperY(AccelStepper::DRIVER, Y_STEP_PIN, Y_DIR_PIN);

void setup() {
  stepperX.setMaxSpeed(500);       // pasos/seg
  stepperX.setAcceleration(200);   // pasos/seg^2
  stepperX.moveTo(200);            // 1 vuelta

  stepperY.setMaxSpeed(300);
  stepperY.setAcceleration(150);
  stepperY.moveTo(100);            // media vuelta
}

void loop() {
  // Al llegar al destino, cada eje invierte su sentido
  if (stepperX.distanceToGo() == 0) {
    stepperX.moveTo(-stepperX.currentPosition());
  }
  if (stepperY.distanceToGo() == 0) {
    stepperY.moveTo(-stepperY.currentPosition());
  }

  // Ambos run() deben llamarse en cada vuelta del loop
  stepperX.run();
  stepperY.run();
}
