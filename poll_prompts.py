
import json
import time
import sys
from pathlib import Path

PROMPTS_FILE = Path.home() / ".antigravity_prompts.json"
TIMEOUT = 60

def poll():
    start = time.time()
    print(f"Polling {PROMPTS_FILE} for {TIMEOUT}s...")
    
    while time.time() - start < TIMEOUT:
        if PROMPTS_FILE.exists():
            try:
                content = PROMPTS_FILE.read_text().strip()
                if content:
                    data = json.loads(content)
                    if data:
                        print(f"FOUND: {json.dumps(data)}")
                        return
            except Exception as e:
                print(f"Error reading: {e}")
        
        time.sleep(1)
    
    print("TIMEOUT")

if __name__ == "__main__":
    poll()
