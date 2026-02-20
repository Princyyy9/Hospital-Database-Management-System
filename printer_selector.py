import tkinter as tk
from tkinter import ttk

class PrinterSelector(tk.Toplevel):
    def __init__(self, master, on_select, initial_printer=None, printers=None):
        super().__init__(master)
        self.title("Select Printer")
        self.geometry("400x180")
        self.resizable(False, False)
        self.grab_set()
        self.selected_printer = tk.StringVar()
        printers = printers or []
        if not printers:
            printers = ["LPT1"]  # fallback
        if initial_printer and initial_printer in printers:
            self.selected_printer.set(initial_printer)
        else:
            self.selected_printer.set(printers[0])

        ttk.Label(self, text="Available Printers:", font=("Arial", 12)).pack(pady=(16,4))
        printer_combo = ttk.Combobox(self, values=printers, textvariable=self.selected_printer, font=("Arial", 11), state="readonly", width=36)
        printer_combo.pack(pady=(0,10))

        ttk.Button(self, text="Select", command=self._select).pack(pady=(8,2))
        ttk.Button(self, text="Cancel", command=self.destroy).pack()

        self.on_select = on_select

    def _select(self):
        printer = self.selected_printer.get()
        self.on_select(printer)
        self.destroy()