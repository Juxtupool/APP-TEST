# MCU and Bootloader configuration
MCU = RP2040
BOOTLOADER = rp2040

# Enable features
BOOTMAGIC_ENABLE = yes     # Allows clearing EEPROM on boot
MOUSEKEY_ENABLE = yes      # Mouse keys control
EXTRAKEY_ENABLE = yes      # Audio control and System keys
CONSOLE_ENABLE = no        # Console utilities
COMMAND_ENABLE = no        # Command mode
BACKLIGHT_ENABLE = no
RGBLIGHT_ENABLE = no
NKRO_ENABLE = yes          # N-Key Rollover
ENCODER_ENABLE = yes       # Enable rotary encoder support
ENCODER_MAP_ENABLE = yes   # Enable mapping encoders in VIA
VIA_ENABLE = yes           # Enable VIA support
LTO_ENABLE = yes           # Enable Link-Time Optimization for smaller binaries
