
# Interstate75W LED Display with MQTT Control

This project uses the Pimoroni Interstate75W to display messages on a 32x64 pixel HUB75 LED display, with brightness control and message handling via MQTT. Demo Video Below

 [![Watch the demo video](https://img.youtube.com/vi/kG3OStmfXLk/0.jpg)](https://youtu.be/kG3OStmfXLk)

## Table of Contents

- [Introduction](#introduction)
- [Features](#features)
- [Hardware Requirements](#hardware-requirements)
- [Software Requirements](#software-requirements)
- [Setup](#setup)
- [Usage](#usage)
- [Code Explanation](#code-explanation)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Introduction

This project leverages the Interstate75W from Pimoroni to display scrolling text messages on a HUB75 LED matrix. The brightness of the display can be controlled manually, and messages are received via MQTT.
It uses an open MQTT text feed as a demo, you can edit to add your own feed and MQTT broker details accordingly. Wifi and MQTT broker are set up in the config.py file, the topic is defined in the main file.
## Features

- Display scrolling text messages on a HUB75 LED matrix.
- Manual brightness control.
- Message reception via MQTT.
- Automatic reconnection to WiFi and MQTT broker.

## Hardware Requirements

- Pimoroni Interstate75W
- HUB75 LED matrix display - we used a 32x64 pixel display with a 4mm pitch
- MQTT broker (local or cloud-based) - a demo mqtt feed is included in the code - note the demo feed sends a message approximatly every 3 minutes. Upon connected you should get the message Checking WiFi integrity.

Got reliable connection
Connecting to broker.
Connected to broker.
Wifi is  up


## Software Requirements

- MicroPython
- Required MicroPython libraries:
  - `interstate75`
  - `mqtt_as`
  - `uasyncio`

## Setup

1. **Clone this repository:**
   ```sh
   git clone git clone https://github.com/yourusername/interstate75w-mqtt-display.git
   cd interstate75w-mqtt-display
   cd interstate75w-mqtt-display
   ```

2. **Upload the code to your microcontroller:**
   - Use a tool like Thonny or ampy to upload the files to your microcontroller.

3. **Configure WiFi and MQTT settings:**
   - Update `config.py` with your WiFi credentials and MQTT broker details if not using the demo feed. 

## Usage

1. **Power up your hardware:**
   - Connect your microcontroller to the HUB75 LED matrix and power it on.

2. **Run the main script:**
   - The script will automatically connect to WiFi and the MQTT broker, then start displaying messages.

3. **Wait for messages via MQTT:**
   - Demo messages should appear every 3 minutes, including news, time and environmental information.

## Code Explanation

### Constants and Initial Setup

The script defines constants for controlling the scrolling text, brightness settings, and initializes the Interstate75W object.

### Brightness Control

The `set_brightness` function allows manual adjustment of the display's brightness. Brightness is scaled from 0 to 100, and colors are updated accordingly.

### MQTT Message Handling

The `sub_cb` function handles incoming MQTT messages, splits the message into lines, and scrolls the text on the display.

### Main Function

The main function connects to the WiFi and MQTT broker, then enters a loop to keep the display and MQTT connection active.

## Troubleshooting

- **WiFi Connection Issues:**
  - Ensure your WiFi credentials in `config.py` are correct.
 
- **MQTT Connection Issues:**
  - Verify the MQTT broker address and credentials.
  - Ensure the broker is running and accessible.

- **Display Issues:**
  - Check the connections between the Interstate75W and the LED matrix.
  - Ensure the power supply is adequate for the LED matrix.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
