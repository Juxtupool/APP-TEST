#include QMK_KEYBOARD_H

// Default key assignments for Layer 0 (Base) and Layer 1 (Fn)
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [0] = LAYOUT_direct(
        KC_A,    KC_B,    KC_C,    KC_D,    KC_E,    KC_F,    MO(1) // GP8 (Encoder switch) toggles Layer 1
    ),
    [1] = LAYOUT_direct(
        KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS
    )
};

// Default encoder map for Layer 0 and Layer 1
#if defined(ENCODER_MAP_ENABLE)
const uint16_t PROGMEM encoder_map[][NUM_ENCODERS][NUM_DIRECTIONS] = {
    [0] = { ENCODER_CCW_CW(KC_VOLD, KC_VOLU) }, // Layer 0: Vol Down / Vol Up
    [1] = { ENCODER_CCW_CW(KC_MS_WH_UP, KC_MS_WH_DOWN) } // Layer 1: Scroll Up / Scroll Down
};
#endif
