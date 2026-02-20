import json
import os
try:
    import win32print
except ImportError:
    win32print = None

CONFIG_FILE = "printer_config.json"

def list_printers():
    printers = []
    if win32print:
        for flags, description, name, comment in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS):
            printers.append(name)
    else:
        printers = ["LPT1"]  # fallback for dot-matrix only
    return printers

def save_printer_choice(printer_name):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"printer": printer_name}, f)

def load_printer_choice():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)["printer"]
    except Exception:
        return "default"