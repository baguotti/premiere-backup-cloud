import os
import json
import time
import shutil
from pathlib import Path
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

CONFIG_FILE = os.path.expanduser("~/.premiere_backup.json")

def ensure_gdrive_running():
    try:
        result = subprocess.run(["pgrep", "-f", "Google Drive"], capture_output=True, text=True)
        if not result.stdout.strip():
            log("Google Drive is not running. Starting it in the background...")
            subprocess.run(["open", "-g", "-a", "Google Drive"])
            time.sleep(3) # Wait for it to mount
    except Exception as e:
        log(f"Error checking/starting Google Drive: {e}")

def log(message):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)

import threading

SYNC_DELAY_SECONDS = 10

class PRProjHandler(FileSystemEventHandler):
    def __init__(self, source_base, destination_base):
        self.source_base = Path(source_base).resolve()
        self.destination_base = Path(destination_base).resolve()
        self.timers = {}
        self.lock = threading.Lock()

    def schedule_sync(self, path_str):
        with self.lock:
            if path_str in self.timers:
                self.timers[path_str].cancel()
            
            timer = threading.Timer(SYNC_DELAY_SECONDS, self.execute_sync, args=[path_str])
            self.timers[path_str] = timer
            timer.start()

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.prproj'):
            self.schedule_sync(event.src_path)

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.prproj'):
            self.schedule_sync(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory and event.src_path.endswith('.prproj'):
            self.schedule_sync(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            if event.src_path.endswith('.prproj'):
                self.schedule_sync(event.src_path)
            if event.dest_path.endswith('.prproj'):
                self.schedule_sync(event.dest_path)

    def execute_sync(self, path_str):
        with self.lock:
            if path_str in self.timers:
                del self.timers[path_str]

        src_path = Path(path_str).resolve()
        
        try:
            rel_path = src_path.relative_to(self.source_base)
        except ValueError:
            return
            
        dest_path = self.destination_base / rel_path
        
        # If the file currently exists locally, it's a copy operation
        if src_path.exists():
            ensure_gdrive_running()
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Check if we need to copy
            if dest_path.exists():
                src_mtime = src_path.stat().st_mtime
                dest_mtime = dest_path.stat().st_mtime
                if abs(src_mtime - dest_mtime) < 1.0 and src_path.stat().st_size == dest_path.stat().st_size:
                    return
            
            try:
                shutil.copy2(src_path, dest_path)
                log(f"Backed up: {rel_path} -> {self.destination_base.name}")
            except Exception as e:
                log(f"Error backing up {rel_path}: {e}")
                
        # If the file NO LONGER exists locally, it's a delete operation
        else:
            if dest_path.exists():
                try:
                    dest_path.unlink()
                    log(f"Deleted backup: {rel_path}")
                except Exception as e:
                    log(f"Error deleting backup {rel_path}: {e}")

def load_config():
    if not os.path.exists(CONFIG_FILE):
        log(f"Error: {CONFIG_FILE} not found!")
        return None
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def initial_sync(source_base, destination_base):
    log(f"Running initial scan for: {source_base}")
    source_path = Path(source_base).resolve()
    destination_path = Path(destination_base).resolve()
    
    if not source_path.exists():
        return
        
    ensure_gdrive_running()
        
    copied_count = 0
    for root, _, files in os.walk(source_path):
        for file in files:
            if file.endswith('.prproj'):
                src_file = Path(root) / file
                rel_path = src_file.relative_to(source_path)
                dest_file = destination_path / rel_path
                
                # Check if it needs copy
                needs_copy = True
                if dest_file.exists():
                    src_mtime = src_file.stat().st_mtime
                    dest_mtime = dest_file.stat().st_mtime
                    if abs(src_mtime - dest_mtime) < 1.0 and src_file.stat().st_size == dest_file.stat().st_size:
                        needs_copy = False
                
                if needs_copy:
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        shutil.copy2(src_file, dest_file)
                        copied_count += 1
                    except Exception as e:
                        log(f"Error copying {rel_path} during initial sync: {e}")
                        
    if copied_count > 0:
        log(f"Initial scan completed. Synced {copied_count} files.")
        
    # Check for orphaned files in destination and delete them
    deleted_count = 0
    if destination_path.exists():
        for root, _, files in os.walk(destination_path):
            for file in files:
                if file.endswith('.prproj'):
                    dest_file = Path(root) / file
                    rel_path = dest_file.relative_to(destination_path)
                    src_file = source_path / rel_path
                    
                    if not src_file.exists():
                        try:
                            dest_file.unlink()
                            deleted_count += 1
                            log(f"Deleted orphaned backup: {rel_path}")
                        except Exception as e:
                            log(f"Error deleting orphaned backup {rel_path}: {e}")
                            
    if copied_count == 0 and deleted_count == 0:
        log("Initial scan completed. All files up to date.")
    elif deleted_count > 0:
        log(f"Cleaned up {deleted_count} orphaned files.")

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    config = load_config()
    if not config or "sync_jobs" not in config:
        log("Invalid or missing configuration.")
        return

    observer = Observer()
    watchers_started = 0
    
    for job in config["sync_jobs"]:
        source = job.get("source")
        destination = job.get("destination")
        
        if not source or not destination:
            log(f"Skipping invalid job: {job}")
            continue
            
        if not os.path.exists(source):
            log(f"Warning: Source folder does not exist: {source}")
            continue
            
        # Perform initial sync
        initial_sync(source, destination)
        
        handler = PRProjHandler(source, destination)
        observer.schedule(handler, source, recursive=True)
        log(f"Watching: {source}")
        log(f"Backup to: {destination}")
        log("-" * 50)
        watchers_started += 1
        
    if watchers_started == 0:
        log("No valid folders to watch. Please check your config.json paths.")
        return

    observer.start()
    log("Auto-Backup is running... Press Ctrl+C to stop.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        log("Stopping auto-backup.")
        
    observer.join()

if __name__ == "__main__":
    main()

