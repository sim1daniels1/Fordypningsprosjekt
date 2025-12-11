#include <AccelStepper.h>

// ---- Pins ----
const int STEP_PIN  = 2;   // TB6600 PUL−
const int DIR_PIN   = 5;   // TB6600 DIR−
const int PRESS_PIN = A1;  // MPX4250AP Vout

// ---- AccelStepper / TB6600 ----
// TB6600 wiring:
//   PUL+ → 5V, PUL− → STEP_PIN
//   DIR+ → 5V, DIR− → DIR_PIN
//   ENA floating (enabled by default)
AccelStepper stepper(AccelStepper::DRIVER, STEP_PIN, DIR_PIN);

// Speeds in microsteps per second (1/8 microstep assumed)
float SPEED_UP   = 25.0f;   // positive = increasing pressure (push syringe)
float SPEED_DOWN = -25.0f;  // negative = decreasing pressure (release)

// ---- Pressure sensor (MPX4250AP) ----
// P[kPa] = 250*(Vout/Vs + 0.04), Vs ~ 5 V, Vout/Vs = adc/1023
const int NAVG = 8;

float P_init     = 0.0f;
float P_low      = 0.0f;
float P_high     = 0.0f;
float margin_kPa = 2.0f;

// ---- Fixed staged schedule ----
// Stage 0: [75,125] kPa
// Stage 1: [75,150] kPa
// Stage 2: [75,175] kPa
// Stage 3: [75,200] kPa
const int   CYCLES_PER_STAGE   = 10;      // N cycles per stage
const int   NUM_STAGES         = 6;
const float P_LOW_BASE_KPA     = 75.0f;
const float P_HIGH_START_KPA   = 125.0f; // first high value
const float P_HIGH_STEP_KPA    = 25.0f;  // increment per stage
const float P_HIGH_MAX_KPA     = 300.0f; // clamp high to this

int   stageIndex           = 0;  // 0..NUM_STAGES-1
long  cycleCount           = 0;
bool  highReachedThisCycle = false;

// ---- State machine ----
enum State { HOLD, GOING_UP, GOING_DOWN };
State state = HOLD;

// ---- Flags ----
bool testRunning = false;


// ============================================================================
// Pressure read helper
// ============================================================================
float readPressure_kPa() {
  static int acc = 0;
  static int cnt = 0;

  int val = analogRead(PRESS_PIN);
  acc += val;
  cnt++;

  if (cnt < NAVG) return NAN;

  int avg = acc / cnt;
  acc = 0;
  cnt = 0;

  float p = 250.0f * ((avg / 1023.0f) + 0.04f);
  return (p < 0.0f) ? 0.0f : p;
}


// ============================================================================
// Update P_low, P_high for current stage
// ============================================================================
void updateBandsFromStage() {
  if (stageIndex >= NUM_STAGES) {
    // Safety: shouldn't normally be called in this case
    Serial.println(F("All stages already completed."));
    testRunning = false;
    stepper.setSpeed(0);
    state = HOLD;
    return;
  }

  P_low  = P_LOW_BASE_KPA;
  P_high = P_HIGH_START_KPA + stageIndex * P_HIGH_STEP_KPA;

  if (P_high > P_HIGH_MAX_KPA) {
    P_high = P_HIGH_MAX_KPA;
  }

  Serial.print(F("Stage "));
  Serial.print(stageIndex);
  Serial.print(F(": P_low="));
  Serial.print(P_low, 1);
  Serial.print(F("  P_high="));
  Serial.println(P_high, 1);
}


// ============================================================================
// Start test
// ============================================================================
void startTest() {
  // Measure ambient for logging (does NOT set targets)
  float sum = 0.0f;
  for (int i = 0; i < 50; i++) {
    int adc = analogRead(PRESS_PIN);
    sum += 250.0f * ((adc / 1023.0f) + 0.04f);
    delay(5);
  }
  P_init = sum / 50.0f;
  if (P_init < 0.0f) P_init = 0.0f;

  // Reset counters
  stageIndex           = 0;
  cycleCount           = 0;
  highReachedThisCycle = false;

  // Zero stepper position (just for logging)
  stepper.setCurrentPosition(0);

  updateBandsFromStage();

  // Start by going up
  state       = GOING_UP;
  testRunning = true;
  stepper.setSpeed(SPEED_UP);

  Serial.print(F("Test started. Ambient P_init="));
  Serial.print(P_init, 2);
  Serial.println(F(" kPa"));
}


// ============================================================================
// Setup
// ============================================================================
void setup() {
  Serial.begin(115200);
  delay(300);

  // Stepper config
  stepper.setMaxSpeed(1000.0f);      // max |speed|
  stepper.setAcceleration(500.0f);   // not used by runSpeed, but fine to set
  stepper.setSpeed(0);

  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN,  OUTPUT);
  digitalWrite(STEP_PIN, LOW);
  digitalWrite(DIR_PIN,  LOW);

  Serial.println(F("TB6600 + AccelStepper continuous cyclic rig ready."));
  Serial.println(F("Send 's' to start, 'x' to stop."));
}


// ============================================================================
// Loop  (UPDATED TO ALWAYS LOG PRESSURE)
// ============================================================================
void loop() {
  static unsigned long lastPrintMs = 0;
  unsigned long nowMs = millis();

  // ---- Serial commands ----
  if (Serial.available()) {
    char c = Serial.read();
    if ((c == 's' || c == 'S') && !testRunning) {
      startTest();
    } else if (c == 'x' || c == 'X') {
      testRunning = false;
      stepper.setSpeed(0);
      state = HOLD;
      Serial.println(F("Test stopped."));
    }
  }

  // ---- Read pressure continuously ----
  float P = readPressure_kPa();

  if (!isnan(P)) {

    // ---- Only move state machine when test is running ----
    if (testRunning) {
      switch (state) {

        case GOING_UP:
          if (P >= P_high - margin_kPa) {
            // Hit high band → immediately go down
            highReachedThisCycle = true;
            state = GOING_DOWN;
            stepper.setSpeed(SPEED_DOWN);
          }
          break;

        case GOING_DOWN:
          if (P <= P_low + margin_kPa) {
            // Hit low band → complete cycle (if high was reached), then go up again
            if (highReachedThisCycle) {
              cycleCount++;
              highReachedThisCycle = false;

              Serial.print(F("Cycle "));
              Serial.print(cycleCount);
              Serial.println(F(" complete."));

              // Check if we should advance stage
              if (cycleCount % CYCLES_PER_STAGE == 0) {
                stageIndex++;
                if (stageIndex < NUM_STAGES) {
                  updateBandsFromStage();
                } else {
                  // All stages done
                  Serial.println(F("All stages complete. Test stopped."));
                  testRunning = false;
                  stepper.setSpeed(0);
                  state = HOLD;
                }
              }
            }
            // Go up again (either same stage or next if changed)
            if (testRunning) {
              state = GOING_UP;
              stepper.setSpeed(SPEED_UP);
            }
          }
          break;

        case HOLD:
          // Only used when test is not running or after manual stop
          break;
      }
    }

    // ---- Logging (ALWAYS, even if not running) ----
    if (nowMs - lastPrintMs >= 150) {
      lastPrintMs = nowMs;

      long posSteps = stepper.currentPosition();

      Serial.print(F("P="));       Serial.print(P, 2);
      Serial.print(F(",P_init=")); Serial.print(P_init, 2);
      Serial.print(F(",P_low="));  Serial.print(P_low, 2);
      Serial.print(F(",P_high=")); Serial.print(P_high, 2);
      Serial.print(F(",posSteps=")); Serial.print(posSteps);
      Serial.print(F(",state="));
      if (state == GOING_UP)      Serial.print("UP");
      else if (state == GOING_DOWN) Serial.print("DOWN");
      else                        Serial.print("HOLD");
      Serial.print(F(",stage="));  Serial.print(stageIndex);
      Serial.print(F(",cycles=")); Serial.print(cycleCount);
      Serial.print(F(",running=")); Serial.print(testRunning ? 1 : 0);
      Serial.println();
    }
  }

  // ---- Run stepper at commanded speed (non-blocking) ----
  stepper.runSpeed();
}
