from interstate75 import Interstate75, SWITCH_A, SWITCH_B
from mqtt_as import MQTTClient, config
from config import wifi_led, blue_led
import uasyncio as asyncio
import machine
import time

# Constants for controlling scrolling text
BACKGROUND_COLOUR = (0, 0, 0)  # Black background to turn off the screen
HOLD_TIME = 2.0
BLANK_SCREEN_TIME = 3
BUFFER_PIXELS = 2  # Increased buffer to ensure full scroll off
SCROLL_SPEED_LEVEL = 10  # Set the desired scrolling speed level (1 to 10)
SCROLL_SPEED = 1 / SCROLL_SPEED_LEVEL  # Convert to a delay in seconds

# Brightness settings
brightness = 100  # Initial brightness (0 to 100)

# State constants
STATE_PRE_SCROLL = 0
STATE_SCROLLING = 1
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

# Set initial brightness
set_brightness(brightness)

# Set initial background
graphics.set_pen(black)
graphics.clear()
i75.update(graphics)
i75.set_led(0, 0, 0)

# Display-related functions
def set_background(color):
    graphics.set_pen(color)
    graphics.clear()

def draw_text_with_outline_multiline(text, x, y, scale=1, text_color=white, outline_color=black, line_height=8):
    graphics.set_font("bitmap8")
    lines = text.split('\n')
    for line_num, line in enumerate(lines):
        y_offset = y + (line_num * line_height * scale)
        graphics.set_pen(outline_color)
        offsets = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        for dx, dy in offsets:
            graphics.text(line, x + dx, y_offset + dy, -1, scale)
        graphics.set_pen(text_color)
        graphics.text(line, x, y_offset, -1, scale)

# MQTT Message Subscription and Display
def sub_cb(topic, msg, retained):
    global STATE_PRE_SCROLL, STATE_SCROLLING, STATE_POST_SCROLL, STATE_BLANK_SCREEN, width, height, black, red, green, blue, yellow, orange, white, brightness
    print(f'Topic: "{topic.decode()}" Message: "{msg.decode()}" Retained: {retained}')
    state = STATE_PRE_SCROLL
    scroll = 0
    DATA = msg.decode('utf-8')
    MESSAGE = "     " + DATA + "     "

    # Split the message into words and then into lines that fit the screen width.
    words = MESSAGE.split()
    lines = []
    current_line = ""
    for word in words:
        if graphics.measure_text(current_line + " " + word, 1) <= width - 2 * (BUFFER_PIXELS + 1):
            current_line += " " + word
        else:
            lines.append(current_line.strip())
            current_line = word
    if current_line:
        lines.append(current_line.strip())

    message_lines = "\n".join(lines)
    num_lines = len(lines)
    line_height = 8  # Font height for scale 1

    # Compute the total scroll distance and initialize the mid-scroll pause flag
    total_scroll = num_lines * line_height + height + BUFFER_PIXELS + 1
    mid_pause_done = False

    last_time = time.ticks_ms()

    while True:
        time_ms = time.ticks_ms()

        if state == STATE_PRE_SCROLL and time_ms - last_time > HOLD_TIME * 1000:
            state = STATE_SCROLLING
            last_time = time_ms

        if state == STATE_SCROLLING and time_ms - last_time > SCROLL_SPEED * 1000:
            scroll += 1

            # Check if we have reached mid-scroll and haven't paused yet.
            if not mid_pause_done and scroll >= total_scroll // 2:
                print("Pausing mid-scroll for 5 seconds...")
                time.sleep(5)  # Pause the scrolling for 5 seconds
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

        # Update brightness for dynamic adjustment
        black, red, green, blue, yellow, orange, white = initialize_colors(brightness)

        # Set background based on message type
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

        # Draw the text with an outline
        draw_text_with_outline_multiline(message_lines,
                                         x=BUFFER_PIXELS + 1,
                                         y=height - scroll + BUFFER_PIXELS,
                                         scale=1,
                                         text_color=white,
                                         outline_color=black)

        i75.update(graphics)
        time.sleep(0.001)
# Demonstrate scheduler is operational.
async def heartbeat():
    s = True
    while True:
        await asyncio.sleep_ms(500)
        blue_led(s)
        s = not s

async def wifi_han(state):
    wifi_led(not state)
    print('Wifi is ', 'up' if state else 'down')
    await asyncio.sleep(1)

# If you connect with clean_session True, must re-subscribe (MQTT spec 3.1.2.4)
async def conn_han(client):
    # MQTT Subscribe Topic
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

# Define configuration
config['subs_cb'] = sub_cb
config['wifi_coro'] = wifi_han
config['connect_coro'] = conn_han
config['clean'] = True

# Set up client
MQTTClient.DEBUG = True  # Optional
client = MQTTClient(config)

asyncio.create_task(heartbeat())

try:
    asyncio.run(main(client))
finally:
    client.close()  # Prevent LmacRxBlk:1 errors
    asyncio.new_event_loop()