#include <AccelStepper.h>

#define STEP_PIN 2
#define DIR_PIN  3

AccelStepper stepperX(AccelStepper::DRIVER, STEP_PIN, DIR_PIN);

void setup() {
  stepperX.setMaxSpeed(500);       // pasos/seg
  stepperX.setAcceleration(200);   // pasos/seg^2
  stepperX.moveTo(200);            // 200 pasos = 1 vuelta (NEMA17 de 1.8°)
}

void loop() {
  // Al llegar al destino, invierte el sentido
  if (stepperX.distanceToGo() == 0) {
    stepperX.moveTo(-stepperX.currentPosition());
  }
  stepperX.run();
}
