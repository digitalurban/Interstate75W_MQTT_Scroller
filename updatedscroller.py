from interstate75 import Interstate75
from mqtt_as import MQTTClient, config
from config import wifi_led, blue_led
import uasyncio as asyncio
import machine
import time
import gc

# --- Configuration ---
BRIGHTNESS = 100        
SCROLL_SPEED_MS = 50    # 50ms is smooth for single core
MIN_DISPLAY_SEC = 5     # How long to pause on the message

# --- Setup ---
i75 = Interstate75(display=Interstate75.DISPLAY_INTERSTATE75_64X32)
graphics = i75.display
width = i75.width
height = i75.height

# --- Helpers ---
def create_pen(r, g, b):
    return graphics.create_pen(int(r*BRIGHTNESS/100), int(g*BRIGHTNESS/100), int(b*BRIGHTNESS/100))

# Pre-define colors to save memory
BLACK  = create_pen(0, 0, 0)
WHITE  = create_pen(255, 255, 255)
RED    = create_pen(255, 0, 0)
GREEN  = create_pen(0, 255, 0)
BLUE   = create_pen(0, 0, 255)
YELLOW = create_pen(255, 255, 0)
ORANGE = create_pen(255, 165, 0)

state = { "text": "Booting...", "color": ORANGE, "new_msg": True }

def update_status(text, color):
    # Only update if changed to avoid unnecessary processing
    if state["text"] != text:
        state["text"] = text
        state["color"] = color
        state["new_msg"] = True
        print(f"Status: {text}")

def wrap_text(text):
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = current_line + " " + word if current_line else word
        if graphics.measure_text(test_line, 1) <= width - 4:
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
        # Optimization: Don't draw off-screen
        if line_y < -10 or line_y > height: continue
        
        graphics.set_pen(BLACK)
        for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
            graphics.text(line, 2 + dx, line_y + dy, -1, 1)
        graphics.set_pen(WHITE)
        graphics.text(line, 2, line_y, -1, 1)
    i75.update(graphics)

# --- The Safe Animation Task ---
async def display_task():
    graphics.set_pen(BLACK)
    graphics.clear()
    i75.update(graphics)

    while True:
        # 1. Wait for data
        while not state["new_msg"]:
            await asyncio.sleep_ms(100)
        
        # 2. Setup
        state["new_msg"] = False
        text = state["text"]
        bg_pen = state["color"]
        lines = wrap_text(text)
        total_height = len(lines) * 8
        center_y = int((height - total_height) / 2)
        final_y = -(total_height + 2)

        # 3. CRITICAL: GC Lock
        # We clean memory NOW, then turn off the "janitor" (Garbage Collector)
        # so it doesn't interrupt our smooth scroll.
        gc.collect()
        gc.disable()

        try:
            # Scroll In
            y_pos = height
            while y_pos > center_y:
                start = time.ticks_ms()
                draw_frame(lines, y_pos, bg_pen)
                y_pos -= 1 
                
                # Compensated sleep
                diff = time.ticks_diff(time.ticks_ms(), start)
                delay = max(1, SCROLL_SPEED_MS - diff)
                await asyncio.sleep_ms(delay)

            # Pause (Unlock GC briefly)
            gc.enable() 
            draw_frame(lines, center_y, bg_pen)
            await asyncio.sleep(MIN_DISPLAY_SEC)
            gc.collect() # Clean again before exit
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

        finally:
            # ALWAYS re-enable GC when done, even if we crash
            gc.enable()
            gc.collect()

        # Clear
        graphics.set_pen(BLACK)
        graphics.clear()
        i75.update(graphics)

# --- Network Handlers ---
async def wifi_han(is_up):
    wifi_led(not is_up)
    if is_up: update_status("WiFi Connected", BLUE)
    else: update_status("WiFi Lost", RED)
    await asyncio.sleep(1)

async def conn_han(client):
    await client.subscribe('personal/ucfnaps/led/#', 1)
    update_status("MQTT Ready", GREEN)

def sub_cb(topic, msg, retained):
    text = msg.decode('utf-8')
    print(f"Rec'd: {text}")
    color = BLUE
    if "Time" in text: color = YELLOW
    elif "News" in text: color = RED
    elif "Air" in text: color = GREEN
    update_status(text, color)

async def heartbeat():
    s = True
    while True:
        await asyncio.sleep_ms(500)
        blue_led(s)
        s = not s

async def main(client):
    asyncio.create_task(display_task())
    try:
        await client.connect()
    except OSError:
        print("Connection failed. Retrying...")
        machine.reset()
        
    while True:
        await asyncio.sleep(5)

# --- Execution ---
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
