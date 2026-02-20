import sys

# SINGLE INSTANCE CHECK - Only for Windows
try:
    import win32event
    import win32api
    import winerror
except ImportError:
    win32event = None  # pywin32 not installed

if win32event:
    mutex = win32event.CreateMutex(None, False, "PatientPythonAppMutex")
    last_error = win32api.GetLastError()
    if last_error == winerror.ERROR_ALREADY_EXISTS:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Already Running", "The Patient Management app is already running.")
        sys.exit(0)

import tkinter as tk
from ui import PatientRegistrationApp

def main():
    root = tk.Tk()
    app = PatientRegistrationApp(root)
    root.protocol("WM_DELETE_WINDOW", app.close_app)
    root.mainloop()

if __name__ == "__main__":
    main()

