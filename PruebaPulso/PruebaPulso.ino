void setup() {
  pinMode(2, OUTPUT);
  pinMode(3, OUTPUT);
  digitalWrite(3, HIGH);   // DIR fija en 5 V
}

void loop() {
  digitalWrite(2, HIGH);
  delay(1);
  digitalWrite(2, LOW);
  delay(1);
}
