from gui import ShScriptHubApp
import tkinter as tk
from utils import get_resource_path
import os

def main():
    root = tk.Tk()
    
    icon_path = get_resource_path('assets/icon.ico')
    if os.path.exists(icon_path):
        try:
            root.iconbitmap(default=icon_path)
        except Exception as e:
            print(f"Warning: Could not set icon: {e}")
    
    app = ShScriptHubApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
