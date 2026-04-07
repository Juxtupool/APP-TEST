// ============================================
// FIRMWARE VERSION - UPDATE WITH EACH RELEASE
// ============================================
const char FIRMWARE_VERSION[] PROGMEM = "1.1.2";
// Version History:
// 1.1.2 - Optimized: Eliminated heap allocations, consolidated debounce logic
// 1.1.1 - Added robust stable-state debouncing, increased delay to 50ms
// 1.1.0 - Fixed GPIO0 spurious key presses, added startup grace period
// 1.0.0 - Initial release

// Define the number of keys on the macropad
const int numKeys = 6;

// Key Configuration
// Robust Pin Mapping to avoid "Ghosting" and Boot issues:
// D0 (16) and D8 (15): Active HIGH (Wire to 3.3V). Internal Pull-down used.
// D1, D2, D3, D4, D7: Active LOW (Wire to GND). Internal Pull-up used.

struct KeyConfig {
  int pin;
  int activeState; // LOW = GND, HIGH = 3.3V
};

KeyConfig keys[numKeys] = {
  {0, LOW},   // Key 1: D3 (Active LOW)
  {2, LOW},   // Key 2: D4 (Active LOW)
  {4, LOW},   // Key 3: D2 (Active LOW)
  {15, HIGH}, // Key 4: D8 (Active HIGH)
  {5, LOW},   // Key 5: D1 (Active LOW)
  {16, HIGH}  // Key 6: D0 (Active HIGH)
};

// Rotary Encoder Pins
const int CLK_PIN = 14; // D5
const int DT_PIN = 12;  // D6
const int SW_PIN = 13;  // D7 (Active LOW)

int lastCLKState;
int currentCLKState;

// --- Timing Constants ---
const unsigned long debounceDelay = 50; // Debounce delay in ms
const unsigned long ACTIVE_DELAY = 1;   // Loop delay when active (ms)
const unsigned long IDLE_DELAY = 10;    // Loop delay when idle (ms)

// --- Debounce State Arrays ---
int lastKeyReading[numKeys];
bool keyState[numKeys];
unsigned long lastKeyDebounceTime[numKeys];

// --- Knob Button Debounce State ---
int lastKnobReading = HIGH;
bool knobState = false;
unsigned long lastKnobDebounceTime = 0;

// ============================================
// HELPER FUNCTIONS
// ============================================

/**
 * Check button debounce state and return true on press event
 * Consolidates debounce logic for reusability
 */
bool checkButtonDebounce(int reading, int& lastReading, bool& state,
                        unsigned long& lastTime, int activeState,
                        unsigned long currentTime) {
    if (reading != lastReading) {
        lastTime = currentTime;
    }
    
    if ((currentTime - lastTime) > debounceDelay) {
        bool isPressed = (reading == activeState);
        if (isPressed != state) {
            state = isPressed;
            lastReading = reading;
            return isPressed;  // Return true only on press
        }
    }
    
    lastReading = reading;
    return false;
}

/**
 * Send version string from PROGMEM
 */
void sendVersion() {
    Serial.print(F("VERSION_"));
    // Read from PROGMEM
    char buffer[10];
    strcpy_P(buffer, FIRMWARE_VERSION);
    Serial.println(buffer);
}

// ============================================
// SETUP
// ============================================

void setup() {
  Serial.begin(115200);

  // Initialize the key pins
  for (int i = 0; i < numKeys; i++) {
    if (keys[i].activeState == LOW) {
      pinMode(keys[i].pin, INPUT_PULLUP);
    } else {
      if (keys[i].pin == 16) {
        pinMode(16, INPUT_PULLDOWN_16);
      } else {
        pinMode(keys[i].pin, INPUT);
      }
    }
    
    // Initialize state
    lastKeyReading[i] = digitalRead(keys[i].pin);
    bool pressed = (lastKeyReading[i] == keys[i].activeState);
    keyState[i] = pressed;
    lastKeyDebounceTime[i] = 0;
  }

  // Initialize Rotary Encoder pins
  pinMode(CLK_PIN, INPUT);
  pinMode(DT_PIN, INPUT);
  pinMode(SW_PIN, INPUT_PULLUP);

  lastCLKState = digitalRead(CLK_PIN);
  
  // Startup grace period
  delay(100);
  
  // Send firmware version
  sendVersion();
}

// ============================================
// MAIN LOOP
// ============================================

void loop() {
  unsigned long currentTime = millis();
  bool anyActivity = false;

  // --- Scan Keys with Debounce ---
  for (int i = 0; i < numKeys; i++) {
    int reading = digitalRead(keys[i].pin);
    
    // Track activity
    if (reading != lastKeyReading[i]) {
      anyActivity = true;
    }
    
    // Check for key press event using consolidated debounce function
    if (checkButtonDebounce(reading, lastKeyReading[i], keyState[i],
                           lastKeyDebounceTime[i], keys[i].activeState, currentTime)) {
      // KEY PRESSED EVENT - send without String allocation
      Serial.print(F("KEY_"));
      Serial.print(i + 1);
      Serial.println(F("_PRESSED"));
      anyActivity = true;
    }
  }

  // --- Rotary Encoder ---
  currentCLKState = digitalRead(CLK_PIN);

  if (currentCLKState != lastCLKState && currentCLKState == 1) {
    anyActivity = true;
    if (digitalRead(DT_PIN) != currentCLKState) {
      Serial.println(F("KNOB_RIGHT"));
    } else {
      Serial.println(F("KNOB_LEFT"));
    }
  }
  lastCLKState = currentCLKState;

  // --- Encoder Button Debounce ---
  int knobReading = digitalRead(SW_PIN);
  
  if (knobReading != lastKnobReading) {
    anyActivity = true;
  }
  
  if (checkButtonDebounce(knobReading, lastKnobReading, knobState,
                         lastKnobDebounceTime, LOW, currentTime)) {
    Serial.println(F("KNOB_PRESS"));
    anyActivity = true;
  }
  
  // CPU optimization: adaptive delay
  if (anyActivity) {
    delay(ACTIVE_DELAY);
  } else {
    delay(IDLE_DELAY);
  }
}