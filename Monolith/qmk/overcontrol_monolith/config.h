#pragma once

// Reduce debounce latency for faster switch response
#define DEBOUNCE 5

// Force RP2040 double-tap to enter bootloader
#define RP2040_BOOTLOADER_DOUBLE_TAP_RESET
#define RP2040_BOOTLOADER_DOUBLE_TAP_RESET_TIMEOUT 500U
#define RP2040_BOOTLOADER_DOUBLE_TAP_RESET_LED_PIN GP25 // RP2040-Zero RGB LED pin
