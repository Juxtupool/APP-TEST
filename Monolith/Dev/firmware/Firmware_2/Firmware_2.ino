#include <Adafruit_TinyUSB.h>

// Define the HID report descriptor for a Keyboard to enable keyboard HID icon in Device Manager
uint8_t const desc_hid_report[] = {
  TUD_HID_REPORT_DESC_KEYBOARD()
};

// Initialize USB HID for Keyboard
Adafruit_USBD_HID usb_hid(desc_hid_report, sizeof(desc_hid_report), HID_ITF_PROTOCOL_KEYBOARD, 2, false);

Adafruit_USBD_MIDI usb_midi;
char knobMode[32] = "Standard";

// ===========================================
// FIRMWARE VERSION
// ============================================
const char FIRMWARE_VERSION[] = "2.2.0";
// Version History:
// 2.2.0 - Non-blocking Serial parsing, robust software debounce for encoder, constant 1ms polling loop
// 2.1.0 - Renamed to Overcontrol. Enabled Keyboard HID for icon.
// 2.0.0 - Migrated to RP2040-Zero. GPIO 0-5 for switches, GPIO 6-8 for rotary encoder.
// 1.1.2 - Optimized: Eliminated heap allocations, consolidated debounce logic
// 1.1.1 - Added robust stable-state debouncing, increased delay to 50ms
// 1.1.0 - Fixed GPIO0 spurious key presses, added startup grace period
// 1.0.0 - Initial release

// Define the number of keys on the macropad
const int numKeys = 6;

// Key Configuration
struct KeyConfig {
  int pin;
  int activeState; // LOW = GND
};

KeyConfig keys[numKeys] = {
  {0, LOW}, {1, LOW}, {2, LOW}, {3, LOW}, {4, LOW}, {5, LOW}
};

// Rotary Encoder Pins
const int CLK_PIN = 6;
const int DT_PIN = 7;
const int SW_PIN = 8;

// --- Debounce State Arrays ---
const unsigned long debounceDelay = 50;
int lastKeyReading[numKeys];
bool keyState[numKeys];
unsigned long lastKeyDebounceTime[numKeys];

int lastKnobReading = HIGH;
bool knobState = false;
unsigned long lastKnobDebounceTime = 0;

// Encoder Debounce States
int debouncedCLK = HIGH;
int lastCLKState = HIGH;
unsigned long lastCLKChangeTime = 0;

// ============================================
// HELPER FUNCTIONS
// ============================================

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
      return isPressed;
    }
  }
  lastReading = reading;
  return false;
}

void sendVersion() {
  Serial.print("VERSION_");
  Serial.println(FIRMWARE_VERSION);
}

// ============================================
// SETUP
// ============================================

void setup() {
  TinyUSBDevice.setManufacturerDescriptor("Overcontrol");
  TinyUSBDevice.setProductDescriptor("Monolith");
  
  usb_hid.begin();
  usb_midi.begin();
  
  Serial.begin(115200);

  for (int i = 0; i < numKeys; i++) {
    pinMode(keys[i].pin, INPUT_PULLUP);
    lastKeyReading[i] = digitalRead(keys[i].pin);
    keyState[i] = (lastKeyReading[i] == keys[i].activeState);
    lastKeyDebounceTime[i] = 0;
  }

  pinMode(CLK_PIN, INPUT_PULLUP);
  pinMode(DT_PIN, INPUT_PULLUP);
  pinMode(SW_PIN, INPUT_PULLUP);
  debouncedCLK = digitalRead(CLK_PIN);
  lastCLKState = debouncedCLK;

  delay(100);
  sendVersion();
}

// ============================================
// MAIN LOOP
// ============================================

void loop() {
  unsigned long currentTime = millis();

  // --- Non-blocking Serial Command Handling ---
  static char rxBuffer[64];
  static size_t rxIndex = 0;
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n' || rxIndex >= sizeof(rxBuffer) - 1) {
      rxBuffer[rxIndex] = '\0';
      if (rxIndex > 0 && rxBuffer[rxIndex - 1] == '\r') {
        rxBuffer[rxIndex - 1] = '\0';
      }
      
      if (strcmp(rxBuffer, "GET_VERSION") == 0) {
        sendVersion();
      } else if (strncmp(rxBuffer, "SET_KNOB_MODE ", 14) == 0) {
        strncpy(knobMode, rxBuffer + 14, sizeof(knobMode) - 1);
        knobMode[sizeof(knobMode) - 1] = '\0';
      }
      
      rxIndex = 0;
    } else if (c != '\r') {
      rxBuffer[rxIndex++] = c;
    }
  }

  // --- Scan Keys ---
  for (int i = 0; i < numKeys; i++) {
    int reading = digitalRead(keys[i].pin);
    if (checkButtonDebounce(reading, lastKeyReading[i], keyState[i],
                            lastKeyDebounceTime[i], keys[i].activeState, currentTime)) {
      Serial.print("KEY_"); Serial.print(i + 1); Serial.println("_PRESSED");
    }
  }

  // --- Debounced Rotary Encoder ---
  int rawCLK = digitalRead(CLK_PIN);
  if (rawCLK != debouncedCLK) {
    if (currentTime - lastCLKChangeTime > 2) { // 2ms stable period to filter out bounce
      debouncedCLK = rawCLK;
    }
  } else {
    lastCLKChangeTime = currentTime;
  }

  if (debouncedCLK != lastCLKState && debouncedCLK == 1) {
    if (digitalRead(DT_PIN) != debouncedCLK) {
      if (strcmp(knobMode, "MIDI Controller") == 0) {
        uint8_t msg[] = {0xB0, 20, 65};
        usb_midi.write(msg, 3);
      } else {
        Serial.println("KNOB_RIGHT");
      }
    } else {
      if (strcmp(knobMode, "MIDI Controller") == 0) {
        uint8_t msg[] = {0xB0, 20, 63};
        usb_midi.write(msg, 3);
      } else {
        Serial.println("KNOB_LEFT");
      }
    }
  }
  lastCLKState = debouncedCLK;

  // --- Encoder Button ---
  int knobReading = digitalRead(SW_PIN);
  if (checkButtonDebounce(knobReading, lastKnobReading, knobState,
                          lastKnobDebounceTime, LOW, currentTime)) {
    if (strcmp(knobMode, "MIDI Controller") == 0) {
      uint8_t noteOn[] = {0x90, 60, 127};
      usb_midi.write(noteOn, 3);
      delay(50);
      uint8_t noteOff[] = {0x80, 60, 0};
      usb_midi.write(noteOff, 3);
    } else {
      Serial.println("KNOB_PRESS");
    }
  }

  delay(1); // Constant high-speed polling
}
