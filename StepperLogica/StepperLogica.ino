#include <AccelStepper.h>

AccelStepper stepperX(AccelStepper::DRIVER, 2, 3);

void setup() {
  stepperX.setMinPulseWidth(20);
  stepperX.setMaxSpeed(20);        // muy lento
  stepperX.setAcceleration(50);
  stepperX.moveTo(80);
}

void loop() {
  stepperX.run();
}
