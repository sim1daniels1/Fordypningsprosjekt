const int PIN = A1;
const float VS = 5.0;
const float ADC_REF = 5.0;
const int ADC_MAX = 1023;

void setup() {
  Serial.begin(115200);
}

void loop() {
  int raw = analogRead(PIN);
  float vout = raw * ADC_REF / ADC_MAX;
  float P_kPa = (vout / VS + 0.04) / 0.004;
  P_kPa = constrain(P_kPa, 20.0, 250.0);
  Serial.print(millis());
  Serial.print(",");
  Serial.println(P_kPa);

  delay(100);
}
