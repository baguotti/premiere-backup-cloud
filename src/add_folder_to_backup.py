import sys
import os
import json
import subprocess

CONFIG_FILE = os.path.expanduser("~/.premiere_backup.json")
PLIST_PATH = os.path.expanduser("~/Library/LaunchAgents/com.riccardo.premierebackup.plist")
DEFAULT_DEST_BASE = "/Users/riccardofusetti/Library/CloudStorage/GoogleDrive-fusetti.riccardo@gmail.com/My Drive/Premiere Backups"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {"sync_jobs": []}
    with open(CONFIG_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {"sync_jobs": []}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def get_destination_folder_name(folder_path):
    path = os.path.normpath(folder_path)
    parts = path.split(os.sep)
    for i in range(len(parts) - 1, -1, -1):
        if parts[i].upper() == "01_PROJECTS" and i > 0:
            return parts[i-1]
    return os.path.basename(path)

def main():
    if len(sys.argv) < 2:
        return
        
    folder_path = sys.argv[1]
    if not os.path.isdir(folder_path):
        return
        
    config = load_config()
    
    # Check if already exists
    for job in config.get("sync_jobs", []):
        if job["source"] == folder_path:
            return
            
    folder_name = get_destination_folder_name(folder_path)
    dest_path = os.path.join(DEFAULT_DEST_BASE, folder_name)
    
    new_job = {
        "source": folder_path,
        "destination": dest_path
    }
    
    if "sync_jobs" not in config:
        config["sync_jobs"] = []
        
    config["sync_jobs"].append(new_job)
    save_config(config)
    
    # Check if service is running, if so restart it
    try:
        result = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
        if "com.riccardo.premierebackup" in result.stdout:
            subprocess.run(["launchctl", "unload", "-w", PLIST_PATH])
            subprocess.run(["launchctl", "load", "-w", PLIST_PATH])
    except Exception:
        pass
        
    # Show notification
    os.system(f'''osascript -e 'display notification "Added to Premiere Auto-Backup" with title "{folder_name}"' ''')

if __name__ == "__main__":
    main()
