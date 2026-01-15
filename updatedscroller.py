from interstate75 import Interstate75
from mqtt_as import MQTTClient, config
from config import wifi_led, blue_led
import uasyncio as asyncio
import machine
import time
import gc

# --- Configuration ---
BRIGHTNESS = 100         
SCROLL_SPEED_MS = 50     
MIN_DISPLAY_SEC = 5      
HORIZ_BUFFER = 10        # 10 pixels buffer on left/right sides only
POST_SCROLL_DELAY = 2.0  # Seconds to hold background color after text leaves

# --- Setup --- edit the pixels below to your Matrix size  - ie 32x64 etc.
i75 = Interstate75(display=Interstate75.DISPLAY_INTERSTATE75_128X128)
graphics = i75.display
width = i75.width
height = i75.height

# --- Helpers ---
def create_pen(r, g, b):
    return graphics.create_pen(int(r*BRIGHTNESS/100), int(g*BRIGHTNESS/100), int(b*BRIGHTNESS/100))

BLACK  = create_pen(0, 0, 0)
WHITE  = create_pen(255, 255, 255)
RED    = create_pen(255, 0, 0)
GREEN  = create_pen(0, 255, 0)
BLUE   = create_pen(0, 0, 255)
YELLOW = create_pen(255, 255, 0)
ORANGE = create_pen(255, 165, 0)

# --- THE QUEUE ---
msg_queue = [("Booting...", ORANGE)]

def add_to_queue(text, color):
    print(f"Queued: {text}")
    msg_queue.append((text, color))

def wrap_text(text):
    words = text.split()
    lines = []
    current_line = ""
    # Use horizontal buffer for available width calculation
    available_width = width - (HORIZ_BUFFER * 2)
    
    for word in words:
        test_line = current_line + " " + word if current_line else word
        if graphics.measure_text(test_line, 1) <= available_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    if current_line: lines.append(current_line)
    return lines

def draw_frame(lines, y_pos, pen):
    graphics.set_pen(pen)
    graphics.clear()
    graphics.set_font("bitmap8")
    
    for i, line in enumerate(lines):
        line_y = y_pos + (i * 8)
        
        # Clipping: Now scrolls full screen (0 to height)
        # We check -8 to ensure the top line finishes scrolling off
        if line_y < -8 or line_y > height: 
            continue
            
        # Draw Shadow/Outline
        graphics.set_pen(BLACK)
        for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
            graphics.text(line, HORIZ_BUFFER + dx, line_y + dy, -1, 1)
            
        # Draw Main Text (X offset by HORIZ_BUFFER)
        graphics.set_pen(WHITE)
        graphics.text(line, HORIZ_BUFFER, line_y, -1, 1)
        
    i75.update(graphics)

# --- Smart Animation Task ---
async def display_task():
    graphics.set_pen(BLACK)
    graphics.clear()
    i75.update(graphics)

    while True:
        while len(msg_queue) == 0:
            await asyncio.sleep_ms(100)
        
        text, bg_pen = msg_queue.pop(0)
        lines = wrap_text(text)
        
        total_height = len(lines) * 8
        is_long = total_height > (height - 4) 

        gc.collect()
        gc.disable()

        try:
            if is_long:
                # 1. Continuous Scroll (Full height)
                y_pos = height
                target = -total_height
                while y_pos > target:
                    start = time.ticks_ms()
                    draw_frame(lines, y_pos, bg_pen)
                    y_pos -= 1
                    diff = time.ticks_diff(time.ticks_ms(), start)
                    delay = max(1, SCROLL_SPEED_MS - diff)
                    await asyncio.sleep_ms(delay)
            else:
                # 2. Center and Pause
                center_y = int((height - total_height) / 2)
                final_y = -total_height

                # Scroll In
                y_pos = height
                while y_pos > center_y:
                    start = time.ticks_ms()
                    draw_frame(lines, y_pos, bg_pen)
                    y_pos -= 1 
                    diff = time.ticks_diff(time.ticks_ms(), start)
                    delay = max(1, SCROLL_SPEED_MS - diff)
                    await asyncio.sleep_ms(delay)

                # Pause while centered
                gc.enable() 
                draw_frame(lines, center_y, bg_pen)
                await asyncio.sleep(MIN_DISPLAY_SEC)
                gc.collect() 
                gc.disable()

                # Scroll Out
                y_pos = center_y
                while y_pos > final_y:
                    start = time.ticks_ms()
                    draw_frame(lines, y_pos, bg_pen)
                    y_pos -= 1
                    diff = time.ticks_diff(time.ticks_ms(), start)
                    delay = max(1, SCROLL_SPEED_MS - diff)
                    await asyncio.sleep_ms(delay)

            # --- POST-SCROLL BUFFER ---
            # Hold the background color for a moment after text leaves
            graphics.set_pen(bg_pen)
            graphics.clear()
            i75.update(graphics)
            await asyncio.sleep(POST_SCROLL_DELAY)

        finally:
            gc.enable()
            gc.collect()

        # Reset screen to black
        graphics.set_pen(BLACK)
        graphics.clear()
        i75.update(graphics)

# --- Network Handlers ---
async def wifi_han(is_up):
    wifi_led(not is_up)
    if is_up: add_to_queue("WiFi Connected", BLUE)
    else: add_to_queue("WiFi Lost", RED)
    await asyncio.sleep(1)

async def conn_han(client):
    await client.subscribe('personal/ucfnaps/led/#', 1)
    add_to_queue("MQTT Ready", GREEN)

def sub_cb(topic, msg, retained):
    text = msg.decode('utf-8')
    color = BLUE
    if "Time" in text: color = YELLOW
    elif "News" in text: color = RED
    elif "Air" in text: color = GREEN
    add_to_queue(text, color)

async def heartbeat():
    s = True
    while True:
        await asyncio.sleep_ms(500)
        blue_led(s)
        s = not s

async def main(client):
    asyncio.create_task(display_task())
    while True:
        try:
            print("Connecting...")
            await client.connect()
            break 
        except OSError:
            add_to_queue("Net Retry...", RED)
            await asyncio.sleep(10) 
    while True:
        await asyncio.sleep(5)

config['subs_cb'] = sub_cb
config['wifi_coro'] = wifi_han
config['connect_coro'] = conn_han
config['clean'] = True
client = MQTTClient(config)
asyncio.create_task(heartbeat())

try:
    asyncio.run(main(client))
finally:
    client.close()
    asyncio.new_event_loop()
