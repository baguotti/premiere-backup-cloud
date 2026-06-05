import os
import sys
import json
import subprocess
import customtkinter as ctk
from tkinter import filedialog, messagebox

# Set modern theme
ctk.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

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

def is_service_running():
    try:
        result = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
        return "com.riccardo.premierebackup" in result.stdout
    except Exception:
        return False

class BackupUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Premiere Auto-Backup")
        self.geometry("700x480")
        self.minsize(600, 400)
        
        self.config = load_config()
        
        # Grid Layout
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Header
        self.header = ctk.CTkLabel(self, text="Watched Premiere Folders", font=ctk.CTkFont(size=24, weight="bold"))
        self.header.grid(row=0, column=0, padx=25, pady=(25, 15), sticky="w")
        
        # Scrollable Frame for List
        self.scrollable_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_frame.grid(row=1, column=0, padx=25, pady=(0, 25), sticky="nsew")
        self.scrollable_frame.grid_columnconfigure(0, weight=1)
        
        # Bottom controls
        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.grid(row=2, column=0, padx=25, pady=(0, 25), sticky="ew")
        self.bottom_frame.grid_columnconfigure(0, weight=1)
        self.bottom_frame.grid_columnconfigure(1, weight=0)
        self.bottom_frame.grid_columnconfigure(2, weight=0)
        
        # Status area
        self.status_label = ctk.CTkLabel(self.bottom_frame, text="Status: Checking...", font=ctk.CTkFont(size=14))
        self.status_label.grid(row=0, column=0, sticky="w", padx=5)
        
        self.btn_toggle = ctk.CTkButton(self.bottom_frame, text="Toggle Service", command=self.toggle_service, width=140, height=36, font=ctk.CTkFont(size=13, weight="bold"))
        self.btn_toggle.grid(row=0, column=1, padx=10)
        
        self.btn_add = ctk.CTkButton(self.bottom_frame, text="+ Add Folder", command=self.add_folder, width=140, height=36, font=ctk.CTkFont(size=13, weight="bold"))
        self.btn_add.grid(row=0, column=2, padx=0)
        
        self.refresh_list()
        self.update_status()

    def refresh_list(self):
        # Clear existing
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
            
        jobs = self.config.get("sync_jobs", [])
        if not jobs:
            lbl = ctk.CTkLabel(self.scrollable_frame, text="No folders added yet.\nClick '+ Add Folder' below to begin.", text_color="gray", font=ctk.CTkFont(size=14))
            lbl.grid(row=0, column=0, pady=50)
            return

        for i, job in enumerate(jobs):
            # Item frame
            item_frame = ctk.CTkFrame(self.scrollable_frame, corner_radius=10)
            item_frame.grid(row=i, column=0, padx=5, pady=5, sticky="ew")
            item_frame.grid_columnconfigure(0, weight=1)
            
            lbl_path = ctk.CTkLabel(item_frame, text=job["source"], anchor="w", font=ctk.CTkFont(size=13))
            lbl_path.grid(row=0, column=0, padx=20, pady=15, sticky="w")
            
            btn_remove = ctk.CTkButton(item_frame, text="Remove", width=80, height=28, fg_color="#ff5252", hover_color="#d32f2f", 
                                       command=lambda f=job["source"]: self.remove_folder(f),
                                       font=ctk.CTkFont(size=12, weight="bold"))
            btn_remove.grid(row=0, column=1, padx=15, pady=15)

    def add_folder(self):
        folder_path = filedialog.askdirectory(title="Select Premiere Project Folder")
        if not folder_path:
            return
            
        # Check if already exists
        for job in self.config.get("sync_jobs", []):
            if job["source"] == folder_path:
                messagebox.showinfo("Info", "This folder is already being watched.")
                return
                
        folder_name = os.path.basename(folder_path.rstrip('/'))
        dest_path = os.path.join(DEFAULT_DEST_BASE, folder_name)
        
        new_job = {
            "source": folder_path,
            "destination": dest_path
        }
        
        if "sync_jobs" not in self.config:
            self.config["sync_jobs"] = []
            
        self.config["sync_jobs"].append(new_job)
        save_config(self.config)
        self.refresh_list()
        
        if is_service_running():
            self.restart_service()
            
    def remove_folder(self, folder):
        if messagebox.askyesno("Confirm", f"Stop backing up:\n{folder}?"):
            self.config["sync_jobs"] = [j for j in self.config["sync_jobs"] if j["source"] != folder]
            save_config(self.config)
            self.refresh_list()
            
            if is_service_running():
                self.restart_service()

    def update_status(self):
        running = is_service_running()
        if running:
            self.status_label.configure(text="● Background Service: Active", text_color="#28a745")
            self.btn_toggle.configure(text="Stop Service", fg_color="transparent", border_width=2, text_color=("black", "white"), hover_color=("gray90", "gray20"))
        else:
            self.status_label.configure(text="○ Background Service: Stopped", text_color="#ff5252")
            self.btn_toggle.configure(text="Start Service", fg_color="#007bff", border_width=0, text_color="white", hover_color="#0056b3")
            
        self.after(2000, self.update_status)

    def toggle_service(self):
        if is_service_running():
            subprocess.run(["launchctl", "unload", "-w", PLIST_PATH])
        else:
            if not os.path.exists(PLIST_PATH):
                messagebox.showerror("Error", "The launchd background service file is missing!")
                return
            subprocess.run(["launchctl", "load", "-w", PLIST_PATH])
        self.update_status()

    def restart_service(self):
        subprocess.run(["launchctl", "unload", "-w", PLIST_PATH])
        subprocess.run(["launchctl", "load", "-w", PLIST_PATH])

if __name__ == "__main__":
    app = BackupUI()

    if sys.platform == "darwin":
        try:
            from AppKit import NSApplication, NSImage
            script_dir = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.abspath(os.path.join(script_dir, "..", "icon", "Icon_256x256.png"))
            if os.path.exists(icon_path):
                ns_app = NSApplication.sharedApplication()
                icon_image = NSImage.alloc().initWithContentsOfFile_(icon_path)
                if icon_image:
                    ns_app.setApplicationIconImage_(icon_image)
        except Exception:
            pass

    os.system('''/usr/bin/osascript -e 'tell app "Finder" to set frontmost of process "Python" to true' ''')
    app.mainloop()
