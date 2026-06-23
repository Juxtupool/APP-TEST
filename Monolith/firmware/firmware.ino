#include <Adafruit_TinyUSB.h>

// Define the HID report descriptor for a Keyboard to enable keyboard HID icon in Device Manager
uint8_t const desc_hid_report[] = {
  TUD_HID_REPORT_DESC_KEYBOARD()
};

// Initialize USB HID for Keyboard
Adafruit_USBD_HID usb_hid(desc_hid_report, sizeof(desc_hid_report), HID_ITF_PROTOCOL_KEYBOARD, 2, false);

Adafruit_USBD_MIDI usb_midi;
String knobMode = "Standard";

// ===========================================
// FIRMWARE VERSION
// ============================================
const char FIRMWARE_VERSION[] = "2.1.0";
// Version History:
// 2.2.0 - Changed knob behaviour from Native USB MIDI to Hardware Interrupt
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
int lastCLKState;

// --- Debounce State Arrays ---
const unsigned long debounceDelay = 50;
int lastKeyReading[numKeys];
bool keyState[numKeys];
unsigned long lastKeyDebounceTime[numKeys];

int lastKnobReading = HIGH;
bool knobState = false;
unsigned long lastKnobDebounceTime = 0;

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
  lastCLKState = digitalRead(CLK_PIN);

  delay(100);
  sendVersion();
}

// ============================================
// MAIN LOOP
// ============================================

void loop() {
  unsigned long currentTime = millis();
  bool anyActivity = false;

  // --- Serial Command Handling ---
  if (Serial.available() > 0) {
    String incoming = Serial.readStringUntil('\n');
    incoming.trim();

    if (incoming == "GET_VERSION") {
      sendVersion();
    } else if (incoming.startsWith("SET_KNOB_MODE ")) {
      knobMode = incoming.substring(14);
    }
  }

  // --- Scan Keys ---
  for (int i = 0; i < numKeys; i++) {
    int reading = digitalRead(keys[i].pin);
    if (reading != lastKeyReading[i]) anyActivity = true;

    if (checkButtonDebounce(reading, lastKeyReading[i], keyState[i],
                            lastKeyDebounceTime[i], keys[i].activeState, currentTime)) {
      Serial.print("KEY_"); Serial.print(i + 1); Serial.println("_PRESSED");
      anyActivity = true;
    }
  }

  // --- Rotary Encoder ---
  int currentCLKState = digitalRead(CLK_PIN);
  if (currentCLKState != lastCLKState && currentCLKState == 1) {
    anyActivity = true;
    if (digitalRead(DT_PIN) != currentCLKState) {
      if (knobMode == "MIDI Controller") {
        uint8_t msg[] = {0xB0, 20, 65};
        usb_midi.write(msg, 3);
      } else {
        Serial.println("KNOB_RIGHT");
      }
    } else {
      if (knobMode == "MIDI Controller") {
        uint8_t msg[] = {0xB0, 20, 63};
        usb_midi.write(msg, 3);
      } else {
        Serial.println("KNOB_LEFT");
      }
    }
  }
  lastCLKState = currentCLKState;

  // --- Encoder Button ---
  int knobReading = digitalRead(SW_PIN);
  if (knobReading != lastKnobReading) anyActivity = true;
  if (checkButtonDebounce(knobReading, lastKnobReading, knobState,
                          lastKnobDebounceTime, LOW, currentTime)) {
    if (knobMode == "MIDI Controller") {
      uint8_t noteOn[] = {0x90, 60, 127};
      usb_midi.write(noteOn, 3);
      delay(50);
      uint8_t noteOff[] = {0x80, 60, 0};
      usb_midi.write(noteOff, 3);
    } else {
      Serial.println("KNOB_PRESS");
    }
    anyActivity = true;
  }

  delay(anyActivity ? 1 : 10);
}
