import json
import os

TEMP_FILE = "temp_daily.json"           # You edit this file manually
CURRENT_AFFAIRS_FILE = "current_affairs.json"  # GitHub updates this automatically at 5:00 AM

def main():
    # 1. Check if temp file exists
    if not os.path.exists(TEMP_FILE):
        print(f"❌ Error: {TEMP_FILE} not found! Please create it first.")
        return

    # 2. Load the data from temp_daily.json
    with open(TEMP_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 3. Write the EXACT SAME data to current_affairs.json (keeps it as a raw array [...])
    with open(CURRENT_AFFAIRS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    print(f"✅ Successfully copied {TEMP_FILE} to {CURRENT_AFFAIRS_FILE} as a raw array!")

if __name__ == "__main__":
    main()
