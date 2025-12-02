"""
Interstate75 MQTT Message Scroller (Dual Core)

Hardware: Pimoroni Interstate75 (RP2040)
Libraries: pimoroni-interstate75, mqtt_as
Features:
 - Dual Core architecture (Core 0 for Wifi/MQTT, Core 1 for Animation)
 - Smooth, drift-compensated scrolling
 - Garbage Collector locking to prevent animation stutter
 - Atomic message display (enters, pauses, exits before accepting new data)
"""

from interstate75 import Interstate75
from mqtt_as import MQTTClient, config
from config import wifi_led, blue_led
import uasyncio as asyncio
import machine
import time
import gc
import _thread

# ==========================================
# CONFIGURATION
# ==========================================
BRIGHTNESS = 100         # Display brightness (0-100)
SCROLL_SPEED_MS = 60     # Delay between pixel moves (Higher = Slower)
MIN_DISPLAY_SEC = 5      # How long to pause in the center to read the text

# ==========================================
# DISPLAY SETUP
# ==========================================
i75 = Interstate75(display=Interstate75.DISPLAY_INTERSTATE75_64X32)
graphics = i75.display
width = i75.width
height = i75.height

# --- Color Helpers ---
def create_pen(r, g, b):
    # Scale RGB values based on brightness
    return graphics.create_pen(
        int(r * BRIGHTNESS / 100),
        int(g * BRIGHTNESS / 100),
        int(b * BRIGHTNESS / 100)
    )

# Pre-defined pens to save memory during runtime
BLACK  = create_pen(0, 0, 0)
WHITE  = create_pen(255, 255, 255)
RED    = create_pen(255, 0, 0)
GREEN  = create_pen(0, 255, 0)
BLUE   = create_pen(0, 0, 255)
YELLOW = create_pen(255, 255, 0)
ORANGE = create_pen(255, 165, 0)

# ==========================================
# SHARED STATE
# ==========================================
# This dictionary is shared between Core 0 (Network) and Core 1 (Display).
state = {
    "text": "Booting...",   
    "color": ORANGE,        
    "new_msg": True         
}

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def update_status(text, color):
    """Updates the shared state. Called by Core 0."""
    # Only update if the text is actually different
    if state["text"] != text:
        state["text"] = text
        state["color"] = color
        state["new_msg"] = True
        print(f"[Status Update] {text}")

def wrap_text(text):
    """Wraps text to fit the width of the display."""
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
    """Draws a single frame of text at a specific Y position."""
    graphics.set_pen(pen)
    graphics.clear()
    
    graphics.set_font("bitmap8")
    for i, line in enumerate(lines):
        line_y = y_pos + (i * 8)
        
        # Optimization: Skip drawing lines that are off-screen
        if line_y < -10 or line_y > height: continue
        
        # Draw Black Outline (4 directions)
        graphics.set_pen(BLACK)
        for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
            graphics.text(line, 2 + dx, line_y + dy, -1, 1)
        
        # Draw White Text
        graphics.set_pen(WHITE)
        graphics.text(line, 2, line_y, -1, 1)
        
    i75.update(graphics)

# ==========================================
# CORE 1: DISPLAY LOOP (BLOCKING)
# ==========================================
def run_display_core_1():
    """
    Runs on the second processor core. 
    Handles animation independently of network latency.
    """
    print("[Core 1] Display Thread Started")
    
    # clear screen on boot
    graphics.set_pen(BLACK)
    graphics.clear()
    i75.update(graphics)

    while True:
        try:
            # 1. IDLE: Wait for new data
            while not state["new_msg"]:
                time.sleep(0.1)
            
            # 2. LOAD DATA
            state["new_msg"] = False
            text = state["text"]
            bg_pen = state["color"]
            lines = wrap_text(text)
            total_height = len(lines) * 8
            
            # Calculate positions
            center_y = int((height - total_height) / 2)
            final_y = -(total_height + 2)

            # 3. CRITICAL SECTION: ANIMATION
            # We disable the Garbage Collector (GC) during movement.
            # This prevents the processor from pausing to clean memory 
            # while we are scrolling, eliminating visual stutter.
            gc.collect()
            gc.disable()

            # --- PHASE 1: SCROLL IN (Bottom to Center) ---
            y_pos = height
            while y_pos > center_y:
                start = time.ticks_ms()
                draw_frame(lines, y_pos, bg_pen)
                y_pos -= 1 
                
                # Compensate for draw time to keep speed consistent
                diff = time.ticks_diff(time.ticks_ms(), start)
                delay = max(0, SCROLL_SPEED_MS - diff)
                time.sleep_ms(int(delay))

            # --- PHASE 2: PAUSE (Read Time) ---
            # Re-enable GC briefly while waiting
            gc.enable()
            draw_frame(lines, center_y, bg_pen)
            time.sleep(MIN_DISPLAY_SEC)
            
            # Disable GC again for exit
            gc.collect()
            gc.disable()

            # --- PHASE 3: SCROLL OUT (Center to Top) ---
            y_pos = center_y
            while y_pos > final_y:
                start = time.ticks_ms()
                draw_frame(lines, y_pos, bg_pen)
                y_pos -= 1
                
                diff = time.ticks_diff(time.ticks_ms(), start)
                delay = max(0, SCROLL_SPEED_MS - diff)
                time.sleep_ms(int(delay))

        except Exception as e:
            print(f"[Core 1 Error] {e}")
        
        finally:
            # Ensure GC is always re-enabled if something goes wrong
            gc.enable()
            gc.collect()

        # Clear screen after message sequence completes
        graphics.set_pen(BLACK)
        graphics.clear()
        i75.update(graphics)

# ==========================================
# CORE 0: NETWORK & MQTT (ASYNC)
# ==========================================

async def wifi_handler(is_up):
    """Callback for WiFi status changes"""
    wifi_led(not is_up)
    if is_up:
        update_status("WiFi Connected", BLUE)
    else:
        update_status("WiFi Lost", RED)
    await asyncio.sleep(1)

async def conn_handler(client):
    """Callback for MQTT connection success"""
    await client.subscribe('personal/ucfnaps/led/#', 1)
    update_status("MQTT Ready", GREEN)

def sub_cb(topic, msg, retained):
    """Callback for incoming MQTT messages"""
    text = msg.decode('utf-8')
    print(f"[MQTT] Rec'd: {text}")
    
    # Color logic based on keywords
    color = BLUE
    if "Time" in text: color = YELLOW
    elif "News" in text: color = RED
    elif "Air" in text: color = GREEN
    
    update_status(text, color)

async def heartbeat():
    """Blinks LED to show system is alive"""
    s = True
    while True:
        await asyncio.sleep_ms(500)
        blue_led(s)
        s = not s

async def main(client):
    try:
        await client.connect()
    except OSError:
        update_status("Connection Failed", RED)
        machine.reset()
    
    # Keep the main loop alive
    while True:
        await asyncio.sleep(5)

# ==========================================
# MAIN EXECUTION
# ==========================================

# Configure MQTT
config['subs_cb'] = sub_cb
config['wifi_coro'] = wifi_handler
config['connect_coro'] = conn_handler
config['clean'] = True

# 1. Start the Display Thread on Core 1
_thread.start_new_thread(run_display_core_1, ())

# 2. Start the Network Loop on Core 0
client = MQTTClient(config)
asyncio.create_task(heartbeat())

try:
    asyncio.run(main(client))
finally:
    client.close()
    asyncio.new_event_loop()
