from interstate75 import Interstate75, SWITCH_A, SWITCH_B
from mqtt_as import MQTTClient, config
from config import wifi_led, blue_led
import uasyncio as asyncio
import machine
import time

# Global text scaling factor (adjust this to change text size)
TEXT_SCALE = 1

# Global screen speed factor: increase to slow down scrolling, decrease to speed up.
GLOBAL_SCREEN_SPEED = 4.0

# Constants for controlling scrolling text
BACKGROUND_COLOUR = (0, 0, 0)  # Black background
HOLD_TIME = 2.0                # Seconds before scrolling starts
BLANK_SCREEN_TIME = 3          # Seconds to hold blank screen after scroll off
BUFFER_PIXELS = 2              # Extra buffer to ensure full scroll off
SCROLL_STEP = 1                # Scroll 1 pixel at a time
SCROLL_DELAY = 0.01 * GLOBAL_SCREEN_SPEED  # Delay in seconds for each scroll step

# Brightness settings
brightness = 100               # Initial brightness (0 to 100)

# State constants
STATE_PRE_SCROLL = 0
STATE_SCROLLING  = 1
STATE_POST_SCROLL = 2
STATE_BLANK_SCREEN = 3

# Create Interstate75 object and graphics surface for drawing
i75 = Interstate75(display=Interstate75.DISPLAY_INTERSTATE75_128X128)
graphics = i75.display
width = i75.width
height = i75.height

# Function to scale colors based on brightness
def scale_color(color, brightness):
    return tuple(int(c * brightness / 100) for c in color)

# Initialize colors with brightness scaling
def initialize_colors(brightness):
    black = graphics.create_pen(0, 0, 0)
    red = graphics.create_pen(*scale_color((255, 0, 0), brightness))
    green = graphics.create_pen(*scale_color((0, 255, 0), brightness))
    blue = graphics.create_pen(*scale_color((0, 0, 255), brightness))
    yellow = graphics.create_pen(*scale_color((255, 255, 0), brightness))
    orange = graphics.create_pen(*scale_color((255, 165, 0), brightness))
    white = graphics.create_pen(*scale_color((255, 255, 255), brightness))
    return black, red, green, blue, yellow, orange, white

black, red, green, blue, yellow, orange, white = initialize_colors(brightness)

# Function to update display with new colors
def update_display():
    graphics.set_pen(black)
    graphics.clear()
    i75.update(graphics)

# Function to set brightness manually
def set_brightness(level):
    global brightness, black, red, green, blue, yellow, orange, white
    brightness = level  # Use level directly (0 to 100)
    black, red, green, blue, yellow, orange, white = initialize_colors(brightness)
    update_display()

# Set initial brightness and background
set_brightness(brightness)
graphics.set_pen(black)
graphics.clear()
i75.update(graphics)
i75.set_led(0, 0, 0)

# --------------------- Drawing Helper Functions ---------------------
def set_background(color):
    graphics.set_pen(color)
    graphics.clear()

def draw_text_with_outline_multiline(text, x, y, scale=TEXT_SCALE, text_color=white, outline_color=black, line_height=8):
    # Use a font that supports scaling; here we assume "bitmap8" is available.
    graphics.set_font("bitmap8")
    lines = text.split('\n')
    scaled_line_height = line_height * scale
    for line_num, line in enumerate(lines):
        y_offset = y + (line_num * scaled_line_height)
        # Draw an outline for better contrast.
        offsets = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        graphics.set_pen(outline_color)
        for dx, dy in offsets:
            graphics.text(line, x + dx, y_offset + dy, -1, scale)
        graphics.set_pen(text_color)
        graphics.text(line, x, y_offset, -1, scale)

# --------------------- MQTT Message and Scrolling ---------------------
def sub_cb(topic, msg, retained):
    global STATE_PRE_SCROLL, STATE_SCROLLING, STATE_POST_SCROLL, STATE_BLANK_SCREEN, width, height
    print(f'Topic: "{topic.decode()}" Message: "{msg.decode()}" Retained: {retained}')
    state = STATE_PRE_SCROLL
    scroll = 0
    DATA = msg.decode('utf-8')
    # Add spaces before and after message so it scrolls cleanly
    MESSAGE = "     " + DATA + "     "

    # Wrap text: split MESSAGE into words and build lines that fit on screen.
    words = MESSAGE.split()
    lines = []
    current_line = ""
    # Use the global TEXT_SCALE in measuring text width.
    for word in words:
        if graphics.measure_text((current_line + " " + word).strip(), TEXT_SCALE) <= width - 2 * (BUFFER_PIXELS + 1):
            current_line = (current_line + " " + word).strip()
        else:
            lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    # Join lines into a multi-line string (separated by newline).
    message_lines = "\n".join(lines)
    num_lines = len(lines)
    # Calculate scaled line height from the font height (assumed 8 for bitmap8)
    line_height = 8 * TEXT_SCALE

    # Compute total scroll distance: text height plus extra buffer
    total_scroll = num_lines * line_height + height + BUFFER_PIXELS + 1
    mid_pause_done = False
    last_time = time.ticks_ms()

    while True:
        time_ms = time.ticks_ms()

        # Transition from pre-scroll (hold) to scrolling
        if state == STATE_PRE_SCROLL and time_ms - last_time > HOLD_TIME * 1000:
            state = STATE_SCROLLING
            last_time = time_ms

        # When scrolling, move the text by SCROLL_STEP when enough time has elapsed
        if state == STATE_SCROLLING and time_ms - last_time > SCROLL_DELAY * 1000:
            scroll += SCROLL_STEP

            # Add a mid-scroll pause for 5 seconds once halfway through
            if not mid_pause_done and scroll >= total_scroll // 2:
                print("Pausing mid-scroll for 5 seconds...")
                time.sleep(5)  # Blocking pause; adjust if needed
                mid_pause_done = True

            if scroll >= total_scroll:
                state = STATE_POST_SCROLL
                last_time = time.ticks_ms()
            else:
                last_time = time.ticks_ms()

        if state == STATE_POST_SCROLL and time.ticks_ms() - last_time > HOLD_TIME * 1000:
            state = STATE_BLANK_SCREEN
            last_time = time.ticks_ms()

        if state == STATE_BLANK_SCREEN and time.ticks_ms() - last_time > BLANK_SCREEN_TIME * 1000:
            set_background(black)
            i75.update(graphics)
            break

        # Update brightness (in case it has changed dynamically)
        black, red, green, blue, yellow, orange, white = initialize_colors(brightness)

        # Set background color based on message content (customize keywords as desired)
        if "Time" in MESSAGE:
            set_background(yellow)
        elif "News" in MESSAGE:
            set_background(red)
        elif "Weather" in MESSAGE:
            set_background(blue)
        elif "Air" in MESSAGE:
            set_background(green)
        else:
            set_background(blue)

        # Draw the multi-line text with an outline.
        # The vertical starting point is computed so that the text scrolls upward.
        draw_text_with_outline_multiline(message_lines,
                                         x=BUFFER_PIXELS + 1,
                                         y=height - scroll + BUFFER_PIXELS,
                                         scale=TEXT_SCALE,
                                         text_color=white,
                                         outline_color=black,
                                         line_height=8)
        i75.update(graphics)
        time.sleep(SCROLL_DELAY)
        
# --------------------- Async Helper Functions ---------------------
async def heartbeat():
    s = True
    while True:
        await asyncio.sleep_ms(500)
        blue_led(s)
        s = not s

async def wifi_han(state):
    wifi_led(not state)
    print('Wifi is', 'up' if state else 'down')
    await asyncio.sleep(1)

async def conn_han(client):
    await client.subscribe('personal/ucfnaps/led/#', 1)

async def main(client):
    try:
        await client.connect()
    except OSError:
        print('Connection failed.')
        machine.reset()
        return
    while True:
        await asyncio.sleep(5)

# --------------------- MQTT and Scheduler Setup ---------------------
config['subs_cb'] = sub_cb
config['wifi_coro'] = wifi_han
config['connect_coro'] = conn_han
config['clean'] = True

MQTTClient.DEBUG = True  # Optional debug output
client = MQTTClient(config)

asyncio.create_task(heartbeat())

try:
    asyncio.run(main(client))
finally:
    client.close()
    asyncio.new_event_loop()
