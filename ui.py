import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from PIL import Image, ImageTk
from tkcalendar import DateEntry
import threading
import datetime
import re
import csv
import logging
from printer_manager import list_printers, save_printer_choice, load_printer_choice

# Import utility functions
import utils as ut

# Import dot matrix print function
from dot_matrix_print_utils import print_ipd_bed_head_ticket, print_epd_card_dot_matrix, print_opd_card_a4_fast
# Import database functions
from database import (
    get_all_users, add_user, delete_user, authenticate_user,
    create_tables, get_next_registration_number,
    add_opd_patient, add_epd_patient, add_ipd_patient,
    update_patient, update_epd_patient, update_ipd_patient,
    get_all_patients, search_patients,
    get_patient_by_reg_number,
    add_medicine, add_medicine_purchase, add_medicine_supply,
    get_current_stock, get_batchwise_stock,
    get_db_connection, update_user_sections, get_user_by_username
)

from printer_manager import save_printer_choice, load_printer_choice
from printer_selector import PrinterSelector
from tkinter import messagebox

def get_cash_in_hand(username, date=None):
    import datetime
    if username == "admin":
        return None
    if not date or (isinstance(date, str) and not date.strip()):
        date = datetime.date.today().strftime("%Y-%m-%d")
    elif isinstance(date, datetime.date):
        date = date.strftime("%Y-%m-%d")
    
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT cash_in_hand FROM user_cash_log WHERE username = %s AND date = %s",
            (username, date)
        )
        row = cursor.fetchone()
      
        return row[0] if row else None
    finally:
        cursor.close()
        conn.close()

        
logger = logging.getLogger(__name__)



class PatientRegistrationApp:
    def __init__(self, master):
        self.master = master
        self.current_reg_number = None
        self.current_page = 1
        self.page_size = 100
        self.is_loading = False
        self.current_role = None
        self.current_username = None
        self.cash_in_hand = 0.0
        self.date_entries = []
        self.style = ttk.Style()
        self.last_saved_ipd_registration_number = None
        self.style.theme_use('clam')
        self.style.configure('TFrame', background='#e0f2f7')
        self.style.configure('TLabel', background='#e0f2f7', font=('Inter', 10))
        self.style.configure('TButton', font=('Inter', 10, 'bold'), padding=10)
        self.style.map('TButton',
            background=[('active', '#81D4FA'), ('!disabled', '#2196F1')],
            foreground=[('active', 'white'), ('!disabled', 'white')]
        )
        self.style.configure('Treeview.Heading', font=('Inter', 10, 'bold'))
        self.style.configure('Treeview', rowheight=25, font=('Arial', 10))
        self.show_role_selection()
        self.opd_to_ipd_transfer_in_progress = False
        self.editing_epd_reg_number = None

    # Add all method stubs and paste your logic from your original code here
    def show_role_selection(self):
        """Display Admin/User choice before login, in a compact non-fullscreen window."""
        for widget in self.master.winfo_children():
            widget.destroy()

        self.role_frame = ttk.Frame(self.master, style='TFrame')
        self.role_frame.pack(expand=True, fill='both', padx=20, pady=20)
        self.master.title("Select Role")
        self.master.geometry("500x500")
        self.master.minsize(320, 220)
        self.master.resizable(False, False)

        ttk.Label(
            self.role_frame,
            text="Login as",
            font=('Arial', 16, 'bold'),
            background='#e0f2f7',
            foreground='#0D47A1'
        ).pack(pady=(16, 18))

        btn_frame = ttk.Frame(self.role_frame, style='TFrame')
        btn_frame.pack(pady=3)

        # Try loading icons
        try:
            admin_img = Image.open("admin_icon.png").resize((44, 44))
            admin_icon = ImageTk.PhotoImage(admin_img)
        except Exception:
            admin_icon = None
        try:
            user_img = Image.open("user_icon.png").resize((44, 44))
            user_icon = ImageTk.PhotoImage(user_img)
        except Exception:
            user_icon = None

        def select_admin():
            self.current_role = 'admin'
            self.role_frame.destroy()
            self.show_login()

        def select_user():
            self.current_role = 'user'
            self.role_frame.destroy()
            self.show_login()

        btn_font = ('Arial', 12, 'bold')
        btn_bg = "#e3f0fa"
        btn_fg = "#0D47A1"
        active_bg = "#bbdefb"

        admin_btn = tk.Button(
            btn_frame,
            text="Admin",
            image=admin_icon, compound='top' if admin_icon else None,
            font=btn_font,
            width=90, height=70,
            command=select_admin,
            bg=btn_bg, fg=btn_fg,
            activebackground=active_bg, activeforeground=btn_fg,
            borderwidth=2, relief="raised", cursor="hand2"
        )
        admin_btn.image = admin_icon

        user_btn = tk.Button(
            btn_frame,
            text="User",
            image=user_icon, compound='top' if user_icon else None,
            font=btn_font,
            width=90, height=70,
            command=select_user,
            bg=btn_bg, fg=btn_fg,
            activebackground=active_bg, activeforeground=btn_fg,
            borderwidth=2, relief="raised", cursor="hand2"
        )
        user_btn.image = user_icon

        admin_btn.grid(row=0, column=0, padx=22, pady=5)
        user_btn.grid(row=0, column=1, padx=22, pady=5)

        ttk.Label(
            self.role_frame,
            text="Select your login type",
            font=('Arial', 10),
            background='#e0f2f7',
            foreground='#1976D2'
        ).pack(pady=(12, 0))

    def show_login(self):
      for widget in self.master.winfo_children():
        widget.destroy()

      self.login_frame = ttk.Frame(self.master, style='TFrame')
      self.login_frame.pack(expand=True, fill='both', padx=20, pady=20)
      self.master.title(f"Patient Management System - Login ({self.current_role.capitalize()})")
      self.master.geometry("500x500")
      self.master.minsize(460, 420)
      self.master.resizable(False, False)

      # --- Top-left Back Button with Icon (place on self.master, not container) ---
      try:
        self._back_icon = ImageTk.PhotoImage(Image.open("back_icon.png").resize((28, 28)))
      except Exception:
        self._back_icon = None

      def go_back():
        self.login_frame.destroy()
        if hasattr(self, 'back_btn') and self.back_btn:
            self.back_btn.destroy()
            self.back_btn = None
        self.show_role_selection()

      # Create back button and store reference
      if self._back_icon:
        self.back_btn = tk.Button(self.master, image=self._back_icon, command=go_back, bg='#e0f2f7',
                                  bd=0, highlightthickness=0, activebackground='#e0f2f7', cursor="hand2")
        self.back_btn.place(x=8, y=8)
      else:
        self.back_btn = tk.Button(self.master, text="Back", command=go_back, bg='#e0f2f7',
                                  bd=0, highlightthickness=0, activebackground='#e0f2f7', cursor="hand2")
        self.back_btn.place(x=8, y=8)

      # --- Layout: Centered vertical stack ---
      container = ttk.Frame(self.login_frame, style='TFrame')
      container.pack(expand=True, fill='both')

      # --- Load relevant logo ---
      logo_icon = None
      try:
        if self.current_role == "admin":
            logo_img = Image.open("admin_icon.png").resize((84, 84))
        else:
            logo_img = Image.open("user_icon.png").resize((84, 84))
        logo_icon = ImageTk.PhotoImage(logo_img)
      except Exception:
        logo_icon = None

      # Logo (centered)
      if logo_icon:
        logo_label = tk.Label(container, image=logo_icon, bg='#e0f2f7')
        logo_label.image = logo_icon
        logo_label.pack(pady=(28, 10))
      else:
        tk.Label(container, text="", background='#e0f2f7').pack(pady=(28, 10))

      # Show current selection
      ttk.Label(
        container,
        text=f"Selected Role: {self.current_role.capitalize()}",
        font=('Arial', 14, 'bold'),
        background='#e0f2f7',
        foreground='#1976D2'
      ).pack(pady=(0, 8))

      # Section title
      ttk.Label(
        container,
        text=f"{self.current_role.capitalize()} Login",
        font=('Arial', 17, 'bold'),
        background='#e0f2f7',
        foreground='#0D47A1'
      ).pack(pady=(0, 18))

      # Username
      ttk.Label(container, text="Username:", background='#e0f2f7').pack(pady=4)
      self.username_entry = ttk.Entry(container, font=('Arial', 12))
      self.username_entry.pack(pady=3, padx=50, fill='x')

      # Password
      ttk.Label(container, text="Password:", background='#e0f2f7').pack(pady=4)
      self.password_entry = ttk.Entry(container, show='*', font=('Arial', 12))
      self.password_entry.pack(pady=3, padx=50, fill='x')

      # Cash in Hand (only for users)
      if self.current_role == "user":
        ttk.Label(container, text="Cash in Hand:", background='#e0f2f7', font=('Arial', 10)).pack(pady=3)
        self.cash_in_hand_entry = ttk.Entry(container, font=('Arial', 10), width=24)
        self.cash_in_hand_entry.pack(pady=3, padx=110)
      else:
        self.cash_in_hand_entry = None  # For admin, not used

      # --- Define login function and assign before binding events ---
      def login():
       username = self.username_entry.get().strip()
       password = self.password_entry.get()

       if self.current_role == "user":
         cash_in_hand = self.cash_in_hand_entry.get().strip() if self.cash_in_hand_entry else ""
         if not username or not password or not cash_in_hand:
            messagebox.showerror("Login Error", "Please enter username, password, and cash in hand.")
            return
         try:
            cash_value = float(cash_in_hand)
            if cash_value < 0:
                raise ValueError
         except ValueError:
            messagebox.showerror("Login Error", "Cash in hand must be a non-negative number.")
            return
         self.cash_in_hand = cash_value
       else:  # admin
          if not username or not password:
            messagebox.showerror("Login Error", "Please enter username and password.")
            return

         # --- Single Session Login Logic ---
       result = authenticate_user(username, password)
       if result == "already_logged_in":
          messagebox.showerror("Login Error", "This user is already logged in on another device.")
          return
       elif result is True:
         if self.current_role == "user":
            from database import save_cash_in_hand
            save_cash_in_hand(username, self.cash_in_hand)
         conn = get_db_connection()
         if conn:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT role FROM users WHERE username=%s", (username,))
            user = cur.fetchone()
            actual_role = user.get('role', 'user') if user else 'user'
            cur.close()
            conn.close()
            if actual_role != self.current_role:
                messagebox.showerror("Login Error", f"User '{username}' does not have {self.current_role} privileges.")
                return
         self.login_frame.destroy()
         self.current_username = username

         # REMOVE back_icon after login
         if hasattr(self, 'back_btn') and self.back_btn:
            self.back_btn.destroy()
            self.back_btn = None

         self.launch_main_ui()
       else:
         messagebox.showerror("Login Error", "Invalid username or password.")

      self.login = login  # <-- assign before any binding

      # --- Enter key navigation ---
      self.username_entry.bind('<Return>', lambda event: self.password_entry.focus_set())
      if self.current_role == "user" and self.cash_in_hand_entry is not None:
         self.password_entry.bind('<Return>', lambda event: self.cash_in_hand_entry.focus_set())
         self.cash_in_hand_entry.bind('<Return>', lambda event: self.login())
      else:
         self.password_entry.bind('<Return>', lambda event: self.login())

      ttk.Button(container, text="Login", command=self.login, width=16).pack(pady=(10, 6))

    def launch_main_ui(self):
      # Hide or destroy the back button on successful login
      if hasattr(self, 'back_btn') and self.back_btn:
        self.back_btn.destroy()
        self.back_btn = None

      self.master.title("Patient Management System")
      self.master.minsize(800, 600)
      self.master.resizable(True, True)
      try:
        self.master.state('zoomed')
      except Exception:
        pass
      
      # -- Fetch allowed sections for the user --
      from database import get_user_by_username
      user = get_user_by_username(self.current_username)
      if user and user.get('sections_allowed'):
        allowed_sections = user.get('sections_allowed').split(',')
      else:
        allowed_sections = ['Reception', 'OPD', 'IPD', 'Medicine', 'Reporting']

      self.notebook = ttk.Notebook(self.master)
      self.notebook.pack(expand=True, fill='both', padx=10, pady=10)


      

      # -- ADMIN TAB AND USER MANAGEMENT BUTTON --
      if self.current_role == "admin":
        self.special_admin_tab = ttk.Frame(self.notebook, style='TFrame', padding="20")
        self.notebook.add(self.special_admin_tab, text="  Admin Only  ")
        ttk.Label(self.special_admin_tab, text="Admin Special Feature", font=('Arial', 14, 'bold')).pack(pady=20)
        ttk.Button(self.special_admin_tab, text="User Management", command=self.open_user_management).pack(pady=10)

        # --- Printer Settings button for Admin Only tab ---
        printer_btn_frame = ttk.Frame(self.special_admin_tab, style='TFrame')
        printer_btn_frame.pack(pady=(10, 0))
        ttk.Button(self.special_admin_tab, text="Printer Settings", command=self.show_printer_settings).pack(pady=10)

        # --- Force Unlock User button ---
        def force_unlock_user():
         from tkinter import simpledialog, messagebox
         username = simpledialog.askstring("Force Unlock User", "Enter username to unlock:")
         if not username:
            return
         from database import logout_user
         success = logout_user(username)
         if success:
            messagebox.showinfo("Force Unlock", f"User '{username}' has been unlocked (logged out).")
         else:
            messagebox.showerror("Force Unlock", f"Failed to unlock user '{username}'. Check if username exists.")

        ttk.Button(self.special_admin_tab, text="Force Unlock User", command=force_unlock_user).pack(pady=10)

      # --- Mandatory Account tab ---
      self.account_tab = ttk.Frame(self.notebook, style='TFrame', padding="20")
      self.notebook.add(self.account_tab, text='  Account  ')
      ttk.Label(self.account_tab, text="Account & Settings", font=('Arial', 14, 'bold')).pack(pady=(20,10))
      ttk.Label(self.account_tab, text=f"Logged in as: {self.current_username}", font=('Arial', 12)).pack(pady=(0,10))
      ttk.Button(self.account_tab, text="Logout", command=self.logout).pack(pady=16)

      # -- REGULAR TABS (Add ONLY if allowed) --
      if 'OPD' in allowed_sections:
        self.registration_frame = ttk.Frame(self.notebook, style='TFrame', padding="20")
        self.notebook.add(self.registration_frame, text='  OPD Patient Registration  ')
        self.registration_frame.columnconfigure(1, weight=1)
        self.create_registration_widgets()
      if 'View/Search' in allowed_sections or 'OPD' in allowed_sections or 'IPD' in allowed_sections or 'EPD' in allowed_sections:
        self.view_search_frame = ttk.Frame(self.notebook, style='TFrame', padding="20")
        self.notebook.add(self.view_search_frame, text='  View/Search Patients  ')
        self.create_view_search_widgets()
      if 'Reception' in allowed_sections:
        self.reception_frame = ttk.Frame(self.notebook, style='TFrame', padding="20")
        self.notebook.add(self.reception_frame, text='  Reception ')
        self.create_reception_widgets()
      if 'IPD' in allowed_sections:
        self.ipd_frame = ttk.Frame(self.notebook, style='TFrame', padding="20")
        self.notebook.add(self.ipd_frame, text='  IPD Management ')
        self.create_ipd_widgets()
      if 'Medicine' in allowed_sections:
        self.medicine_tab = ttk.Frame(self.notebook, style='TFrame', padding="20")
        self.notebook.add(self.medicine_tab, text='  Medicine  ')
        self.add_medicine_options(self.medicine_tab)
      if 'Reporting' in allowed_sections:
        self.reporting_tab = ttk.Frame(self.notebook, style='TFrame', padding="20")
        self.notebook.add(self.reporting_tab, text='  Reporting  ')
        self.reporting_frame = ReportingFrame(self.reporting_tab, self.current_username, self.current_role)
        self.reporting_frame.pack(fill="both", expand=True)

      self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_change)
      self.master.bind("<Configure>", lambda event: self.on_resize(event))

    def open_user_management(self):
      UserManagementWindow(self.master)

    def close_app(self):
      try:
        pool = getattr(self, "connection_pool", None)
        if pool and hasattr(pool, "_cnx_queue"):
            for conn in list(pool._cnx_queue.queue):
                try:
                    conn.close()
                except Exception:
                    pass
            logger.info("Database pool connections closed.")
      except Exception as e:
        logger.error(f"Error cleaning up pool: {e}")
      finally:
        # LOGOUT current user before application closes
        if self.current_username:
            from database import logout_user
            logout_user(self.current_username)
        self.master.destroy()

    def logout(self):
      if self.current_username:
        from database import logout_user
        logout_user(self.current_username)
        self.current_username = None
      # Optionally, destroy main UI and show login screen again
      self.show_login()

    def on_tab_change(self, event):
      # Destroy all calendar popups for each DateEntry known
      for entry in getattr(self, "date_entries", []):
        try:
            entry.hide_calendar()  # This safely hides the popup without breaking future interactions.
        except Exception:
            pass
      selected_tab = self.notebook.tab(self.notebook.select(), "text")
      if "View/Search Patients" in selected_tab:
        self.current_page = 1
        self.load_all_patients()
    
    def on_resize(self, event):
      # Only adjust layout if these frames exist
      if hasattr(self, 'registration_frame') and self.registration_frame.winfo_exists():
        self.registration_frame.columnconfigure(1, weight=1)
      if hasattr(self, 'view_search_frame') and self.view_search_frame.winfo_exists():
        self.view_search_frame.columnconfigure(0, weight=1)
      if hasattr(self, 'reception_frame') and self.reception_frame.winfo_exists():
        self.reception_frame.columnconfigure(0, weight=1)
      if hasattr(self, 'ipd_frame') and self.ipd_frame.winfo_exists():
        self.ipd_frame.columnconfigure(0, weight=1)

    def create_registration_widgets(self):
      row_idx = 0
      ttk.Label(self.registration_frame, text="OPD Patient Registration",
              font=('Arial', 14, 'bold'), background='#e0f2f7', foreground='#0D47A1').grid(
        row=row_idx, column=0, columnspan=2, pady=(0,20), sticky="ew")
      row_idx += 1
      self.fields = {}
      self.field_widgets = {}
      mandatory_fields = [
        'first_name', 'father_name', 'age', 'gender', 'town', 'state', 'address',
        'mobile_number', 'medical_department'
      ]
      field_definitions = [
        ("Registration No.:", "registration_number", False, ttk.Entry),
        ("First Name:", "first_name", True, ttk.Entry),
        ("Last Name:", "last_name", False, ttk.Entry),
        ("Father's Name:", "father_name", True, ttk.Entry),
        ("ABHA Number:", "abha_number", False, ttk.Entry),
        ("Age:", "age", True, ttk.Entry),
        ("Gender:", "gender", True, ttk.Combobox, ['Male', 'Female', 'Other']),
        ("Mobile Number:", "mobile_number", True, ttk.Entry),
        ("Email:", "email", False, ttk.Entry),
        ("Address:", "address", True, ttk.Entry),
        ("Post Office:", "post_office", False, ttk.Entry),
        ("Town:", "town", True, ttk.Entry),
        ("State:", "state", True, ttk.Entry),
        ("Registration Fee (Rs):", "registration_fee", False, ttk.Entry),
        ("Payment Status:", "payment_status", False, ttk.Combobox, ['Paid', 'Free']),
        ("Registration Date (DD/MM/YYYY):", "registration_date", False, ttk.Entry),
        ("Medical Department:", "medical_department", True, ttk.Combobox,['General Medicine', 'Pediatrics', 'Orthopedics', 'Gynecology','Cardiology', 'Neurology', 'Surgery', 'ENT', 'Dermatology', 'Psychiatry']),
      ]
      for label_text, key, required, widget_type, *widget_info in field_definitions:
        ttk.Label(self.registration_frame, text=label_text).grid(
            row=row_idx, column=0, sticky="w", pady=5, padx=10)
        if widget_type == tk.Text:
            text_widget = tk.Text(self.registration_frame, height=4, width=50, font=('Arial', 10), wrap='word')
            text_widget.grid(row=row_idx, column=1, sticky="ew", pady=5, padx=10)
            self.fields[key] = text_widget
            self.field_widgets[key] = text_widget
            text_widget.bind('<Return>', self.move_to_next_field)
        elif widget_type == ttk.Combobox:
            combobox_var = tk.StringVar()
            combobox = ttk.Combobox(self.registration_frame, textvariable=combobox_var,
                                    values=widget_info[0], font=('Arial', 10), state='readonly')
            combobox.grid(row=row_idx, column=1, sticky="ew", pady=5, padx=10)
            self.fields[key] = combobox_var
            self.field_widgets[key] = combobox
            combobox.bind('<Return>', self.move_to_next_field)
        else:
            entry = ttk.Entry(self.registration_frame, width=50, font=('Arial', 10))
            if key == 'registration_number':
                entry.config(state='readonly')
                entry.delete(0, tk.END)  # always blank
            entry.grid(row=row_idx, column=1, sticky="ew", pady=5, padx=10)
            self.fields[key] = entry
            self.field_widgets[key] = entry
            entry.bind('<Return>', self.move_to_next_field)

            if key == 'registration_date':
                self.fields[key].bind('<FocusOut>', self.validate_registration_date)
                self.fields[key].bind('<KeyRelease>', self.format_reg_date)

        if required or key in mandatory_fields:
            ttk.Label(self.registration_frame, text="*", foreground="red", background='#e0f2f7').grid(
                row=row_idx, column=0, sticky="e", padx=(0,5))
        row_idx += 1
      self.fields['registration_date'].bind('<KeyRelease>', self.format_reg_date)
      button_frame = ttk.Frame(self.registration_frame, style='TFrame')
      button_frame.grid(row=row_idx, column=0, columnspan=2, pady=20, sticky="ew")
      button_frame.columnconfigure(0, weight=1)
      self.save_update_button = ttk.Button(
        button_frame, text="Save New Patient", command=self.save_or_update_patient)
      self.save_update_button.pack(side=tk.LEFT, padx=10)
      ttk.Button(button_frame, text="Clear Form", command=self.clear_form).pack(side=tk.LEFT, padx=10)
      ttk.Button(button_frame, text="Print Patient Card", command=self.show_print_preview).pack(side=tk.LEFT, padx=10)
      self.back_to_register_button = ttk.Button(
        button_frame, text="Back to New Patient", command=self.reset_to_new_patient)
      self.back_to_register_button.pack(side=tk.LEFT, padx=10)
      
      # Always hide initially
      self.back_to_register_button.pack_forget()
      
      
      
      self.clear_form()

    def move_to_next_field(self, event):
        current_widget = event.widget
        for key, widget in self.fields.items():
            if widget == current_widget or (isinstance(widget, tk.StringVar) and self.field_widgets[key] == current_widget):
                current_key = key
                break
        else:
            return
        field_order = [
            'registration_number', 'first_name', 'last_name', 'father_name', 'abha_number',
            'age', 'gender', 'mobile_number', 'email', 'address',
            'post_office', 'town', 'state', 'registration_fee', 'payment_status',
            'registration_date', 'medical_department'
        ]
        if current_key in field_order:
            current_index = field_order.index(current_key)
            next_index = current_index + 1 if current_index < len(field_order) - 1 else current_index
            if next_index < len(field_order):
                next_key = field_order[next_index]
                next_widget = self.field_widgets.get(next_key)
                if next_key == 'registration_number':
                    next_index += 1
                    if next_index < len(field_order):
                        next_key = field_order[next_index]
                        next_widget = self.field_widgets.get(next_key)
                    else:
                        return
                if next_widget:
                    next_widget.focus_set()

    
    def validate_registration_date(self, event=None):
      entry = self.fields['registration_date']
      value = entry.get().strip()
      # If empty, allow it
      if not value:
        return
      # Check for proper format
      if not re.match(r"^\d{2}/\d{2}/\d{4}$", value):
        if len(value) == 10:  # Only show error if full date is entered
            messagebox.showerror("Input Error", 
                "Please enter date in DD/MM/YYYY format with forward slashes (e.g., 31/12/2025)")
            entry.delete(0, tk.END)
            return
      # Validate the date if complete
      if len(value) == 10:
        try:
            datetime.datetime.strptime(value, "%d/%m/%Y")
        except ValueError:
            messagebox.showerror("Input Error", "Invalid date. Please enter a valid date.")
            entry.delete(0, tk.END)

    def format_reg_date(self, event):
     
      entry = self.fields['registration_date']
      value = entry.get().replace('/', '')  # Remove any existing slashes
      if len(value) > 8:
        value = value[:8]
      if len(value) > 4:
        entry.delete(0, tk.END)
        entry.insert(0, f"{value[:2]}/{value[2:4]}/{value[4:]}")  # Force dd/mm/yyyy format
      elif len(value) > 2:
        entry.delete(0, tk.END)
        entry.insert(0, f"{value[:2]}/{value[2:]}")
      else:
        entry.delete(0, tk.END)
        entry.insert(0, value)

    def create_view_search_widgets(self):
      from tkcalendar import DateEntry

      # --- Outer Frame for Padding ---
      outer_frame = ttk.Frame(self.view_search_frame, style='TFrame')
      outer_frame.grid(row=0, column=0, sticky="nsew", padx=24, pady=15)
      self.view_search_frame.rowconfigure(0, weight=0)
      self.view_search_frame.columnconfigure(0, weight=1)

      # --- Filter Frame ---
      filter_frame = ttk.LabelFrame(outer_frame, text="Patient Search Filters", padding=(18,14))
      filter_frame.grid(row=0, column=0, sticky="ew")
      for i in range(6):
        filter_frame.columnconfigure(i, weight=1)

      # Row 0: Registration Number, Name, Phone
      ttk.Label(filter_frame, text="Registration Number:", font=('Arial', 10)).grid(row=0, column=0, sticky="e", padx=(2,2), pady=3)
      self.reg_no_search_var = tk.StringVar()
      self.reg_no_search_entry = ttk.Entry(filter_frame, textvariable=self.reg_no_search_var, width=15)
      self.reg_no_search_entry.grid(row=0, column=1, sticky="w", padx=(0,12), pady=3)

      ttk.Label(filter_frame, text="Name:", font=('Arial', 10)).grid(row=0, column=2, sticky="e", padx=(2,2), pady=3)
      self.name_search_var = tk.StringVar()
      self.name_search_entry = ttk.Entry(filter_frame, textvariable=self.name_search_var, width=15)
      self.name_search_entry.grid(row=0, column=3, sticky="w", padx=(0,12), pady=3)
      self.name_search_entry.bind("<Return>", lambda event: self.perform_search())

      ttk.Label(filter_frame, text="Phone:", font=('Arial', 10)).grid(row=0, column=4, sticky="e", padx=(2,2), pady=3)
      self.phone_search_var = tk.StringVar()
      self.phone_search_entry = ttk.Entry(filter_frame, textvariable=self.phone_search_var, width=15)
      self.phone_search_entry.grid(row=0, column=5, sticky="w", padx=(0,6), pady=3)

      ttk.Label(filter_frame, text="Father's Name:", font=('Arial', 10)).grid(row=0, column=4, sticky="e", padx=(2,2), pady=3)
      self.father_name_search_var = tk.StringVar()
      self.father_name_search_entry = ttk.Entry(filter_frame, textvariable=self.father_name_search_var, width=15)
      self.father_name_search_entry.grid(row=0, column=5, sticky="w", padx=(0,6), pady=3)

      # Row 1: Department, Town, State
      ttk.Label(filter_frame, text="Department:", font=('Arial', 10)).grid(row=1, column=0, sticky="e", padx=(2,2), pady=3)
      self.dept_search_var = tk.StringVar()
      self.dept_search_entry = ttk.Combobox(
        filter_frame, textvariable=self.dept_search_var,
        values=['', 'General Medicine', 'Pediatrics', 'Orthopedics', 'Gynecology',
                'Cardiology', 'Neurology', 'Surgery', 'ENT', 'Dermatology', 'Psychiatry'],
        width=15, state="readonly")
      self.dept_search_entry.grid(row=1, column=1, sticky="w", padx=(0,12), pady=3)

      ttk.Label(filter_frame, text="Town:", font=('Arial', 10)).grid(row=1, column=2, sticky="e", padx=(2,2), pady=3)
      self.town_search_var = tk.StringVar()
      self.town_search_entry = ttk.Entry(filter_frame, textvariable=self.town_search_var, width=15)
      self.town_search_entry.grid(row=1, column=3, sticky="w", padx=(0,12), pady=3)

      ttk.Label(filter_frame, text="State:", font=('Arial', 10)).grid(row=1, column=4, sticky="e", padx=(2,2), pady=3)
      self.state_search_var = tk.StringVar()
      self.state_search_entry = ttk.Entry(filter_frame, textvariable=self.state_search_var, width=15)
      self.state_search_entry.grid(row=1, column=5, sticky="w", padx=(0,6), pady=3)

      # Row 2: Gender, Age, From Date, To Date
      ttk.Label(filter_frame, text="Gender:", font=('Arial', 10)).grid(row=2, column=0, sticky="e", padx=(2,2), pady=3)
      self.gender_search_var = tk.StringVar()
      self.gender_search_entry = ttk.Combobox(
        filter_frame, textvariable=self.gender_search_var,
        values=['', 'Male', 'Female', 'Other'], width=15, state="readonly")
      self.gender_search_entry.grid(row=2, column=1, sticky="w", padx=(0,12), pady=3)

      ttk.Label(filter_frame, text="Age:", font=('Arial', 10)).grid(row=2, column=2, sticky="e", padx=(2,2), pady=3)
      self.age_search_var = tk.StringVar()
      self.age_search_entry = ttk.Entry(filter_frame, textvariable=self.age_search_var, width=15)
      self.age_search_entry.grid(row=2, column=3, sticky="w", padx=(0,12), pady=3)

      ttk.Label(filter_frame, text="From Date:", font=('Arial', 10)).grid(row=2, column=4, sticky="e", padx=(2,2), pady=3)
      self.from_date_var = tk.StringVar()
      self.from_date_entry = DateEntry(
        filter_frame, textvariable=self.from_date_var, width=15, date_pattern='dd/MM/yyyy',
        showweeknumbers=False, background='#e0f2f7', foreground='#0D47A1', borderwidth=2
     )
      self.from_date_entry.grid(row=2, column=5, sticky="w", padx=(0,6), pady=3)
      self.date_entries.append(self.from_date_entry)

      ttk.Label(filter_frame, text="To Date:", font=('Arial', 10)).grid(row=3, column=0, sticky="e", padx=(2,2), pady=3)
      self.to_date_var = tk.StringVar()
      self.to_date_entry = DateEntry(
        filter_frame, textvariable=self.to_date_var, width=15, date_pattern='dd/MM/yyyy',
        showweeknumbers=False, background='#e0f2f7', foreground='#0D47A1', borderwidth=2
      )
      self.to_date_entry.grid(row=3, column=1, sticky="w", padx=(0,12), pady=3)
      self.date_entries.append(self.to_date_entry)

      # Row 3: Patient Type
      ttk.Label(filter_frame, text="Patient Type:", font=('Arial', 10)).grid(row=3, column=2, sticky="e", padx=(2,2), pady=3)
      self.patient_type_var = tk.StringVar()
      self.patient_type_combo = ttk.Combobox(
        filter_frame, textvariable=self.patient_type_var,
        values=['All', 'OPD', 'EPD', 'IPD'], width=15, state="readonly")
      self.patient_type_combo.grid(row=3, column=3, sticky="w", padx=(0,12), pady=3)
      self.patient_type_combo.set("All")

      # --- Button Row ---
      btn_frame = ttk.Frame(outer_frame, style='TFrame')
      btn_frame.grid(row=1, column=0, sticky="ew", pady=(8,0))
      for i in range(3): btn_frame.columnconfigure(i, weight=1)
      ttk.Button(btn_frame, text="🔍 Search", command=self.perform_search, width=14).grid(row=0, column=0, padx=4)
      ttk.Button(btn_frame, text="Show All", command=lambda: self.load_all_patients(page=1), width=12).grid(row=0, column=1, padx=4)
      ttk.Button(btn_frame, text="Clear Filters", command=self.clear_search_filters, width=12).grid(row=0, column=2, padx=4)

      # --- Progress Bar ---
      self.progress_bar = ttk.Progressbar(self.view_search_frame, mode='indeterminate')
      self.progress_bar.grid(row=2, column=0, sticky="ew", pady=7)

      # --- Results Table ---
      columns = ("registration_number", "first_name", "last_name", "mobile_number", "gender", "age", "patient_type")
      self.patient_tree = ttk.Treeview(self.view_search_frame, columns=columns, show="headings", selectmode="browse")
      for col in columns:
        self.patient_tree.heading(col, text=col.replace('_', ' ').title(), anchor=tk.W)
        self.patient_tree.column(col, width=120, anchor=tk.W)
      self.patient_tree.grid(row=3, column=0, sticky="nsew", pady=10)
      self.view_search_frame.rowconfigure(3, weight=1)
      scrollbar = ttk.Scrollbar(self.view_search_frame, orient="vertical", command=self.patient_tree.yview)
      scrollbar.grid(row=3, column=1, sticky="ns")
      self.patient_tree.configure(yscrollcommand=scrollbar.set)

      # --- Pagination ---
      pagination_frame = ttk.Frame(self.view_search_frame, style='TFrame')
      pagination_frame.grid(row=4, column=0, sticky="ew", pady=7)
      self.prev_button = ttk.Button(pagination_frame, text="Previous", command=self.prev_page, state='disabled')
      self.prev_button.grid(row=0, column=0, padx=5)
      self.page_label = ttk.Label(pagination_frame, text="Page 1", background='#e0f2f7')
      self.page_label.grid(row=0, column=1, padx=7)
      self.next_button = ttk.Button(pagination_frame, text="Next", command=self.next_page)
      self.next_button.grid(row=0, column=2, padx=5)
  
      # --- Action Button Row (Edit for Admin) ---
      action_button_frame = ttk.Frame(self.view_search_frame, style='TFrame')
      action_button_frame.grid(row=5, column=0, sticky="ew", pady=10)
      if self.current_role == "admin":
        ttk.Button(action_button_frame, text="Edit Selected Patient", command=self.edit_selected_patient).pack(side=tk.LEFT, padx=10)

    def clear_search_filters(self):
      self.reg_no_search_var.set("")
      self.name_search_var.set("")
      self.father_name_search_var.set("")
      self.phone_search_var.set("")
      self.dept_search_var.set("")
      self.town_search_var.set("")
      self.state_search_var.set("")
      self.gender_search_var.set("")
      self.age_search_var.set("")
      self.from_date_var.set("")
      self.to_date_var.set("")
      self.patient_type_var.set("All")

    def create_reception_widgets(self):
        for widget in self.reception_frame.winfo_children():
          widget.destroy()
        ttk.Label(self.reception_frame, text="Reception Dashboard",
                  font=('Arial', 16, 'bold'), background='#e0f2f7', foreground='#0D47A1').grid(
            row=0, column=0, columnspan=2, pady=(0,20), sticky="ew")
        emergency_frame = ttk.LabelFrame(self.reception_frame, text="1. Emergency", padding="10")
        emergency_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        ttk.Button(emergency_frame, text="Register Emergency Patient",
                  command=self.show_emergency_case_form).pack(pady=5)
        opd_reg_frame = ttk.LabelFrame(self.reception_frame, text="2. OPD Patient Registration", padding="10")
        opd_reg_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        ttk.Button(opd_reg_frame, text="Register OPD Patient",
                   command=lambda: self.notebook.select(self.registration_frame)).pack(pady=5)
        opd_card_frame = ttk.LabelFrame(self.reception_frame, text="3. OPD Patient Card", padding="10")
        opd_card_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=5)
        ttk.Button(opd_card_frame, text="Generate OPD Patient Card",
            command=self.prompt_and_generate_opd_card).pack(pady=5)
        edp_card_frame = ttk.LabelFrame(self.reception_frame, text="4. EDP Patient Card", padding="10")
        edp_card_frame.grid(row=4, column=0, sticky="nsew", padx=10, pady=5)
        ttk.Button(edp_card_frame, text="Generate EPD Patient Card",
                   command=self.prompt_and_generate_epd_card).pack(pady=5)
        enquiry_frame = ttk.LabelFrame(self.reception_frame, text="5. Patient Enquiry", padding="10")
        enquiry_frame.grid(row=5, column=0, sticky="nsew", padx=10, pady=5)
        ttk.Button(enquiry_frame, text="Search Patient Records",
                   command=lambda: self.notebook.select(self.view_search_frame)).pack(pady=5)
        self.reception_frame.columnconfigure(0, weight=1)
        self.reception_frame.rowconfigure(5, weight=1)

    def create_ipd_widgets(self):
      # This is your IPD management dashboard.
      for widget in self.ipd_frame.winfo_children():
        widget.destroy()
      ttk.Label(self.ipd_frame, text="IPD Management Dashboard",
              font=('Arial', 16, 'bold'), background='#e0f2f7', foreground='#0D47A1').grid(
        row=0, column=0, columnspan=2, pady=(0, 20), sticky="ew")
      ipd_new_frame = ttk.LabelFrame(self.ipd_frame, text="1. IPD New Patient", padding="10")
      ipd_new_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
      ttk.Button(ipd_new_frame, text="Register New IPD Patient",
               command=self.show_ipd_patient_form).pack(pady=5)
      epd_to_ipd_frame = ttk.LabelFrame(self.ipd_frame, text="2. EPD to IPD", padding="10")
      epd_to_ipd_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
      ttk.Button(epd_to_ipd_frame, text="Transfer EPD Patient to IPD",
               command=self.transfer_epd_to_ipd).pack(pady=5)
      opd_to_ipd_frame = ttk.LabelFrame(self.ipd_frame, text="3. OPD to IPD", padding="10")
      opd_to_ipd_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=5)
      ttk.Button(opd_to_ipd_frame, text="Transfer OPD Patient to IPD",
               command=self.transfer_opd_to_ipd).pack(pady=5)
      self.ipd_frame.columnconfigure(0, weight=1)
      self.ipd_frame.rowconfigure(4, weight=1)

    def show_printer_settings(self):
      from printer_manager import list_printers, load_printer_choice
      printers = list_printers()
      PrinterSelector(self.master, self.set_printer, initial_printer=load_printer_choice(), printers=printers)

    def set_printer(self, printer):
      save_printer_choice(printer)
      messagebox.showinfo("Printer selection", f"Printer saved: {printer}")

    def save_or_update_patient(self):
      import datetime
      # Collect and validate mandatory fields
      mandatory_fields = {
        'first_name': 'First Name',
        'father_name': "Father's Name",
        'age': 'Age',
        'gender': 'Gender',
        'mobile_number': 'Mobile Number',
        'address': 'Address',
        'town': 'Town',
        'state': 'State',
        'medical_department': 'Medical Department'
      }

      missing_fields = []
      data = {}
      for key, label in mandatory_fields.items():
        widget = self.fields[key]
        value = widget.get().strip() if not isinstance(widget, tk.Text) else widget.get("1.0", tk.END).strip()
        if not value:
            missing_fields.append(label)
        data[key] = value

      if missing_fields:
        messagebox.showerror("Input Error", f"Please fill in the following required fields: {', '.join(missing_fields)}")
        return

      # Collect optional fields
      data.update({
        'last_name': self.fields['last_name'].get().strip() or None,
        'abha_number': self.fields['abha_number'].get().strip() or None,
        'email': self.fields['email'].get().strip() or None,
        'post_office': self.fields['post_office'].get().strip() or None,
        'registration_fee': self.fields['registration_fee'].get().strip() or '5.0',
        'payment_status': self.fields['payment_status'].get().strip() or 'Paid',
        'registration_date': self.fields['registration_date'].get().strip()
      })

      # Validate mobile number
      if not data['mobile_number'].isdigit() or len(data['mobile_number']) != 10:
        messagebox.showerror("Input Error", "Mobile number must be exactly 10 digits")
        return

      # Validate email if provided
      if data['email']:
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", data['email']):
            messagebox.showerror("Input Error", "Invalid email format")
            return

      # Validate age
      try:
        age = int(data['age'])
        if not (0 <= age <= 150):
            raise ValueError
        data['age'] = age
      except ValueError:
        messagebox.showerror("Input Error", "Age must be a valid number between 0 and 150")
        return

      # Validate registration fee
      try:
        reg_fee = float(data['registration_fee'])
        if reg_fee < 0:
            raise ValueError
        data['registration_fee'] = reg_fee
      except ValueError:
        messagebox.showerror("Input Error", "Registration fee must be a valid non-negative number")
        return

      # Validate and process registration date
      if not data['registration_date']:
        data['registration_date'] = datetime.datetime.now().strftime("%d/%m/%Y")
      else:
        try:
            if not re.match(r'^\d{2}/\d{2}/\d{4}$', data['registration_date']):
                raise ValueError("Invalid date format")
            day, month, year = map(int, data['registration_date'].split('/'))
            datetime.datetime(year, month, day)
        except (ValueError, IndexError):
            messagebox.showerror("Input Error", "Registration date must be in DD/MM/YYYY format (e.g., 31/12/2025)")
            return

      logger.info(f"Processing patient data: {data}")

      try:
        success = False
        action_msg = ""

        # Update existing patient
        if self.current_reg_number:
            # Use original registration_date for update (from edit mode)
            # If not set, fall back to form value but this is risky!
            reg_date_for_update = getattr(self, 'editing_registration_date', None)
            if not reg_date_for_update:
                reg_date_for_update = data['registration_date']
            # Convert to DB format (YYYY-MM-DD)
            import datetime
            try:
                if '/' in reg_date_for_update:
                    reg_date_for_update_db = datetime.datetime.strptime(reg_date_for_update, "%d/%m/%Y").strftime("%Y-%m-%d")
                else:
                    reg_date_for_update_db = reg_date_for_update
            except Exception:
                reg_date_for_update_db = reg_date_for_update
            # Remove registration_date from update data to avoid changing partition key!
            update_data = dict(data)
            update_data.pop('registration_date', None)
            success = update_patient(self.current_reg_number, reg_date_for_update_db, **update_data)
            action_msg = "updated"
            logger.info(f"Updating patient {self.current_reg_number}")
        else:
            # Generate new registration number for new patient
            reg_number = get_next_registration_number('opd')
            if not reg_number:
                messagebox.showerror("Error", "Could not generate registration number")
                return
            data['registration_number'] = reg_number
            data['created_by'] = self.current_username
            self.current_reg_number = reg_number
            reg_number_db = add_opd_patient(**data)
            if reg_number_db:
                success = True
                action_msg = "registered"
                logger.info(f"Added new patient with registration number: {reg_number}")
            else:
                success = False
                action_msg = "register"
                logger.error("Failed to add new patient")

        if success:
            messagebox.showinfo(
                "Success",
                f"Patient '{data['first_name']} {data['last_name'] or ''}' {action_msg} successfully!\n"
                f"Registration Number: {self.current_reg_number}"
            )
            self.fields['registration_number'].config(state='normal')
            self.fields['registration_number'].delete(0, tk.END)
            self.fields['registration_number'].insert(0, str(self.current_reg_number))
            self.fields['registration_number'].config(state='readonly')
            self.save_update_button.config(text="Update Patient")
            if hasattr(self, 'back_to_register_button'):
                self.back_to_register_button.pack(side=tk.LEFT, padx=10)
            for field in self.fields.values():
                if hasattr(field, 'configure'):
                    field.configure(style='TEntry')
            self.load_all_patients()
        else:
            messagebox.showerror("Error", f"Failed to {action_msg} patient. Please check inputs or database connection.")

      except Exception as e:
        logger.error(f"Error in save_or_update_patient: {str(e)}")
        messagebox.showerror("Error", f"An unexpected error occurred: {str(e)}")

    def clear_form(self, set_defaults=True):
      for key, widget in self.fields.items():
        if isinstance(widget, ttk.Entry):
            widget.config(state='normal')
            widget.delete(0, tk.END)
            if key == 'registration_number':
                widget.config(state='readonly')  
        elif isinstance(widget, tk.Text):
            widget.delete("1.0", tk.END)
        elif isinstance(widget, tk.StringVar):
            widget.set('')
      # Ensure gender and department comboboxes stay readonly after clearing
      self.field_widgets['gender'].config(state='readonly')
      self.field_widgets['medical_department'].config(state='readonly')
      if set_defaults:
        self.fields['registration_fee'].insert(0, "5.0")
        self.fields['payment_status'].set('Paid')
        self.fields['registration_date'].insert(0, datetime.date.today().strftime("%d/%m/%Y"))
      self.fields['age'].delete(0, tk.END)

    def reset_to_new_patient(self):
        self.clear_form(set_defaults=True)
        self.current_reg_number = None
        self.save_update_button.config(text="Save New Patient")
        self.back_to_register_button.pack_forget()

    def transfer_opd_to_ipd(self):
      """Open a window to select an OPD patient and transfer to IPD, with search functionality."""
      import tkinter as tk
      from tkinter import ttk, messagebox

      top = tk.Toplevel(self.master)
      top.title("Select OPD Patient to Transfer to IPD")
      top.geometry("850x500")

      # --- Search Bar ---
      search_frame = ttk.Frame(top)
      search_frame.pack(fill="x", padx=10, pady=6)

      ttk.Label(search_frame, text="Search (Name or Reg No):").pack(side=tk.LEFT, padx=5)
      search_var = tk.StringVar()
      search_entry = ttk.Entry(search_frame, textvariable=search_var, width=35)
      search_entry.pack(side=tk.LEFT, padx=5)

      def load_patients(search_term=""):
        # Fetch OPD patients not already in IPD, filtered by search term if provided
        conn = get_db_connection()
        patients = []
        if conn:
            cur = conn.cursor(dictionary=True)
            base_query = """
                SELECT registration_number, first_name, last_name, gender, age
                FROM OPD_Patients
                WHERE registration_number NOT IN (SELECT registration_number FROM IPD_Patients)
            """
            params = ()
            if search_term:
                base_query += " AND (first_name LIKE %s OR last_name LIKE %s OR registration_number LIKE %s)"
                like = f"%{search_term}%"
                params = (like, like, like)
            base_query += " ORDER BY registration_number DESC"
            cur.execute(base_query, params)
            patients = cur.fetchall()
            cur.close()
            conn.close()
        # Populate the treeview
        tree.delete(*tree.get_children())
        for p in patients:
            tree.insert("", "end", values=(
                p["registration_number"], p["first_name"], p["last_name"], p["gender"], p["age"]
            ))

      def on_search(*args):
        search_term = search_var.get().strip()
        load_patients(search_term)

      # --- Treeview for displaying OPD patients ---
      columns = ("registration_number", "first_name", "last_name", "gender", "age")
      tree = ttk.Treeview(top, columns=columns, show="headings")
      for col in columns:
        tree.heading(col, text=col.replace('_', ' ').title())
        tree.column(col, width=150)
      tree.pack(fill="both", expand=True, padx=10, pady=10)

      # Search and show all buttons
      ttk.Button(search_frame, text="Search", command=on_search).pack(side=tk.LEFT, padx=5)
      ttk.Button(search_frame, text="Show All", command=lambda: load_patients("")).pack(side=tk.LEFT, padx=5)
      search_entry.bind("<Return>", lambda e: on_search())

      # Initial load: show all patients
      load_patients()

      def on_transfer():
        selected = tree.focus()
        if not selected:
            messagebox.showwarning("No selection", "Please select an OPD patient to transfer.")
            return
        reg_no = tree.item(selected, "values")[0]
        top.destroy()
        self.show_ipd_patient_form(prefill_opd_registration_number=reg_no)

      ttk.Button(top, text="Transfer Selected to IPD", command=on_transfer).pack(pady=10)


    def transfer_epd_to_ipd(self):
      """Open a window to select an EPD patient and transfer to IPD, with search functionality."""
      import tkinter as tk
      from tkinter import ttk, messagebox

      top = tk.Toplevel(self.master)
      top.title("Select EPD Patient to Transfer to IPD")
      top.geometry("850x500")

      # --- Search Bar ---
      search_frame = ttk.Frame(top)
      search_frame.pack(fill="x", padx=10, pady=6)

      ttk.Label(search_frame, text="Search (Name or Reg No):").pack(side=tk.LEFT, padx=5)
      search_var = tk.StringVar()
      search_entry = ttk.Entry(search_frame, textvariable=search_var, width=35)
      search_entry.pack(side=tk.LEFT, padx=5)

      def load_patients(search_term=""):
        # Fetch EPD patients not already in IPD, filtered by search term if provided
        conn = get_db_connection()
        patients = []
        if conn:
            cur = conn.cursor(dictionary=True)
            base_query = """
                SELECT registration_number, first_name, last_name, gender, age
                FROM EPD_Patients
                WHERE registration_number NOT IN (SELECT registration_number FROM IPD_Patients)
            """
            params = ()
            if search_term:
                base_query += " AND (first_name LIKE %s OR last_name LIKE %s OR registration_number LIKE %s)"
                like = f"%{search_term}%"
                params = (like, like, like)
            base_query += " ORDER BY registration_number DESC"
            cur.execute(base_query, params)
            patients = cur.fetchall()
            cur.close()
            conn.close()
        # Populate the treeview
        tree.delete(*tree.get_children())
        for p in patients:
            tree.insert("", "end", values=(
                p["registration_number"], p["first_name"], p["last_name"], p["gender"], p["age"]
            ))

      def on_search(*args):
        search_term = search_var.get().strip()
        load_patients(search_term)

      # --- Treeview for displaying EPD patients ---
      columns = ("registration_number", "first_name", "last_name", "gender", "age")
      tree = ttk.Treeview(top, columns=columns, show="headings")
      for col in columns:
        tree.heading(col, text=col.replace('_', ' ').title())
        tree.column(col, width=150)
      tree.pack(fill="both", expand=True, padx=10, pady=10)
      # Search and show all buttons
      ttk.Button(search_frame, text="Search", command=on_search).pack(side=tk.LEFT, padx=5)
      ttk.Button(search_frame, text="Show All", command=lambda: load_patients("")).pack(side=tk.LEFT, padx=5)
      search_entry.bind("<Return>", lambda e: on_search())

      # Initial load: show all patients
      load_patients()

      def on_transfer():
        selected = tree.focus()
        if not selected:
            messagebox.showwarning("No selection", "Please select an EPD patient to transfer.")
            return
        reg_no = tree.item(selected, "values")[0]
        top.destroy()
        self.show_ipd_patient_form(prefill_epd_registration_number=reg_no)

      ttk.Button(top, text="Transfer Selected to IPD", command=on_transfer).pack(pady=10)

    def perform_search(self):
      registration_number = self.reg_no_search_var.get().strip()
      name = self.name_search_var.get().strip()
      father_name = self.father_name_search_var.get().strip()
      phone = self.phone_search_var.get().strip()
      department = self.dept_search_var.get().strip()
      town = self.town_search_var.get().strip()
      state = self.state_search_var.get().strip()
      gender = self.gender_search_var.get().strip()
      age = self.age_search_var.get().strip()
      from_date = self.from_date_var.get().strip()
      to_date = self.to_date_var.get().strip()
      patient_type = self.patient_type_var.get().strip()
      # CHANGE: Always search all pages at once!
      page = 1
      page_size = 10000  # Arbitrarily large; fetch all results in one go

      try:
        results, info_msg = search_patients(
            registration_number=registration_number,
            name=name,
            father_name=father_name, 
            phone=phone,
            department=department,
            town=town,
            state=state,
            gender=gender,
            age=age,
            from_date=from_date,
            to_date=to_date,
            patient_type=patient_type,
            page=page,
            page_size=page_size
        )
        self._update_patient_tree(results, info_msg)
        # CHANGE: Disable pagination buttons after search
        self.prev_button.config(state='disabled')
        self.next_button.config(state='disabled')
        self.page_label.config(text="All results")
      except Exception as e:
        import traceback
        traceback.print_exc()
        self.show_error(f"Search error: {e}")
      finally:
        self.is_loading = False
        self.progress_bar.stop()
        self.master.config(cursor="")

    def _perform_search_thread(self):
      try:
        results, info_msg = search_patients(
            registration_number=self.reg_no_search_var.get().strip(),
            name=self.name_search_var.get().strip(),
            phone=self.phone_search_var.get().strip(),
            department=self.dept_search_var.get().strip(),
            town=self.town_search_var.get().strip(),
            state=self.state_search_var.get().strip(),
            gender=self.gender_search_var.get().strip(),
            age=self.age_search_var.get().strip(),
            from_date=self.from_date_var.get().strip(),
            to_date=self.to_date_var.get().strip(),
            patient_type=self.patient_type_var.get().strip(),
            page=self.current_page,
            page_size=self.page_size,
        )
        self.master.after(0, lambda: self._update_patient_tree(results, info_msg))
      except Exception as e:
        import traceback
        traceback.print_exc()
        self.master.after(0, self.show_error, f"Search error: {e}")
      finally:
        self.is_loading = False
        self.master.after(0, self.progress_bar.stop)
        self.master.after(0, lambda: self.master.config(cursor=""))

    def _update_patient_tree(self, patients, info_msg=None):
      for item in self.patient_tree.get_children():
        self.patient_tree.delete(item)
      for patient in patients:
        display_age = patient['age'] if patient['age'] is not None else 'N/A'
        self.patient_tree.insert("", tk.END, values=(
            patient['registration_number'],
            patient['first_name'],
            patient['last_name'],
            patient['mobile_number'],
            patient['gender'],
            display_age,
            patient['patient_type']
        ))

      self.page_label.config(text=f"Page {self.current_page}")
      self.prev_button.config(state='normal' if self.current_page > 1 else 'disabled')
      self.next_button.config(state='normal' if len(patients) == self.page_size else 'disabled')
      self.master.config(cursor="")

      # Show patients found/not found message
      if info_msg:
        messagebox.showinfo("Search Results", info_msg)
     
    def load_all_patients(self, page=None):
        if self.is_loading:
            return
        self.is_loading = True
        if page:
            self.current_page = page
        for item in self.patient_tree.get_children():
            self.patient_tree.delete(item)
        self.progress_bar.start()
        self.master.config(cursor="wait")
        threading.Thread(target=self._load_all_patients_thread, daemon=True).start()
    
    def _load_all_patients_thread(self):
        try:
            patients = get_all_patients(page=self.current_page, page_size=self.page_size)
            self.master.after(0, lambda: self._update_patient_tree(patients))
        finally:
            self.master.after(0, lambda: self.progress_bar.stop())
            self.master.after(0, lambda: setattr(self, 'is_loading', False))

    def prev_page(self):
      if self.current_page > 1:
        self.current_page -= 1
        if self.reg_no_search_var.get().strip() or self.name_search_var.get().strip():
            self.perform_search()
        else:
            self.load_all_patients()

    def next_page(self):
      self.current_page += 1
      if self.reg_no_search_var.get().strip() or self.name_search_var.get().strip():
        self.perform_search()
      else:
        self.load_all_patients()

    def edit_selected_patient(self):
      selected = self.patient_tree.focus()
      if not selected:
        messagebox.showwarning("No selection", "Select a patient to edit.")
        return
      values = self.patient_tree.item(selected, "values")
      reg_no = values[0]
      patient_type = values[6]  # Last col is patient_type

      if patient_type == "OPD":
        patient = get_patient_by_reg_number(reg_no)
        if patient:
            self.notebook.select(self.registration_frame)
            self.current_reg_number = reg_no
            
            # Populate registration form with patient data
            for key in self.fields:
                widget = self.fields[key]
                value = patient.get(key, "")
                
                # Special handling for registration_date to ensure dd/mm/yyyy format
                if key == 'registration_date' and value:
                    try:
                        if isinstance(value, str):
                            # Handle potential different date formats
                            if '-' in value:
                                date_obj = datetime.datetime.strptime(value, "%Y-%m-%d")
                            elif '/' in value:
                                # Check if it's already in dd/mm/yyyy
                                if len(value) == 10 and value[2] == '/' and value[5] == '/':
                                    date_obj = datetime.datetime.strptime(value, "%d/%m/%Y")
                                else:
                                    date_obj = datetime.datetime.strptime(value, "%Y/%m/%d")
                            else:
                                continue
                            value = date_obj.strftime("%d/%m/%Y")
                        elif isinstance(value, datetime.date):
                            value = value.strftime("%d/%m/%Y")
                    except (ValueError, TypeError) as e:
                        logger.error(f"Date conversion error for {reg_no}: {e}")
                        value = datetime.datetime.now().strftime("%d/%m/%Y")
                
                if isinstance(widget, ttk.Entry):
                    widget.config(state='normal')
                    widget.delete(0, tk.END)
                    widget.insert(0, str(value) if value is not None else "")
                    if key == 'registration_number':
                        widget.config(state='readonly')
                elif isinstance(widget, tk.StringVar):
                    widget.set(str(value) if value is not None else "")
                elif isinstance(widget, tk.Text):
                    widget.delete("1.0", tk.END)
                    widget.insert("1.0", str(value) if value is not None else "")
            

            # Update UI elements for edit mode
            self.save_update_button.config(text="Update Patient")
            if self.current_username == 'admin':
                self.back_to_register_button.pack(side=tk.LEFT, padx=10)
        else:
            messagebox.showerror("Not Found", f"No OPD patient found with registration number {reg_no}.")
    
      elif patient_type == "EPD":
        patient = self.get_epd_patient_by_reg_number(reg_no)
        if patient:
          # Clear reception frame and create EPD form
          for widget in self.reception_frame.winfo_children():
            widget.destroy()
        
          self.notebook.select(self.reception_frame)
          self.show_emergency_case_form()

          self.editing_epd_reg_number = reg_no
        
          # Populate form with patient data
          for key, widget in self.emergency_field_widgets.items():
            value = patient.get(key, "")
            
            # Handle date formatting
            if key == 'date' and value:
                try:
                    # Convert various date formats to dd/mm/yyyy
                    if isinstance(value, str):
                        # Handle different date separators and formats
                        if '-' in value:
                            if value[2] == '-':  # dd-mm-yyyy
                                date_obj = datetime.datetime.strptime(value, "%d-%m-%Y")
                            else:  # yyyy-mm-dd
                                date_obj = datetime.datetime.strptime(value, "%Y-%m-%d")
                        elif '/' in value:
                            if value[2] == '/':  # dd/mm/yyyy
                                date_obj = datetime.datetime.strptime(value, "%d/%m/%Y")
                            else:  # yyyy/mm/dd
                                date_obj = datetime.datetime.strptime(value, "%Y/%m/%d")
                        else:
                            # If no separator, assume YYYYMMDD
                            date_obj = datetime.datetime.strptime(value, "%Y%m%d")
                        value = date_obj.strftime("%d/%m/%Y")
                    elif isinstance(value, datetime.date):
                        value = value.strftime("%d/%m/%Y")
                except Exception as e:
                    print(f"Date conversion error: {e}")
                    value = datetime.datetime.now().strftime("%d/%m/%Y")
            
            if isinstance(widget, ttk.Entry):
                widget.config(state='normal')
                widget.delete(0, tk.END)
                widget.insert(0, str(value) if value is not None else "")
                if key == 'registration_number':
                    widget.config(state='readonly')
            elif isinstance(widget, ttk.Combobox):
                widget.set(str(value) if value is not None else "")
            elif isinstance(widget, tk.Text):
                widget.delete("1.0", tk.END)
                widget.insert("1.0", str(value) if value is not None else "")

            # Ensure gender, department, and police_case are always readonly dropdowns (EPD edit case)
            for k in ('gender', 'medical_department', 'police_case'):
             widget = self.emergency_field_widgets.get(k)
             if isinstance(widget, ttk.Combobox):
              widget.config(state='readonly')
        
          # Update button text
          for widget in self.reception_frame.winfo_children():
            if isinstance(widget, ttk.Frame):
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Button) and child.cget('text') == "Save Emergency Case":
                        child.config(text="Update Emergency Case")
                        break
        else:
          messagebox.showerror("Not Found", f"No EPD patient found with registration number {reg_no}.")
    
      elif patient_type == "IPD":
        # Clear all widgets in IPD frame before creating the form
        for widget in self.ipd_frame.winfo_children():
            widget.destroy()
            
        patient = None
        conn = get_db_connection()
        if conn:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM IPD_Patients WHERE registration_number = %s", (reg_no,))
            patient = cur.fetchone()
            cur.close()
            conn.close()
        
        if patient:
            self.notebook.select(self.ipd_frame)
            self.create_ipd_form_widgets()
            
            for key, widget in self.ipd_field_widgets.items():
                value = patient.get(key, "")
                # Use consistent date format for admission/discharge date
                if key in ("admission_date", "discharge_date") and value:
                    value = self.to_display_date(str(value))
                
                if isinstance(widget, ttk.Entry):
                    widget.config(state='normal')
                    widget.delete(0, tk.END)
                    widget.insert(0, str(value) if value is not None else "")
                    if key == 'registration_number':
                        widget.config(state='readonly')
                elif isinstance(widget, tk.StringVar):
                    widget.set(str(value) if value is not None else "")
                elif isinstance(widget, tk.Text):
                    widget.delete("1.0", tk.END)
                    widget.insert("1.0", str(value) if value is not None else "")
                elif isinstance(widget, ttk.Combobox):
                    widget.set(str(value) if value is not None else "")
            
            self.last_saved_ipd_registration_number = patient.get('registration_number')
            self.save_ipd_button.config(text="Update Patient")
        else:
            messagebox.showerror("Not Found", f"No IPD patient found with registration number {reg_no}.")
    
    def to_display_date(self, date_str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.datetime.strptime(date_str, fmt).strftime("%d/%m/%Y")
            except Exception:
                continue
        return date_str

    def show_emergency_case_form(self):
      import datetime
      self.editing_epd_reg_number = None
      for widget in self.reception_frame.winfo_children():
        widget.destroy()

      row_idx = 0
      ttk.Label(self.reception_frame, text="Emergency Patient Registration",
            font=('Arial', 14, 'bold'), background='#e0f2f7', foreground='#B71C1C').grid(
        row=row_idx, column=0, columnspan=2, pady=(0, 20), sticky="ew")
      row_idx += 1

      self.emergency_fields = {}
      self.emergency_field_widgets = {}

      field_definitions = [
        ("Registration Number:", "registration_number", ttk.Entry),
        ("Date (DD/MM/YYYY):", "date", ttk.Entry),
        ("First Name:", "first_name", ttk.Entry),
        ("Last Name:", "last_name", ttk.Entry),
        ("Father's Name:", "father_name", ttk.Entry),
        ("Age:", "age", ttk.Entry),
        ("Gender:", "gender", ttk.Combobox, ['Male', 'Female', 'Other']),
        ("Mobile Number:", "mobile_number", ttk.Entry),
        ("Email:", "email", ttk.Entry),
        ("ABHA Number:", "abha_number", ttk.Entry),
        ("Police Case (Yes/No):", "police_case", ttk.Combobox, ['Yes', 'No']),
        ("Address:", "address", ttk.Entry),         
        ("Post Office:", "post_office", ttk.Entry),
        ("Town:", "town", ttk.Entry),
        ("State:", "state", ttk.Entry),
        ("Medical Department:", "medical_department", ttk.Combobox, [
            'General Medicine', 'Pediatrics', 'Orthopedics', 'Gynecology',
            'Cardiology', 'Neurology', 'Surgery', 'ENT', 'Dermatology', 'Psychiatry'
        ]),
      ]

      field_keys_order = []

      for label_text, key, widget_type, *widget_info in field_definitions:
        ttk.Label(self.reception_frame, text=label_text).grid(
            row=row_idx, column=0, sticky="w", pady=5, padx=10
        )
        if widget_type == tk.Text:
            text_widget = tk.Text(self.reception_frame, height=3, width=120)
            text_widget.grid(row=row_idx, column=1, sticky="ew", pady=5, padx=10)
            self.emergency_fields[key] = text_widget
            self.emergency_field_widgets[key] = text_widget
            text_widget.bind('<Return>', self.move_to_next_emergency_field)
        elif widget_type == ttk.Combobox:
            combobox_var = tk.StringVar()
            combobox = ttk.Combobox(self.reception_frame, textvariable=combobox_var,
                                    values=widget_info[0], font=('Arial', 10), state='readonly', width=110)
            combobox.grid(row=row_idx, column=1, sticky="ew", pady=5, padx=10)
            self.emergency_fields[key] = combobox_var
            self.emergency_field_widgets[key] = combobox
            combobox.bind('<Return>', self.move_to_next_emergency_field)
            if key == 'police_case':
                combobox.set('No')  # Default value
        else:
            if key == "registration_number":
                entry = ttk.Entry(self.reception_frame, width=110, font=('Arial', 10), state='readonly')
            else:
                entry = ttk.Entry(self.reception_frame, width=110, font=('Arial', 10))
            entry.grid(row=row_idx, column=1, sticky="ew", pady=5, padx=10)
            if key == "date":
                entry.insert(0, datetime.date.today().strftime('%d/%m/%Y'))
            self.emergency_fields[key] = entry
            self.emergency_field_widgets[key] = entry
            entry.bind('<Return>', self.move_to_next_emergency_field)
        field_keys_order.append(key)
        row_idx += 1

      # Buttons
      button_frame = ttk.Frame(self.reception_frame, style='TFrame')
      button_frame.grid(row=row_idx, column=0, columnspan=2, pady=20, sticky="ew")
      ttk.Button(button_frame, text="Save Emergency Case", command=self.save_emergency_case).pack(side=tk.LEFT, padx=10)
      ttk.Button(button_frame, text="Print Card", command=self.print_emergency_card).pack(side=tk.LEFT, padx=10)
      ttk.Button(button_frame, text="Back", command=self.create_reception_widgets).pack(side=tk.LEFT, padx=10)
      ttk.Button(button_frame, text="Clear Form", command=self.clear_emergency_form).pack(side=tk.LEFT, padx=10)
      self.master.geometry("1600x900")


    def move_to_next_emergency_field(self, event):
      current_widget = event.widget
      for key, widget in self.emergency_field_widgets.items():
        if widget == current_widget:
            current_key = key
            break
      else:
        return

      field_order = [
        'registration_number', 'date', 'first_name', 'last_name', 'father_name',
        'age', 'gender', 'mobile_number', 'email', 'abha_number', 'police_case',
        'address', 'post_office', 'town', 'state', 'medical_department'
      ]
    
      if current_key in field_order:
        current_index = field_order.index(current_key)
        next_index = current_index + 1
        if next_index < len(field_order):
            next_key = field_order[next_index]
            next_widget = self.emergency_field_widgets.get(next_key)
            if next_widget:
                next_widget.focus_set()

    def save_emergency_case(self):
      import datetime

      # Collect all field values from the form
      data = {}
      for key, widget in self.emergency_fields.items():
        if hasattr(widget, 'get'):
            if isinstance(widget, tk.Text):
                value = widget.get("1.0", tk.END).strip()
            else:
                value = widget.get().strip()
        else:
            value = None
        data[key] = value
        
      if not data.get('mobile_number'):
        data['mobile_number'] = None

      # Validate required fields
      missing_fields = []
      if not data.get('first_name'):
        missing_fields.append('First Name')
      if not data.get('age'):
        missing_fields.append('Age')
      if not data.get('gender'):
        missing_fields.append('Gender')
      if not data.get('medical_department'):
        missing_fields.append('Medical Department')
    
      if missing_fields:
        messagebox.showerror("Input Error", "Please provide: " + ", ".join(missing_fields))
        return

      # Validate mobile number
      mobile = data.get('mobile_number', '')
      if mobile and (not mobile.isdigit() or len(mobile) != 10):
        messagebox.showerror("Input Error", "Mobile number must be 10 digits.")
        return

      # Validate age
      try:
        data['age'] = int(data.get('age'))
        if data['age'] < 0 or data['age'] > 150:
            raise ValueError
      except (ValueError, TypeError):
        messagebox.showerror("Input Error", "Age must be a valid number between 0 and 150.")
        return

      # Validate and convert date for DB
      date_str = data.get('date')
      if date_str:
        try:
            datetime.datetime.strptime(date_str, '%d/%m/%Y')
            data['date'] = ut.convert_to_db_date_format(date_str)
        except ValueError:
            messagebox.showerror("Input Error", "Date must be in DD/MM/YYYY format.")
            return
      else:
        data['date'] = ut.convert_to_db_date_format(datetime.date.today().strftime('%d/%m/%Y'))

      # Validate and convert arrival_datetime if present
      arrival_datetime_str = data.get('arrival_datetime')
      if arrival_datetime_str:
        try:
            # Accept DD/MM/YYYY HH:MM:SS or fallback to now
            data['arrival_datetime'] = datetime.datetime.strptime(arrival_datetime_str, "%d/%m/%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            # Fallback to now
            data['arrival_datetime'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
      else:
        data['arrival_datetime'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

      # Validate and convert discharge_datetime if present
      discharge_datetime_str = data.get('discharge_datetime')
      if discharge_datetime_str:
        try:
            data['discharge_datetime'] = datetime.datetime.strptime(discharge_datetime_str, "%d/%m/%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            data['discharge_datetime'] = None

      if hasattr(self, 'editing_epd_reg_number') and self.editing_epd_reg_number:
        reg_number = self.editing_epd_reg_number
        data.pop('registration_number', None)
        success = update_epd_patient(reg_number, **data)
        if success:
            self.last_emergency_save_data = data.copy()
            self.last_emergency_save_data["registration_number"] = reg_number
            messagebox.showinfo("Saved", f"Emergency case updated!\nReg No: {reg_number}")
        else:
            self.last_emergency_save_data = None
            messagebox.showerror("Error", f"Failed to update emergency case for Reg No: {reg_number}")
      else:
        # Add new patient
        reg_number = get_next_registration_number('epd')
        if not reg_number:
            messagebox.showerror("Error", "Could not generate registration number.")
            return
        data['registration_number'] = reg_number
        saved_reg_number = add_epd_patient(
            data.get('registration_number'),
            data.get('first_name'),
            data.get('last_name'),
            data.get('father_name'),
            data.get('abha_number'),
            data.get('age'),
            data.get('gender'),
            data.get('mobile_number'),
            data.get('email'),
            data.get('address'),
            data.get('post_office'),
            data.get('town'),
            data.get('state'),
            data.get('medical_department'),
            data.get('police_case'),
            data.get('emergency_type'),
            data.get('arrival_mode'),
            data.get('arrival_datetime'),
            data.get('triage_level'),
            data.get('attending_doctor'),
            data.get('discharge_datetime'),
            data.get('outcome'),
            data.get('notes'),
            data.get('date'),
            self.current_username
        )
        if saved_reg_number:
            self.last_emergency_save_data = data.copy()
            self.last_emergency_save_data["registration_number"] = reg_number
            messagebox.showinfo(
                "Saved",
                f"Emergency case saved!\nReg No: {reg_number}\nYou can now print the card."
            )
        else:
            self.last_emergency_save_data = None
            messagebox.showerror("Error", "Failed to save emergency case. Check inputs or database.")

    def clear_emergency_form(self):
      import datetime
      self.editing_epd_reg_number = None  # Exit edit mode, so next save is a new patient

      for key, widget in self.emergency_field_widgets.items():
        if isinstance(widget, ttk.Entry):
            widget.config(state='normal')
            widget.delete(0, tk.END)

            if key == 'date':
                widget.insert(0, datetime.date.today().strftime('%d/%m/%Y'))
            if key == 'registration_number':
                widget.config(state='readonly')
        elif isinstance(widget, tk.Text):
            widget.delete("1.0", tk.END)
        elif isinstance(widget, ttk.Combobox):
            widget.set('')
            if key == 'police_case':
                widget.set('No')

      # Ensure gender, department, and police_case are always readonly dropdowns
      if 'gender' in self.emergency_field_widgets:
        self.emergency_field_widgets['gender'].config(state='readonly')
      if 'medical_department' in self.emergency_field_widgets:
        self.emergency_field_widgets['medical_department'].config(state='readonly')
      if 'police_case' in self.emergency_field_widgets:
        self.emergency_field_widgets['police_case'].config(state='readonly')
    
    def print_emergency_card(self):
      import tkinter as tk
      from tkinter import messagebox

      data = getattr(self, 'last_emergency_save_data', None)
      if not data:
        messagebox.showerror("Error", "No emergency case data has been saved yet.\nSave before printing!")
        return

      # --- Window setup for A4 ---
      a4_width_px = 793
      a4_height_px = 1122

      preview_window = tk.Toplevel(self.master)
      preview_window.title("EPD Bed Head Ticket Print Preview")
      preview_window.geometry(f"{a4_width_px}x{a4_height_px}")
      preview_window.config(bg="white")
      preview_window.resizable(False, False)
      preview_window.grab_set()

      # --- Outer Frame with margin ---
      outer_frame = tk.Frame(preview_window, bg="white", width=a4_width_px, height=a4_height_px)
      outer_frame.pack(expand=True, fill='both', padx=32, pady=32)

      # --- Header ---
      tk.Label(outer_frame, text="SRI RAM JANKI MEDICAL COLLEGE & HOSPITAL", font=('Arial', 22, 'bold'), bg='white').pack(anchor='center', pady=(10,0))
      tk.Label(outer_frame, text="MUZAFFARPUR", font=('Arial', 16, 'bold'), bg='white').pack(anchor='center', pady=(0,4))
      tk.Label(outer_frame, text="EPD PATIENT CARD", font=('Arial', 16, 'bold', 'underline'), bg='white').pack(anchor='center', pady=(0,18))

      # --- Patient Info Section ---
      info_frame = tk.Frame(outer_frame, bg="white")
      info_frame.pack(fill='x', padx=22, pady=(0,12))

      left_labels = [
        "Reg. No.:", "Name:", "Father's/Husband's Name:", "Address:", "Town:", "Date:"
      ]
      right_labels = [
        "Age:", "Gender:", "Mobile:", "Department:", "State:", "Attending Doctor:"
      ]
      def safe(v, default="N/A"):
        val = data.get(v)
        return "" if val is None or str(val).strip().lower() in ("", "none", "null", "n/a") else str(val)
      def safe_date(v):
        val = data.get(v)
        try:
            import datetime
            if isinstance(val, datetime.date):
                return val.strftime("%d/%m/%Y")
            elif isinstance(val, str) and len(val) >= 10:
                from datetime import datetime as dt
                try:
                    if "/" in val:
                        return val
                    elif "-" in val:
                        return dt.strptime(val[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
                except Exception:
                    return val
            return val or ""
        except Exception:
            return val or ""
      left_values = [
        safe('registration_number'),
        f"{safe('first_name','')} {safe('last_name','')}".strip(),
        safe('father_name'),
        safe('address'),
        safe('town'),
        safe_date('date'),
        
        ]
      right_values = [
        safe('age'),
        safe('gender'),
        safe('mobile_number'),
        safe('medical_department'),
        safe('state'),
        safe('attending_doctor'),
      ]
      for i in range(len(left_labels)):
        tk.Label(info_frame, text=left_labels[i], font=('Arial', 12, 'bold'), bg='white', anchor='w').grid(
            row=i, column=0, sticky='w', padx=2, pady=3
        )
        tk.Label(info_frame, text=left_values[i], font=('Arial', 12), bg='white', anchor='w').grid(
            row=i, column=1, sticky='w', padx=2, pady=3
        )
        tk.Label(info_frame, text=right_labels[i], font=('Arial', 12, 'bold'), bg='white', anchor='w').grid(
            row=i, column=2, sticky='w', padx=16, pady=3
        )
        tk.Label(info_frame, text=right_values[i], font=('Arial', 12), bg='white', anchor='w').grid(
            row=i, column=3, sticky='w', padx=2, pady=3
        )


      # --- Table for Clinical Notes ---
      table_frame = tk.Frame(outer_frame, bg="white", bd=1, relief="solid")
      table_frame.pack(fill="x", expand=False, padx=2, pady=(18,18))
      for col, text, width in zip(range(3), ["Date/Time", "Clinical Notes", "Advice"], [20, 54, 22]):
        tk.Label(table_frame, text=text, font=('Arial', 12, 'bold'), bg="white", borderwidth=1, relief="solid", width=width, anchor='center').grid(row=0, column=col, sticky="nsew")
        table_frame.columnconfigure(col, weight=1)
      for i in range(1, 8):  # 7 rows
        for col, width in zip(range(3), [20, 54, 22]):
            tk.Label(table_frame, text="", font=('Arial', 12), bg="white", borderwidth=1, relief="solid", width=width, anchor='w').grid(row=i, column=col, sticky="nsew")

      # --- Print Button ---
      def on_print():
       try:
        from dot_matrix_print_utils import print_epd_card_dot_matrix
        print_epd_card_dot_matrix(self.last_emergency_save_data)
        messagebox.showinfo("Print", "Print job sent!")
        self.last_emergency_save_data = None  # Clear data after printing
       except Exception as e:
        messagebox.showerror("Print Error", f"Printing failed: {e}")

      tk.Button(
        outer_frame,
        text="Print",
        font=('Arial', 12, 'bold'),
        command=on_print
      ).pack(pady=(24,0))

      preview_window.transient(self.master)
      preview_window.wait_window(preview_window)

    def prompt_and_generate_opd_card(self):
      from tkinter import simpledialog
      reg_no = simpledialog.askstring("OPD Patient Card", "Enter Registration Number of the OPD patient:")
      if reg_no is None:  # User cancelled
        return
      reg_no = reg_no.strip()
      if not reg_no:
        messagebox.showerror("Input Error", "Please enter a registration number.")
        return
      patient = get_patient_by_reg_number(reg_no)
      if not patient:
        messagebox.showerror("Not Found", f"No OPD patient found with registration number {reg_no}.")
        return
      self.current_reg_number = reg_no
      self.show_print_preview()

    def prompt_and_generate_epd_card(self):
      from tkinter import simpledialog
      reg_no = simpledialog.askstring("EPD Patient Card", "Enter Registration Number of the EPD patient:")
      if reg_no is None:
        return
      reg_no = reg_no.strip()
      if not reg_no:
        messagebox.showerror("Input Error", "Please enter a registration number.")
        return
      patient = self.get_epd_patient_by_reg_number(reg_no)
      if not patient:
        messagebox.showerror("Not Found", f"No EPD patient found with registration number {reg_no}.")
        return
      self.last_emergency_save_data = patient  # reuse your print_emergency_card logic
      self.print_emergency_card()

    # --- Transfer OPD/EPD to IPD: Always generate a new registration number ---

    def show_ipd_patient_form(self, prefill_opd_registration_number=None, prefill_epd_registration_number=None):
      import datetime
      # Clear the IPD form
      for widget in self.ipd_frame.winfo_children():
        widget.destroy()
      self.create_ipd_form_widgets()
      self.ipd_form_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10, columnspan=2)

      # Always blank and readonly for new IPD registration
      reg_entry = self.ipd_field_widgets['registration_number']
      reg_entry.config(state='normal')
      reg_entry.delete(0, tk.END)
      reg_entry.config(state='readonly')

      patient_data = None
      previous_reg_no = None
      if prefill_opd_registration_number:
        patient_data = self.get_opd_patient_by_reg_number(prefill_opd_registration_number)
        previous_reg_no = prefill_opd_registration_number
      elif prefill_epd_registration_number:
        patient_data = self.get_epd_patient_by_reg_number(prefill_epd_registration_number)
        previous_reg_no = prefill_epd_registration_number

      if patient_data:
        mapping = {
            'first_name': 'first_name',
            'last_name': 'last_name',
            'father_name': 'father_name',
            'abha_number': 'abha_number',
            'age': 'age',
            'gender': 'gender',
            'mobile_number': 'mobile_number',
            'email': 'email',
            'address': 'address',
            'post_office': 'post_office',
            'town': 'town',
            'state': 'state',
            'medical_department': 'medical_department',
        }
        for form_key, data_key in mapping.items():
            widget = self.ipd_field_widgets.get(form_key)
            value = patient_data.get(data_key, '')
            if isinstance(widget, ttk.Entry):
                widget.config(state='normal')
                widget.delete(0, tk.END)
                widget.insert(0, str(value) if value is not None else '')
            elif isinstance(widget, tk.Text):
                widget.delete("1.0", tk.END)
                widget.insert("1.0", str(value) if value is not None else '')
            elif isinstance(widget, ttk.Combobox):
                widget.set(str(value) if value is not None else '')

      # IPD-only fields blank for new/transfer
      for key in ['police_case', 'bed_number', 'room_number', 'admission_date', 'discharge_date', 'notes']:
        widget = self.ipd_field_widgets.get(key)
        if isinstance(widget, ttk.Entry):
            widget.config(state='normal')
            widget.delete(0, tk.END)
            if key == 'admission_date':
                widget.insert(0, datetime.date.today().strftime("%d/%m/%Y"))
        elif isinstance(widget, tk.Text):
            widget.delete("1.0", tk.END)
        elif isinstance(widget, ttk.Combobox):
            widget.set('')

      # Optional: Show previous reg no for traceability
      if previous_reg_no:
        if 'previous_registration_number' in self.ipd_field_widgets:  # If field exists
            widget = self.ipd_field_widgets['previous_registration_number']
            widget.config(state='normal')
            widget.delete(0, tk.END)
            widget.insert(0, previous_reg_no)
            widget.config(state='readonly')

      if 'police_case' in self.ipd_field_widgets:
        self.ipd_field_widgets['police_case'].set('No')
        self.ipd_field_widgets['police_case'].state(['readonly'])

      if hasattr(self, "notebook") and hasattr(self, "ipd_frame"):
        self.notebook.select(self.ipd_frame)

      if patient_data:
        msg = "Patient details copied. Previous registration number: {}".format(previous_reg_no) if previous_reg_no else "Patient details copied."
        messagebox.showinfo("IPD Transfer", msg + " Please fill the remaining IPD details and save.")


    def save_ipd_patient(self):
      # ... gather all field values and validate as before ...
      # Build ipd_data dictionary
      mandatory_fields = {
        'first_name': 'First Name',
        'father_name': "Father's Name",
        'age': 'Age',
        'gender': 'Gender',
        'mobile_number': 'Mobile Number',
        'address': 'Address',
        'town': 'Town',
        'state': 'State',
        'medical_department': 'Medical Department',
        'police_case': 'Police Case',
        'bed_number': 'Bed Number',
        'room_number': 'Room Number',
        'admission_date': 'Admission Date'
      }
      missing_fields = []
      data = {}
      for key, label in mandatory_fields.items():
        widget = self.ipd_field_widgets[key]
        if isinstance(widget, tk.Text):
            value = widget.get("1.0", tk.END).strip()
        elif isinstance(widget, ttk.Combobox):
            value = widget.get().strip()
        elif isinstance(widget, ttk.Entry):
            value = widget.get().strip()
        elif isinstance(widget, tk.StringVar):
            value = widget.get().strip()
        else:
            value = ''
        if not value:
            missing_fields.append(label)
        data[key] = value

      for key in ['last_name', 'abha_number', 'email', 'post_office', 'discharge_date']:
        widget = self.ipd_field_widgets.get(key)
        if widget:
            if isinstance(widget, tk.Text):
                data[key] = widget.get("1.0", tk.END).strip() or None
            else:
                data[key] = widget.get().strip() or None
        else:
            data[key] = None
      if 'notes' in self.ipd_field_widgets:
        data['notes'] = self.ipd_field_widgets['notes'].get("1.0", tk.END).strip() or None
      else:
        data['notes'] = None

      if missing_fields:
        messagebox.showerror("Input Error", f"Please fill in the following required fields: {', '.join(missing_fields)}")
        return

      if not data['mobile_number'].isdigit() or len(data['mobile_number']) != 10:
        messagebox.showerror("Input Error", "Mobile number must be 10 digits.")
        return

      if data['email'] and not re.match(r"[^@]+@[^@]+\.[^@]+", data['email']):
        messagebox.showerror("Input Error", "Invalid email format.")
        return

      try:
        data['age'] = int(data['age'])
        if data['age'] < 0 or data['age'] > 150:
            raise ValueError
      except ValueError:
        messagebox.showerror("Input Error", "Age must be a valid number between 0 and 150.")
        return

      try:
        admission_date_db = datetime.datetime.strptime(data['admission_date'], "%d/%m/%Y").strftime("%Y-%m-%d")
      except Exception:
        messagebox.showerror("Input Error", "Admission date must be DD/MM/YYYY.")
        return

      discharge_date_db = None
      if data['discharge_date']:
        try:
            discharge_date_db = datetime.datetime.strptime(data['discharge_date'], "%d/%m/%Y").strftime("%Y-%m-%d")
        except Exception:
            messagebox.showerror("Input Error", "Discharge date must be DD/MM/YYYY.")
            return

      # Prepare ipd_data for DB operations (insert or update)
      ipd_data = {
        "first_name": data['first_name'],
        "last_name": data.get('last_name'),
        "father_name": data['father_name'],
        "abha_number": data.get('abha_number'),
        "age": data['age'],
        "gender": data['gender'],
        "mobile_number": data['mobile_number'],
        "email": data.get('email'),
        "address": data['address'],
        "post_office": data.get('post_office'),
        "town": data['town'],
        "state": data['state'],
        "medical_department": data['medical_department'],
        "police_case": data['police_case'],
        "bed_number": data['bed_number'],
        "room_number": data['room_number'],
        "admission_date": admission_date_db,
        "discharge_date": discharge_date_db,
        "notes": data.get('notes')
      }

      # --- NEW LOGIC: If editing (Update), else Insert ---
      if self.last_saved_ipd_registration_number:
        reg_no = self.last_saved_ipd_registration_number
        success = update_ipd_patient(reg_no, **ipd_data)
        if success:
            messagebox.showinfo("Success", f"Patient {reg_no} updated successfully!")
            if self.ipd_print_button:
                self.ipd_print_button.config(state='normal')
        else:
            messagebox.showerror("Error", f"Failed to update IPD patient {reg_no}.")
      else:
        reg_no = get_next_registration_number('ipd')
        ipd_data["registration_number"] = reg_no
        ipd_id = self.save_ipd_patient_to_db(ipd_data)
        if ipd_id:
            self.last_saved_ipd_registration_number = reg_no
            messagebox.showinfo("Success", f"Patient saved as registration number {reg_no}")
            self.ipd_field_widgets['registration_number'].config(state='normal')
            self.ipd_field_widgets['registration_number'].delete(0, tk.END)
            self.ipd_field_widgets['registration_number'].insert(0, str(reg_no))
            self.ipd_field_widgets['registration_number'].config(state='readonly')
            if self.ipd_print_button:
                self.ipd_print_button.config(state='normal')
        else:
            messagebox.showerror("Error", "Failed to register IPD patient. Check inputs or database.")

    def get_epd_patient_by_reg_number(self, registration_number):
      """
      Fetch EPD patient details by registration number.
      Returns a dict of patient data, or None if not found.
      """
      conn = get_db_connection()
      if not conn:
        return None
      try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM EPD_Patients WHERE registration_number = %s", (registration_number,))
        patient = cur.fetchone()
        cur.close()
        return patient
      except Exception as e:
        print(f"Error fetching EPD patient: {e}")
        return None
      finally:
        conn.close()

    def get_opd_patient_by_reg_number(self, registration_number):
      """
      Fetch OPD patient details by registration number.
      Returns a dict of patient data, or None if not found.
      """
      conn = get_db_connection()
      if not conn:
        return None
      try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM OPD_Patients WHERE registration_number = %s", (registration_number,))
        patient = cur.fetchone()
        cur.close()
        return patient
      except Exception as e:
        print(f"Error fetching OPD patient: {e}")
        return None
      finally:
        conn.close()

    def create_ipd_form_widgets(self):
      # Clear existing widgets
      for widget in self.ipd_frame.winfo_children():
        widget.destroy()

      # Create main frame
      self.ipd_form_frame = ttk.Frame(self.ipd_frame)
      self.ipd_form_frame.pack(fill='both', expand=True, padx=20, pady=10)

      # Title - Left aligned
      ttk.Label(self.ipd_form_frame, text="IPD Patient Registration",
            font=('Arial', 14, 'bold'), background='#e0f2f7', foreground='#0D47A1').pack(pady=(0, 20), anchor='w')

      # Create form frame
      form_frame = ttk.Frame(self.ipd_form_frame)
      form_frame.pack(fill='both', expand=True)

      self.ipd_fields = {}
      self.ipd_field_widgets = {}

      row_idx = 0
      field_definitions = [
        ("Registration No.:", "registration_number", False, ttk.Entry),
        ("First Name:", "first_name", True, ttk.Entry),
        ("Last Name:", "last_name", False, ttk.Entry),
        ("Father's Name:", "father_name", True, ttk.Entry),
        ("ABHA Number:", "abha_number", False, ttk.Entry),
        ("Age:", "age", True, ttk.Entry),
        ("Gender:", "gender", True, ttk.Combobox, ['Male', 'Female', 'Other']),
        ("Mobile Number:", "mobile_number", True, ttk.Entry),
        ("Email:", "email", False, ttk.Entry),
        ("Address:", "address", True, ttk.Entry),
        ("Post Office:", "post_office", False, ttk.Entry),
        ("Town:", "town", True, ttk.Entry),
        ("State:", "state", True, ttk.Entry),
        ("Police Case:", "police_case", False, ttk.Combobox, ['No', 'Yes']),
        ("Bed Number:", "bed_number", True, ttk.Entry),
        ("Room Number:", "room_number", True, ttk.Entry),
        ("Admission Date (DD/MM/YYYY):", "admission_date", False, ttk.Entry),
        ("Discharge Date (DD/MM/YYYY):", "discharge_date", False, ttk.Entry),
        ("Medical Department:", "medical_department", True, ttk.Combobox, [
            'General Medicine', 'Pediatrics', 'Orthopedics', 'Gynecology',
            'Cardiology', 'Neurology', 'Surgery', 'ENT', 'Dermatology', 'Psychiatry'
        ]),
        ("Notes:", "notes", False, tk.Text),
        ]

      # Save field order for Enter key navigation
      self.ipd_field_order = [fd[1] for fd in field_definitions]

      for label_text, key, required, widget_type, *widget_info in field_definitions:
        # Label in col 0, asterisk (if required) in col 1, widget in col 2
        ttk.Label(form_frame, text=label_text.rstrip(), anchor="w").grid(row=row_idx, column=0, sticky="w", pady=3, padx=(0, 4))
        if required:
            ttk.Label(form_frame, text="*", foreground="red", background='#e0f2f7', anchor="w").grid(row=row_idx, column=1, sticky="w")
        else:
            ttk.Label(form_frame, text="", background='#e0f2f7').grid(row=row_idx, column=1, sticky="w")  # empty for alignment

        if widget_type == tk.Text:
            text_widget = tk.Text(form_frame, height=3, width=40, font=('Arial', 10), wrap='word')
            text_widget.grid(row=row_idx, column=2, sticky="ew", padx=(2, 10), pady=3)
            self.ipd_fields[key] = text_widget
            self.ipd_field_widgets[key] = text_widget
        elif widget_type == ttk.Combobox:
            combobox_var = tk.StringVar()
            combobox = ttk.Combobox(form_frame, textvariable=combobox_var,
                                    values=widget_info[0], font=('Arial', 10),
                                    state='readonly', width=38)
            combobox.grid(row=row_idx, column=2, sticky="ew", padx=(2, 10), pady=3)
            self.ipd_fields[key] = combobox_var
            self.ipd_field_widgets[key] = combobox
            if key == 'police_case':
                combobox.set('No')
        else:
            entry = ttk.Entry(form_frame, width=40, font=('Arial', 10))
            if key == 'registration_number':
                entry.config(state='readonly')
            entry.grid(row=row_idx, column=2, sticky="ew", padx=(2, 10), pady=3)
            self.ipd_fields[key] = entry
            self.ipd_field_widgets[key] = entry
            if key == 'admission_date':
                entry.insert(0, datetime.datetime.now().strftime('%d/%m/%Y'))
        row_idx += 1


      # Configure the form frame columns
      form_frame.columnconfigure(0, weight=0)  # label
      form_frame.columnconfigure(1, weight=0)  # asterisk
      form_frame.columnconfigure(2, weight=1)  # widget

      # Create button frame at the bottom
      button_frame = ttk.Frame(self.ipd_form_frame)
      button_frame.pack(pady=15, anchor='center')

      # Add buttons with consistent width
      button_width = 15
      padding = 5

      self.save_ipd_button = ttk.Button(
        button_frame, 
        text="Save IPD Patient", 
        command=self.save_ipd_patient,
        width=button_width
      )
      self.save_ipd_button.pack(side=tk.LEFT, padx=padding)

      ttk.Button(
        button_frame, 
        text="Clear Form", 
        command=self.clear_ipd_form,
        width=button_width
      ).pack(side=tk.LEFT, padx=padding)

      ttk.Button(
        button_frame, 
        text="Back", 
        command=self.create_ipd_widgets,
        width=button_width
      ).pack(side=tk.LEFT, padx=padding)

      self.ipd_print_button = ttk.Button(
        button_frame, 
        text="Print Card", 
        command=self.show_print_preview_ipd,
        width=button_width
      )
      self.ipd_print_button.pack(side=tk.LEFT, padx=padding)
      self.ipd_print_button.config(state='disabled')

      # Bind Enter key to move between fields
      for key in self.ipd_field_order:
        widget = self.ipd_field_widgets.get(key)
        if isinstance(widget, (ttk.Entry, ttk.Combobox)):
            widget.bind('<Return>', self.move_to_next_ipd_field)
        elif isinstance(widget, tk.Text):
            widget.bind('<Return>', self.move_to_next_ipd_field)

    def save_ipd_patient(self):
      mandatory_fields = {
        'first_name': 'First Name',
        'father_name': "Father's Name",
        'age': 'Age',
        'gender': 'Gender',
        'mobile_number': 'Mobile Number',
        'address': 'Address',
        'town': 'Town',
        'state': 'State',
        'medical_department': 'Medical Department',
        'police_case': 'Police Case',
        'bed_number': 'Bed Number',
        'room_number': 'Room Number',
        'admission_date': 'Admission Date'
      }
      missing_fields = []
      data = {}
      for key, label in mandatory_fields.items():
        widget = self.ipd_field_widgets[key]
        if isinstance(widget, tk.Text):
            value = widget.get("1.0", tk.END).strip()
        elif isinstance(widget, ttk.Combobox):
            value = widget.get().strip()
        elif isinstance(widget, ttk.Entry):
            value = widget.get().strip()
        elif isinstance(widget, tk.StringVar):
            value = widget.get().strip()
        else:
            value = ''
        if not value:
            missing_fields.append(label)
        data[key] = value

      for key in ['last_name', 'abha_number', 'email', 'post_office', 'discharge_date']:
        widget = self.ipd_field_widgets.get(key)
        if widget:
            if isinstance(widget, tk.Text):
                data[key] = widget.get("1.0", tk.END).strip() or None
            else:
                data[key] = widget.get().strip() or None
        else:
            data[key] = None
      if 'notes' in self.ipd_field_widgets:
        data['notes'] = self.ipd_field_widgets['notes'].get("1.0", tk.END).strip() or None
      else:
        data['notes'] = None

      if missing_fields:
        messagebox.showerror("Input Error", f"Please fill in the following required fields: {', '.join(missing_fields)}")
        return

      if not data['mobile_number'].isdigit() or len(data['mobile_number']) != 10:
        messagebox.showerror("Input Error", "Mobile number must be 10 digits.")
        return

      if data['email'] and not re.match(r"[^@]+@[^@]+\.[^@]+", data['email']):
        messagebox.showerror("Input Error", "Invalid email format.")
        return

      try:
        data['age'] = int(data['age'])
        if data['age'] < 0 or data['age'] > 150:
            raise ValueError
      except ValueError:
        messagebox.showerror("Input Error", "Age must be a valid number between 0 and 150.")
        return

      try:
        admission_date_db = datetime.datetime.strptime(data['admission_date'], "%d/%m/%Y").strftime("%Y-%m-%d")
      except Exception:
        messagebox.showerror("Input Error", "Admission date must be DD/MM/YYYY.")
        return

      discharge_date_db = None
      if data['discharge_date']:
        try:
            discharge_date_db = datetime.datetime.strptime(data['discharge_date'], "%d/%m/%Y").strftime("%Y-%m-%d")
        except Exception:
            messagebox.showerror("Input Error", "Discharge date must be DD/MM/YYYY.")
            return

      ipd_data = {
        "first_name": data['first_name'],
        "last_name": data.get('last_name'),
        "father_name": data['father_name'],
        "abha_number": data.get('abha_number'),
        "age": data['age'],
        "gender": data['gender'],
        "mobile_number": data['mobile_number'],
        "email": data.get('email'),
        "address": data['address'],
        "post_office": data.get('post_office'),
        "town": data['town'],
        "state": data['state'],
        "medical_department": data['medical_department'],
        "police_case": data['police_case'],
        "bed_number": data['bed_number'],
        "room_number": data['room_number'],
        "admission_date": admission_date_db,
        "discharge_date": discharge_date_db,
        "notes": data.get('notes')
      }

      # --- NEW LOGIC: If editing (Update), else Insert ---
      if self.last_saved_ipd_registration_number:
        reg_no = self.last_saved_ipd_registration_number
        success = update_ipd_patient(reg_no, **ipd_data)
        if success:
            messagebox.showinfo("Success", f"Patient {reg_no} updated successfully!")
            if self.ipd_print_button:
                self.ipd_print_button.config(state='normal')
        else:
            messagebox.showerror("Error", f"Failed to update IPD patient {reg_no}.")
      else:
        # New patient, generate registration number and insert
        reg_no = get_next_registration_number('ipd')
        ipd_data["registration_number"] = reg_no
        ipd_id = self.save_ipd_patient_to_db(ipd_data)
        if ipd_id:
            self.last_saved_ipd_registration_number = reg_no
            messagebox.showinfo("Success", f"Patient saved as registration number {reg_no}")
            self.ipd_field_widgets['registration_number'].config(state='normal')
            self.ipd_field_widgets['registration_number'].delete(0, tk.END)
            self.ipd_field_widgets['registration_number'].insert(0, str(reg_no))
            self.ipd_field_widgets['registration_number'].config(state='readonly')
            if self.ipd_print_button:
                self.ipd_print_button.config(state='normal')
        else:
            messagebox.showerror("Error", "Failed to register IPD patient. Check inputs or database.")

    def save_ipd_patient_to_db(self,data):
      """
      Save a full IPD patient record to IPD_Patients table.
      Expects all keys present in `data`.
      """
      required_fields = [
        "registration_number", "first_name", "father_name", "age", "gender", "mobile_number",
        "address", "town", "state", "medical_department", "police_case", "bed_number",
        "room_number", "admission_date"
      ]
      missing = [field for field in required_fields if not data.get(field)]
      if missing:
        messagebox.showerror("Input Error", f"Missing required fields for IPD patient: {', '.join(missing)}")
        return None

      conn = get_db_connection()
      if not conn:
        messagebox.showerror("Database Error", "Could not connect to database.")
        return None
      cursor = None
      try:
        cursor = conn.cursor()
        sql = """
            INSERT INTO IPD_Patients (
                registration_number, first_name, last_name, father_name, abha_number, age, gender,
                mobile_number, email, address, post_office, town, state, medical_department,
                police_case, bed_number, room_number, admission_date, discharge_date, notes, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            data.get("registration_number"),
            data.get("first_name"),
            data.get("last_name"),
            data.get("father_name"),
            data.get("abha_number"),
            data.get("age"),
            data.get("gender"),
            data.get("mobile_number"),
            data.get("email"),
            data.get("address"),
            data.get("post_office"),
            data.get("town"),
            data.get("state"),
            data.get("medical_department"),
            data.get("police_case"),
            data.get("bed_number"),
            data.get("room_number"),
            data.get("admission_date"),
            data.get("discharge_date"),
            data.get("notes"),
            self.current_username
        )
        cursor.execute(sql, values)
        conn.commit()
        ipd_id = cursor.lastrowid
        logger.info(f"Added IPD patient: {ipd_id}, Reg: {data.get('registration_number')}")
        return ipd_id
      except Exception as e:
        logger.error(f"Error saving IPD patient: {e}")
        messagebox.showerror("Database Error", f"Error saving IPD patient: {e}")
        return None
      finally:
        if cursor:
            cursor.close()
        conn.close()

    def move_to_next_ipd_field(self, event):
      widget = event.widget
      order = self.ipd_field_order
      widgets = self.ipd_field_widgets
      current_index = None
      for idx, key in enumerate(order):
        if widgets[key] == widget:
            current_index = idx
            break
      if current_index is not None and current_index + 1 < len(order):
        next_widget = widgets[order[current_index + 1]]
        next_widget.focus_set()
        if isinstance(next_widget, tk.Text):
            next_widget.mark_set("insert", "1.0")
      return "break"

    def clear_ipd_form(self):
      for key, widget in self.ipd_field_widgets.items():
        if isinstance(widget, ttk.Entry):
            widget.config(state='normal')
            widget.delete(0, tk.END)
            if key == 'registration_number':
                widget.config(state='readonly')
            if key == 'admission_date':
                widget.insert(0, datetime.date.today().strftime("%d/%m/%Y"))
        elif isinstance(widget, tk.Text):
            widget.delete("1.0", tk.END)
        elif isinstance(widget, ttk.Combobox):
            widget.set('')
            # Always enforce readonly for dropdowns after clearing
            widget.config(state='readonly')

      # Ensure gender and department comboboxes stay readonly after clearing
      self.ipd_field_widgets['gender'].config(state='readonly')
      self.ipd_field_widgets['medical_department'].config(state='readonly')
      if 'police_case' in self.ipd_field_widgets:
        self.ipd_field_widgets['police_case'].set('No')
        self.ipd_field_widgets['police_case'].config(state='readonly')

      self.last_saved_ipd_registration_number = None
      if self.ipd_print_button:
        self.ipd_print_button.config(state='disabled')
      self.save_ipd_button.config(text="Save IPD Patient")
      self.last_saved_ipd_registration_number = None  

    def show_print_preview(self):
      import tkinter as tk
      from tkinter import ttk, messagebox
      import textwrap

      data = self.get_opd_patient_by_reg_number(self.current_reg_number)
      if not data:
        messagebox.showerror("Print Error", "No OPD patient data found for the current registration number.\nPlease save or select a patient first.")
        return
      def safe(key, default=""):
        v = data.get(key, default) if data else default
        return v if v is not None else default

      a4_width_px = 793
      a4_height_px = 1122
      top_content_height = int(a4_height_px / 3)

      preview = tk.Toplevel(self.master)
      preview.title("OPD Card Print Preview")
      preview.geometry(f"{a4_width_px}x{a4_height_px}")
      preview.config(bg="white")
      preview.resizable(False, False)
      preview.grab_set()

      main_frame = tk.Frame(preview, bg="white")
      main_frame.pack(fill="both", expand=True)

      # Top 1/3rd: Actual card content
      card_frame = tk.Frame(main_frame, bg="white", height=top_content_height)
      card_frame.pack(fill="x", side="top")
      card_frame.pack_propagate(False)

      # --- Header Section ---
      tk.Label(card_frame, text="अनुसूची • 6 धर्म संख्या • 10",
             font=("Arial Unicode MS", 10), bg="white").pack(pady=(12,0))
      tk.Label(card_frame, text="श्री राम जानकी मेडिकल कॉलेज एवं अस्पताल समस्तीपुर",
             font=("Arial", 16,"bold"), bg="white").pack()
      tk.Label(card_frame, text="(OPD PATIENT CARD)",
             font=("Arial", 13, "bold"), bg="white").pack(pady=(7,0))
      ttk.Separator(card_frame, orient="horizontal").pack(fill='x', padx=10, pady=(8, 0))

      # --- Patient Info Section ---
      info_frame = tk.Frame(card_frame, bg="white")
      info_frame.pack(padx=16, pady=(10,4), anchor="nw")

      font_label = ("Arial", 11)
      font_value = ("Arial", 11, "bold")

      row = 0
      # Row 0: Registration No. | Abha No. | Date
      tk.Label(info_frame, text="Registration No.", font=font_label, bg="white").grid(row=row, column=0, sticky="w")
      tk.Label(info_frame, text=safe('registration_number'), font=font_value, bg="white").grid(row=row, column=1, sticky="w", padx=(0,18))
      tk.Label(info_frame, text="Abha No.", font=font_label, bg="white").grid(row=row, column=2, sticky="w")
      tk.Label(info_frame, text=safe('abha_number'), font=font_value, bg="white").grid(row=row, column=3, sticky="w", padx=(0,18))
      tk.Label(info_frame, text="Date", font=font_label, bg="white").grid(row=row, column=4, sticky="w")
      tk.Label(info_frame, text=safe('registration_date'), font=font_value, bg="white").grid(row=row, column=5, sticky="w")
      row += 1

      # Row 1: Patient Name | Age
      tk.Label(info_frame, text="Patient Name:-", font=font_label, bg="white").grid(row=row, column=0, sticky="w", pady=(7,0))
      tk.Label(info_frame, text=f"{safe('first_name','')} {safe('last_name','')}", font=font_value, bg="white").grid(row=row, column=1, sticky="w", pady=(7,0), padx=(0,18))
      tk.Label(info_frame, text="Age: ", font=font_label, bg="white").grid(row=row, column=2, sticky="w")
      tk.Label(info_frame, text=f"{safe('age')} M/Yrs", font=font_value, bg="white").grid(row=row, column=3, sticky="w", pady=(7,0))
      row += 1

      # Father's/Guardian/Husband Name (multi-line)
      guardian_value = safe('father_name')
      guardian_lines = textwrap.wrap(guardian_value, 35)
      tk.Label(info_frame, text="Father's/Guardian/\nHusband Name: ", font=font_label, bg="white", justify="left", anchor="nw").grid(row=row, column=0, sticky="nw", pady=(7,0))
      for idx, gline in enumerate(guardian_lines):
        tk.Label(info_frame, text=gline, font=font_value, bg="white", justify="left", wraplength=250, anchor="nw").grid(row=row+idx, column=1, sticky="nw", pady=(7,0) if idx == 0 else (0,0), padx=(0,18))
      tk.Label(info_frame, text="Gender: ", font=font_label, bg="white").grid(row=row, column=2, sticky="w")
      tk.Label(info_frame, text=safe('gender'), font=font_value, bg="white").grid(row=row, column=3, sticky="w", pady=(7,0))
      row += max(1, len(guardian_lines))

      # Address (multi-line: pushes everything down)
      address_value = " ".join([safe('address'), safe('town'), safe('state')])
      address_lines = textwrap.wrap(address_value, 45)
      tk.Label(info_frame, text="Address: ", font=font_label, bg="white").grid(row=row, column=0, sticky="nw", pady=(7,0))
      for idx, aline in enumerate(address_lines):
        tk.Label(info_frame, text=aline, font=font_value, bg="white", justify="left", wraplength=320, anchor="nw").grid(row=row+idx, column=1, sticky="nw", pady=(7,0) if idx == 0 else (0,0), padx=(0,18))
      row += len(address_lines)

      # --- Mobile and Fee: ALWAYS after last address line, aligned right ---
      tk.Label(info_frame, text="Mobile No: ", font=font_label, bg="white").grid(row=row, column=3, sticky="w", padx=(0,8), pady=(7,0))
      tk.Label(info_frame, text=safe('mobile_number'), font=font_value, bg="white").grid(row=row, column=4, sticky="w", pady=(7,0))
      tk.Label(info_frame, text="निबंधन शुल्क: ", font=font_label, bg="white").grid(row=row+1, column=3, sticky="w", padx=(0,8), pady=(0,0))
      tk.Label(info_frame, text=f"₹ {safe('registration_fee','5.00')}", font=font_value, bg="white").grid(row=row+1, column=4, sticky="w", pady=(0,0))

      # --- Thin horizontal line under info ---
      ttk.Separator(card_frame, orient="horizontal").pack(fill='x', padx=10, pady=(8,0))

      # --- Left-aligned block for Weight, BP, PR, Room No. ---
      fields_block = tk.Frame(card_frame, bg="white")
      fields_block.pack(anchor="w", padx=10, pady=(4,0))  # Tight to separator, left aligned

      labels = ["Weight :", "BP :", "PR :", "Room No. :"]
      for i, lbl in enumerate(labels):
        tk.Label(fields_block, text=lbl, font=("Arial", 9), bg="white", anchor="w", justify="left").grid(row=i, column=0, sticky="w", pady=(0,0), padx=(0,0))

      # --- Centered Print Button Only ---
      btn_frame = tk.Frame(main_frame, bg="white")
      btn_frame.pack(expand=True, fill='both')
      ttk.Button(
        btn_frame,
        text="Print",
        command=lambda: self._do_print_opd_card(data),
        width=26
      ).pack(expand=True, anchor="center", pady=20)

 
      # --- Footer Note (always at the bottom) ---
      footer_frame = tk.Frame(main_frame, bg="white")
      footer_frame.pack(side='top', fill='x', pady=(2, 5))
      ttk.Separator(footer_frame, orient="horizontal").pack(fill='x', pady=(0,1))
      tk.Label(footer_frame, text="नोट•", font=("Arial", 12, "bold"), fg="black", bg="white", anchor="w").pack(side="left", padx=(5,0))
      tk.Label(footer_frame, text="कृपया इस टिकट को हमेशा साथ लावें अन्यथा दवा नहीं मिलेगी ।",
             font=("Arial Unicode MS", 10), fg="black", bg="white", anchor="w").pack(side="left", padx=(6,0))
      
      preview.transient(self.master)
      preview.wait_window(preview)

    def _do_print_opd_card(self, data):
      from tkinter import messagebox
      try:
        if not data:
            messagebox.showerror("Print Error", "No patient data found for printing. Please save or select a patient first.")
            return
        printer_name = load_printer_choice()  # Gets the user's chosen printer or "default"
        print_opd_card_a4_fast(data, printer_name=printer_name)
        messagebox.showinfo("Print", f"Print job sent to printer: {printer_name}")
      except Exception as e:
        messagebox.showerror("Print Error", f"Printing failed: {e}")

      

    def add_medicine_options(self, medicine_tab):
      options = [
        ("Supply", "Record a supplied medicine."),
        ("Purchase", "Record a new medicine purchase."),
        ("Expiry", "Record medicine expiry."),
        ("Stock", "View medicine stock and alerts."),
     ]

      self.medicine_option_frames = {}

      button_frame = ttk.Frame(medicine_tab)
      button_frame.pack(side="top", fill="x", pady=15)

      content_frame = ttk.Frame(medicine_tab)
      content_frame.pack(side="top", fill="both", expand=True)

      def show_option(option):
        for frame in self.medicine_option_frames.values():
            frame.pack_forget()
        self.medicine_option_frames[option].pack(fill="both", expand=True, padx=20, pady=20)

      for option, desc in options:
        frame = ttk.Frame(content_frame, style='TFrame', padding=30)
        self.medicine_option_frames[option] = frame

        if option == "Supply":
            self.supply_section = SupplyMedicineSection(frame)
        elif option == "Purchase":
            self.purchase_section = PurchaseMedicineSection(frame)
        elif option == "Expiry":
            self.expiry_section = ExpiryMedicineSection(frame)
        elif option == "Stock":
            self.stock_section = StockMedicineSection(frame)

      # Optional: let supply section refresh stock section
      self.supply_section.stock_section = getattr(self, "stock_section", None)

      # Button creation (unchanged)
      for option, desc in options:
        btn = tk.Button(
            button_frame,
            text=option,
            font=("Arial", 14, "bold"),
            width=20,
            height=2,
            bg="#2196F3",
            fg="white",
            activebackground="#1976D2",
            activeforeground="white",
            relief="raised",
            bd=3,
            command=lambda opt=option: show_option(opt)
        )
        btn.pack(side="left", padx=10, pady=5, expand=True, fill="x")

      show_option(options[0][0])

    def show_print_preview_ipd(self):
      import tkinter as tk
      from tkinter import messagebox

      if not self.last_saved_ipd_registration_number:
        messagebox.showerror("Error", "No IPD patient has been saved yet. Save before printing!")
        return

      patient_data = None
      conn = get_db_connection()
      if conn:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM IPD_Patients WHERE registration_number = %s", (self.last_saved_ipd_registration_number,))
        patient_data = cur.fetchone()
        cur.close()
        conn.close()
      if not patient_data:
        messagebox.showerror("Error", "IPD patient data not found. Cannot print.")
        return

      def val(key, default=""):
        v = patient_data.get(key, default)
        return str(v) if v is not None else default

      # --- Page and margin setup for A4 ---
      PAGE_W, PAGE_H = 794, 1123    # A4 at ~96dpi, adjust for your printer/screen
      MARGIN = 36                   # About 0.5 inch
      BORDER_W, BORDER_H = PAGE_W - 2*MARGIN, PAGE_H - 2*MARGIN

      preview = tk.Toplevel(self.master)
      preview.title("IPD Bed Head Ticket Print Preview")
      preview.geometry(f"{PAGE_W}x{PAGE_H}")
      preview.config(bg="white")
      preview.resizable(False, False)
      preview.grab_set()

      # --- Draw the solid page border with Canvas for sharpness ---
      border_canvas = tk.Canvas(preview, width=PAGE_W, height=PAGE_H, bg="white", highlightthickness=0)
      border_canvas.place(x=0, y=0)
      border_canvas.create_rectangle(MARGIN, MARGIN, PAGE_W-MARGIN, PAGE_H-MARGIN, width=2)

      main_frame = tk.Frame(preview, bg="white")
      main_frame.place(x=MARGIN, y=MARGIN, width=BORDER_W, height=BORDER_H)

      # Title
      tk.Label(main_frame, text="SRI RAM JANKI MEDICAL COLLEGE & HOSPITAL", font=("Helvetica", 18, "bold"), bg="white").place(relx=0.5, y=32, anchor="n")
      tk.Label(main_frame, text="SAMASTIPUR", font=("Helvetica", 15, "bold"), bg="white").place(relx=0.5, y=62, anchor="n")
      tk.Label(main_frame, text="BED HEAD TICKET", font=("Helvetica", 15, "bold"), bg="white").place(relx=0.5, y=87, anchor="n")
      canvas_title = tk.Canvas(main_frame, width=300, height=5, bg="white", highlightthickness=0)
      canvas_title.place(relx=0.5, y=110, anchor="n")
      canvas_title.create_line(0, 2, 300, 2, width=2)

      y0 = 130
      x_left = 30
      x_right = 765
      mid = 410
      font = ("Helvetica", 11)
      field_height = 22
      value_gap = 8     # vertical gap below value text before dotted line
      line_gap = 14     # vertical gap after dotted line before next field (increase for more space)
      section_gap = 24  # extra gap before diagnosis section
      INNER_MARGIN = 16

      # Helper to draw dotted line below a widget
      def draw_dotted_line_below_widget(widget, x_start, x_end, y_offset=2, min_length=60):
         widget.update_idletasks()
         label_y = widget.winfo_y()
         label_h = widget.winfo_height()
         width = max(x_end - x_start, min_length)
         dot_canvas = tk.Canvas(main_frame, width=width, height=4, bg="white", highlightthickness=0)
         dot_canvas.place(x=x_start, y=label_y + label_h + y_offset)
         x = 0
         while x < width:
          dot_canvas.create_line(x, 2, min(x+6, width), 2, fill="#333", width=1)
          x += 10

      y = y0

      # 1. Ward & Side
      label1 = tk.Label(main_frame, text="Ward:", font=font, bg="white")
      label1.place(x=x_left, y=y)
      value1 = tk.Label(main_frame, text=val("ward"), font=font, bg="white")
      value1.place(x=x_left + 60, y=y)
      label2 = tk.Label(main_frame, text="Side:", font=font, bg="white")
      label2.place(x=mid-10, y=y)
      value2 = tk.Label(main_frame, text=val("side"), font=font, bg="white")
      value2.place(x=mid+50, y=y)
      draw_dotted_line_below_widget(value1, value1.winfo_x()+90, mid-INNER_MARGIN)
      draw_dotted_line_below_widget(value2, value2.winfo_x(), value2.winfo_x() + value2.winfo_width() + 230)
      y += field_height + value_gap + line_gap

      # 2. Year, Reg. No., Bed No.
      label1 = tk.Label(main_frame, text="Year: ", font=font, bg="white")
      label1.place(x=x_left, y=y)
      value1 = tk.Label(main_frame, text=val("admission_date")[:4], font=font, bg="white")
      value1.place(x=x_left+45, y=y)
      label2 = tk.Label(main_frame, text="Reg. No.: ", font=font, bg="white")
      label2.place(x=x_left+105, y=y)
      value2 = tk.Label(main_frame, text=val("registration_number"), font=font, bg="white")
      value2.place(x=x_left+105+100, y=y)
      label3 = tk.Label(main_frame, text="Bed No.: ", font=font, bg="white")
      label3.place(x=mid, y=y)
      value3 = tk.Label(main_frame, text=val("bed_number"), font=font, bg="white")
      value3.place(x=mid+80, y=y)
      draw_dotted_line_below_widget(value1, value1.winfo_x()+70, x_left+95 - INNER_MARGIN)
      draw_dotted_line_below_widget(value2, value2.winfo_x()-30, mid- INNER_MARGIN)
      draw_dotted_line_below_widget(value3, value3.winfo_x(), value3.winfo_x() + value3.winfo_width() + 180)
      y += field_height + value_gap + line_gap

      # 3. Name, Age, Sex, Religion
      label1 = tk.Label(main_frame, text="Name: ", font=font, bg="white")
      label1.place(x=x_left, y=y)
      full_name = f"{val('first_name')} {val('last_name')}"
      value1 = tk.Label(main_frame, text=full_name, font=font, bg="white")
      value1.place(x=x_left+52, y=y)
      label2 = tk.Label(main_frame, text="Age: ", font=font, bg="white")
      label2.place(x=x_left+250, y=y)
      value2 = tk.Label(main_frame, text=val("age"), font=font, bg="white")
      value2.place(x=x_left+250+30, y=y)
      label3 = tk.Label(main_frame, text="Sex: ", font=font, bg="white")
      label3.place(x=x_left+345, y=y)
      value3 = tk.Label(main_frame, text=val("gender"), font=font, bg="white")
      value3.place(x=x_left+350+30, y=y)
      label4 = tk.Label(main_frame, text="Religion: ", font=font, bg="white")
      label4.place(x=x_left+450, y=y)
      value4 = tk.Label(main_frame, text=val("religion"), font=font, bg="white")
      value4.place(x=x_left+450+80, y=y)
      draw_dotted_line_below_widget(value1, value1.winfo_x()+90, x_left+250-INNER_MARGIN)
      draw_dotted_line_below_widget(value2, value2.winfo_x(), x_left+240-INNER_MARGIN)
      draw_dotted_line_below_widget(value3, value3.winfo_x(), x_left+350- INNER_MARGIN)
      draw_dotted_line_below_widget(value4, value4.winfo_x(), value4.winfo_x() + value4.winfo_width() + 130)
      y += field_height + value_gap + line_gap

      # 4. Father's/Husband's Name
      label1 = tk.Label(main_frame, text="Father’s / Husband’s Name: ", font=font, bg="white")
      label1.place(x=x_left, y=y)
      value1 = tk.Label(main_frame, text=val("father_name"), font=font, bg="white")
      value1.place(x=x_left+200, y=y)
      draw_dotted_line_below_widget(value1, value1.winfo_x()+220, value1.winfo_x() + value1.winfo_width() + 700)
      y += field_height + value_gap + line_gap

      # 5. Mother's Name
      label1 = tk.Label(main_frame, text="Mother’s Name: ", font=font, bg="white")
      label1.place(x=x_left, y=y)
      value1 = tk.Label(main_frame, text=val("mother_name"), font=font, bg="white")
      value1.place(x=x_left+120, y=y)
      draw_dotted_line_below_widget(value1, value1.winfo_x()+140, value1.winfo_x() + value1.winfo_width() + 700)
      y += field_height + value_gap + line_gap

      # 6. Village/Mohalla, P.O.
      label1 = tk.Label(main_frame, text="Village/Mohalla: ", font=font, bg="white")
      label1.place(x=x_left, y=y)
      value1 = tk.Label(main_frame, text=val("address"), font=font, bg="white")
      value1.place(x=x_left+135, y=y)
      label2 = tk.Label(main_frame, text="P.O.: ", font=font, bg="white")
      label2.place(x=x_left+280, y=y)
      value2 = tk.Label(main_frame, text=val("post_office"), font=font, bg="white")
      value2.place(x=x_left+280+45, y=y)
      draw_dotted_line_below_widget(value1, value1.winfo_x()+140, x_left+280- INNER_MARGIN)
      draw_dotted_line_below_widget(value2, value2.winfo_x(), value2.winfo_x() + value2.winfo_width() + 300)
      y += field_height + value_gap + line_gap

      # 7. P.S., Distt.
      label1 = tk.Label(main_frame, text="P.S.: ", font=font, bg="white")
      label1.place(x=x_left, y=y)
      value1 = tk.Label(main_frame, text=val("ps"), font=font, bg="white")
      value1.place(x=x_left+50, y=y)
      label2 = tk.Label(main_frame, text="Distt.: ", font=font, bg="white")
      label2.place(x=x_left+200, y=y)
      value2 = tk.Label(main_frame, text=val("town"), font=font, bg="white")
      value2.place(x=x_left+200+45, y=y)
      draw_dotted_line_below_widget(value1, value1.winfo_x()+80, x_left+200- INNER_MARGIN)
      draw_dotted_line_below_widget(value2, value2.winfo_x(), value2.winfo_x() + value2.winfo_width() + 350)
      y += field_height + value_gap + line_gap

      # 8. Date & Time of Admission, Discharge
      label1 = tk.Label(main_frame, text="Date & Time of Admission: ", font=font, bg="white")
      label1.place(x=x_left, y=y)
      value1 = tk.Label(main_frame, text=val("admission_date"), font=font, bg="white")
      value1.place(x=x_left+200, y=y)
      label2 = tk.Label(main_frame, text="Date & Time of Discharge: ", font=font, bg="white")
      label2.place(x=mid, y=y)
      value2 = tk.Label(main_frame, text=val("discharge_date"), font=font, bg="white")
      value2.place(x=mid+190, y=y)
      draw_dotted_line_below_widget(value1, value1.winfo_x()+230, mid-INNER_MARGIN)
      draw_dotted_line_below_widget(value2, value2.winfo_x(), value2.winfo_x() + value2.winfo_width() + 20)
      y += field_height + value_gap + line_gap

      # 9. Result & Advice
      label1 = tk.Label(main_frame, text="Result & Advice: ", font=font, bg="white")
      label1.place(x=x_left, y=y)
      value1 = tk.Label(main_frame, text=val("notes"), font=font, bg="white")
      value1.place(x=x_left+120, y=y)
      draw_dotted_line_below_widget(value1, value1.winfo_x()+150, value1.winfo_x() + value1.winfo_width() + 700)
      y += field_height + value_gap + section_gap

      diag_font = ("Helvetica", 11, "bold")
      tk.Label(main_frame, text="Diagnosis (a) Provisional", font=diag_font, bg="white").place(x=x_left, y=y)
      tk.Label(main_frame, text=val("diagnosis_provisional"), font=font, bg="white").place(x=x_left+180, y=y)
      y += 18
      tk.Label(main_frame, text="(b) Final", font=diag_font, bg="white").place(x=x_left+60, y=y)
      tk.Label(main_frame, text=val("diagnosis_final"), font=font, bg="white").place(x=x_left+180, y=y)
      y += 18
      tk.Label(main_frame, text="(c) ICD X", font=diag_font, bg="white").place(x=x_left+60, y=y)
      tk.Label(main_frame, text=val("diagnosis_icdx"), font=font, bg="white").place(x=x_left+180, y=y)
      y += 30

      # --- Clinical Notes Box: Only one rectangle, one horizontal line under headers ---
      table_top = y
      table_left = x_left
      table_width = x_right - x_left - 4*INNER_MARGIN
      table_height = 230

      # Header positions (adjust as needed for alignment)
      col_date = 0
      col_notes = 130
      col_advice = 420

      table_canvas = tk.Canvas(main_frame, width=table_width, height=table_height, bg="white", highlightthickness=0)
      table_canvas.place(x=table_left, y=table_top)

      # Draw the single outer border
      table_canvas.create_rectangle(0, 0, table_width, table_height, width=2)

      # Draw the header line
      table_canvas.create_line(0, 32, table_width, 32, width=2)

      # Draw vertical column lines (from header line to bottom, not above)
      table_canvas.create_line(col_notes, 0, col_notes, table_height, width=2)
      table_canvas.create_line(col_advice, 0, col_advice, table_height, width=2)

      # Draw headers
      table_font = ("Helvetica", 12, "bold")
      table_canvas.create_text(8, 16, text="Date", font=table_font, anchor="w")
      table_canvas.create_text(col_notes+8, 16, text="Clinical Notes", font=table_font, anchor="w")
      table_canvas.create_text(col_advice+8, 16, text="Advice", font=table_font, anchor="w")

      def do_print():
        from dot_matrix_print_utils import print_ipd_bed_head_ticket
        print_data = {
            "ward": val("ward"),
            "side": val("side"),
            "year": val("admission_date")[:4],
            "registration_number": val("registration_number"),
            "bed_number": val("bed_number"),
            "name": f"{val('first_name')} {val('last_name')}",
            "age": val("age"),
            "sex": val("gender"),
            "religion": val("religion"),
            "father_name": val("father_name"),
            "mother_name": val("mother_name"),
            "village": val("address"),
            "po": val("post_office"),
            "ps": val("ps"),
            "distt": val("town"),
            "admission_datetime": val("admission_date"),
            "discharge_datetime": val("discharge_date"),
            "result_advice": val("notes"),
            "diagnosis_provisional": val("diagnosis_provisional"),
            "diagnosis_final": val("diagnosis_final"),
            "diagnosis_icdx": val("diagnosis_icdx"),
            "clinical_notes": ""
        }
        print_ipd_bed_head_ticket(print_data)
        messagebox.showinfo("Print", "Print job sent!")

      btnf = tk.Frame(main_frame, bg="white")
      btnf.place(relx=0.5, y=table_top+table_height+20, anchor="n")
      tk.Button(btnf, text="Print", font=("Arial", 12, "bold"), command=do_print, width=14).pack()

      preview.transient(self.master)
      preview.wait_window(preview)

class UserManagementWindow:
    def __init__(self, parent):
        self.window = tk.Toplevel(parent)
        self.window.title("User Management")
        self.window.state("zoomed")  # Open as full window
        self.window.minsize(800, 600)
        
        # Initialize variables
        self.selected_user = None
        self.all_tabs = ['Reception', 'OPD', 'IPD', 'Medicine', 'Reporting', 'View/Search']
        
        # Style configuration
        style = ttk.Style()
        style.configure('User.TFrame', background='#e0f2f7')
        
        # Main container
        main_frame = ttk.Frame(self.window, style='User.TFrame', padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left side - User List
        left_frame = ttk.Frame(main_frame, style='User.TFrame')
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # User list with only essential columns
        columns = ("username", "password", "date_created", "role")
        self.user_tree = ttk.Treeview(left_frame, columns=columns, show="headings", height=20)
        
        # Configure column headings
        self.user_tree.heading("username", text="Username")
        self.user_tree.heading("password", text="Password")
        self.user_tree.heading("date_created", text="Date Created")
        self.user_tree.heading("role", text="Role")
        
        # Configure column widths
        self.user_tree.column("username", width=150)
        self.user_tree.column("password", width=150)
        self.user_tree.column("date_created", width=150)
        self.user_tree.column("role", width=100)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.user_tree.yview)
        self.user_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack the tree and scrollbar
        self.user_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind selection event
        self.user_tree.bind('<<TreeviewSelect>>', self.on_user_select)
        
        # Right side - User Details
        right_frame = ttk.Frame(main_frame, style='User.TFrame')
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 0))
        
        # User Details Form
        ttk.Label(right_frame, text="User Details", font=('Arial', 12, 'bold')).pack(pady=(0, 10))
        
        # Username
        ttk.Label(right_frame, text="Username:").pack(anchor='w')
        self.username_var = tk.StringVar()
        self.username_entry = ttk.Entry(right_frame, textvariable=self.username_var, width=30)
        self.username_entry.pack(fill=tk.X, pady=(0, 10))
        
        # Password
        ttk.Label(right_frame, text="Password:").pack(anchor='w')
        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(right_frame, textvariable=self.password_var, width=30)
        self.password_entry.pack(fill=tk.X, pady=(0, 10))
        
        # Role
        ttk.Label(right_frame, text="Role:").pack(anchor='w')
        self.role_var = tk.StringVar(value='user')
        role_frame = ttk.Frame(right_frame)
        role_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Radiobutton(role_frame, text="User", variable=self.role_var, value="user").pack(side=tk.LEFT)
        ttk.Radiobutton(role_frame, text="Admin", variable=self.role_var, value="admin").pack(side=tk.LEFT)
        
        # Tab Permissions
        ttk.Label(right_frame, text="Tab Permissions:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        self.tab_vars = {}
        for tab in self.all_tabs:
            var = tk.BooleanVar()
            self.tab_vars[tab] = var
            ttk.Checkbutton(right_frame, text=tab, variable=var).pack(anchor='w')
        
        # Buttons
        button_frame = ttk.Frame(right_frame, style='User.TFrame')
        button_frame.pack(fill=tk.X, pady=20)
        
        self.add_button = ttk.Button(button_frame, text="Add User", command=self.add_user)
        self.add_button.pack(side=tk.LEFT, padx=5)
        
        self.update_button = ttk.Button(button_frame, text="Update User", command=self.update_user)
        self.update_button.pack(side=tk.LEFT, padx=5)
        self.update_button.config(state='disabled')  # Initially disabled
        
        self.delete_button = ttk.Button(button_frame, text="Delete User", command=self.delete_user)
        self.delete_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Clear Form", command=self.clear_form).pack(side=tk.LEFT, padx=5)
        
        # Load initial data
        self.refresh_user_list()
    
    def refresh_user_list(self):
        # Clear existing items
        for item in self.user_tree.get_children():
            self.user_tree.delete(item)
        
        # Get users from database
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute("SELECT username, plain_password, created_at, role FROM users")
                users = cursor.fetchall()
                
                for user in users:
                    # Format the date to show only date and time (no seconds)
                    created_at = user['created_at'].strftime("%Y-%m-%d %H:%M") if user['created_at'] else ""
                    
                    self.user_tree.insert("", tk.END, values=(
                        user['username'],
                        user['plain_password'],
                        created_at,
                        user['role']
                    ))
            finally:
                cursor.close()
                conn.close()
    
    def on_user_select(self, event):
        selected_items = self.user_tree.selection()
        if not selected_items:
            self.clear_form()
            self.update_button.config(state='disabled')
            return
        
        # Get the selected user's data
        item = selected_items[0]
        user_data = self.user_tree.item(item)['values']
        username = user_data[0]
        
        # Get full user details including tab permissions
        user = get_user_by_username(username)
        if user:
            self.selected_user = username
            self.username_var.set(user['username'])
            self.password_var.set(user['plain_password'])
            self.role_var.set(user['role'])
            
            # Set tab permissions
            allowed_sections = user.get('sections_allowed', '').split(',') if user.get('sections_allowed') else []
            for tab, var in self.tab_vars.items():
                var.set(tab in allowed_sections)
            
            self.update_button.config(state='normal')
        
    def add_user(self):
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()
        role = self.role_var.get()
        
        if not username or not password:
            messagebox.showerror("Error", "Username and password are required!")
            return
        
        # Get selected tabs
        selected_tabs = [tab for tab, var in self.tab_vars.items() if var.get()]
        
        # Add user to database
        success, message = add_user(username, password, role)
        if success:
            # Update tab permissions
            update_user_sections(username, selected_tabs)
            messagebox.showinfo("Success", "User added successfully!")
            self.refresh_user_list()
            self.clear_form()
        else:
            messagebox.showerror("Error", message)
    
    def update_user(self):
        if not self.selected_user:
            messagebox.showerror("Error", "No user selected!")
            return
        
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()
        role = self.role_var.get()
        
        if not username or not password:
            messagebox.showerror("Error", "Username and password are required!")
            return
        
        # Get selected tabs
        selected_tabs = [tab for tab, var in self.tab_vars.items() if var.get()]
        
        # Update user in database
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                import bcrypt
                hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                cursor.execute("""
                    UPDATE users 
                    SET password_hash = %s, plain_password = %s, role = %s 
                    WHERE username = %s
                """, (hashed_password, password, role, username))
                conn.commit()
                
                # Update tab permissions
                update_user_sections(username, selected_tabs)
                
                messagebox.showinfo("Success", "User updated successfully!")
                self.refresh_user_list()
                self.clear_form()
            except Exception as e:
                conn.rollback()
                messagebox.showerror("Error", f"Failed to update user: {str(e)}")
            finally:
                cursor.close()
                conn.close()
    
    def delete_user(self):
        selected_items = self.user_tree.selection()
        if not selected_items:
            messagebox.showerror("Error", "Please select a user to delete!")
            return
        
        username = self.user_tree.item(selected_items[0])['values'][0]
        
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete user '{username}'?"):
            success, message = delete_user(username)
            if success:
                messagebox.showinfo("Success", "User deleted successfully!")
                self.refresh_user_list()
                self.clear_form()
            else:
                messagebox.showerror("Error", message)
    
    def clear_form(self):
        self.selected_user = None
        self.username_var.set("")
        self.password_var.set("")
        self.role_var.set("user")
        for var in self.tab_vars.values():
            var.set(False)
        self.update_button.config(state='disabled')

class SupplyMedicineSection:
    def __init__(self, parent, stock_section=None):
        self.stock_section = stock_section

        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        # --- Supply Form ---
        form = ttk.LabelFrame(frame, text="Record Medicine Supply (Batch/Expiry Aware)")
        form.pack(fill="x", pady=10)

        self.medicine_var = tk.StringVar()
        self.dept_var = tk.StringVar()
        self.qty_var = tk.StringVar()
        self.date_var = tk.StringVar(value=datetime.datetime.now().strftime('%d/%m/%Y'))
        self.batch_var = tk.StringVar()  # For manual batch selection

        ttk.Label(form, text="Medicine Name:").grid(row=0, column=0, padx=4, pady=3, sticky="e")
        self.medicine_entry = ttk.Entry(form, textvariable=self.medicine_var, width=25)
        self.medicine_entry.grid(row=0, column=1, padx=4, pady=3)

        ttk.Label(form, text="Department:").grid(row=1, column=0, padx=4, pady=3, sticky="e")
        dept_choices = ["Emergency", "OPD", "IPD", "ICU", "Pharmacy", "Lab", "Other"]
        self.dept_combo = ttk.Combobox(form, textvariable=self.dept_var, values=dept_choices, width=22, state="readonly")
        self.dept_combo.grid(row=1, column=1, padx=4, pady=3)

        ttk.Label(form, text="Quantity:").grid(row=2, column=0, padx=4, pady=3, sticky="e")
        self.qty_entry = ttk.Entry(form, textvariable=self.qty_var, width=25)
        self.qty_entry.grid(row=2, column=1, padx=4, pady=3)

        ttk.Label(form, text="Date:").grid(row=3, column=0, padx=4, pady=3, sticky="e")
        self.date_entry = ttk.Entry(form, textvariable=self.date_var, width=25)
        self.date_entry.grid(row=3, column=1, padx=4, pady=3)

        # --- Batch selection ---
        ttk.Label(form, text="Batch (Expiry):").grid(row=4, column=0, padx=4, pady=3, sticky="e")
        self.batch_combo = ttk.Combobox(form, textvariable=self.batch_var, width=22, state="readonly")
        self.batch_combo.grid(row=4, column=1, padx=4, pady=3)

        # Bind events after creating widgets
        self.batch_combo.bind("<Button-1>", self.update_batch_list)
        self.medicine_entry.bind("<FocusOut>", self.update_batch_list)

        ttk.Button(form, text="Record Supply (FEFO)", command=self.record_supply_fefo).grid(row=5, column=0, pady=8)
        ttk.Button(form, text="Record Supply (Select Batch)", command=self.record_supply_selected_batch).grid(row=5, column=1, pady=8)

        # --- Supply Records Table ---
        ttk.Label(frame, text="Recent Supply Records", font=("Arial", 13, "bold")).pack(anchor="w", pady=(15, 5))
        columns = ("Medicine", "Department", "Quantity", "Date", "Batch ID", "Expiry", "Days Left")
        self.table = ttk.Treeview(frame, columns=columns, show="headings", height=10)
        for col in columns:
            self.table.heading(col, text=col, anchor="center")
            self.table.column(col, width=100, anchor="center")
        self.table.pack(fill="x", pady=3)

        # Row tag colors
        self.table.tag_configure('red', background='#FFCDD2', foreground='red')    # <= 15 days
        self.table.tag_configure('blue', background='#BBDEFB', foreground='blue')  # <= 30 days
        self.table.tag_configure('black', background='white', foreground='black')  # > 30 days
        self.table.tag_configure('expired', background='#B0BEC5', foreground='#616161') # already expired

        self.refresh_table_from_db()

    def record_supply_fefo(self):
        name = self.medicine_var.get().strip()
        dept = self.dept_var.get().strip()
        qty = self.qty_var.get().strip()
        date = self.date_var.get().strip()

        if not (name and dept and qty and date):
            messagebox.showerror("Input Error", "All fields are required.")
            return
        if not qty.isdigit():
            messagebox.showerror("Input Error", "Quantity must be a positive integer.")
            return

        supply_qty = int(qty)
        current_stock = get_current_stock(name)
        if current_stock is None:
            messagebox.showerror("Stock Error", f"Medicine '{name}' not found in database.")
            return
        if current_stock <= 0:
            messagebox.showerror("Stock Error", f"Medicine '{name}' not available.")
            return
        if supply_qty > current_stock:
            messagebox.showerror("Stock Error", f"Only {current_stock} units available.")
            return

        try:
            supply_date_db = datetime.datetime.strptime(date, "%d/%m/%Y").strftime("%Y-%m-%d")
        except Exception:
            messagebox.showerror("Input Error", "Date must be in DD/MM/YYYY format.")
            return

        # FEFO: pick the batch with earliest expiry and available stock
        batches = get_batchwise_stock(name)
        batches = sorted(batches, key=lambda b: b[2])  # Sort by expiry date
        remaining = supply_qty
        supplied = False

        for batch in batches:
            batch_id, supplier, expiry_date, purchased_qty, supplied_qty, stock_left = batch
            if stock_left <= 0:
                continue
            to_supply = min(stock_left, remaining)
            if to_supply <= 0:
                continue
            result = add_medicine_supply(
                medicine_name=name,
                supply_date=supply_date_db,
                quantity=to_supply,
                department=dept,
                purchase_id=batch_id
            )
            if result:
                supplied = True
                remaining -= to_supply
                if remaining <= 0:
                    break

        if supplied and remaining == 0:
            messagebox.showinfo("Success", f"Supplied {supply_qty} units of '{name}' using FEFO.")
            self.refresh_table_from_db()
            self.medicine_var.set("")
            self.dept_var.set("")
            self.qty_var.set("")
            self.date_var.set(datetime.datetime.now().strftime('%d/%m/%Y'))
            self.batch_var.set("")
            if self.stock_section:
                self.stock_section.refresh_table_from_db()
        else:
            messagebox.showerror("Error", "Failed to record supply. Not enough stock or database error.")

    def update_batch_list(self, event=None):
        """
        Update the batch_combo dropdown with batches for the selected medicine.
        """
        name = self.medicine_var.get().strip()
        if not name:
            self.batch_combo['values'] = []
            self.batch_var.set("")
            return
        batches = get_batchwise_stock(name)
        batch_display = []
        for batch in batches:
            # batch: (batch_id, supplier, expiry_date, purchased_qty, supplied_qty, stock_left)
            expiry_str = batch[2].strftime("%d/%m/%Y") if hasattr(batch[2], "strftime") else str(batch[2])
            display = f"Batch #{batch[0]} | Exp: {expiry_str} | Qty: {batch[5]}"
            batch_display.append(display)
        self.batch_combo['values'] = batch_display
        if batch_display:
            self.batch_combo.current(0)
        else:
            self.batch_var.set("")

    def record_supply_selected_batch(self):
        name = self.medicine_var.get().strip()
        dept = self.dept_var.get().strip()
        qty = self.qty_var.get().strip()
        date = self.date_var.get().strip()
        batch_str = self.batch_var.get().strip()

        if not (name and dept and qty and date and batch_str):
            messagebox.showerror("Input Error", "All fields and batch selection are required.")
            return
        if not qty.isdigit():
            messagebox.showerror("Input Error", "Quantity must be a positive integer.")
            return

        try:
            batch_id = int(batch_str.split("#")[1].split("|")[0].strip())
        except Exception:
            messagebox.showerror("Input Error", "Invalid batch selection.")
            return

        supply_qty = int(qty)
        batches = get_batchwise_stock(name)
        batch = next((b for b in batches if b[0] == batch_id), None)
        if not batch:
            messagebox.showerror("Error", "Selected batch not found or out of stock.")
            return
        if batch[5] < supply_qty:
            messagebox.showerror("Stock Error", f"Only {batch[5]} units available in selected batch.")
            return

        try:
            supply_date_db = datetime.datetime.strptime(date, "%d/%m/%Y").strftime("%Y-%m-%d")
        except Exception:
            messagebox.showerror("Input Error", "Date must be in DD/MM/YYYY format.")
            return

        success = add_medicine_supply(
            medicine_name=name,
            supply_date=supply_date_db,
            quantity=supply_qty,
            department=dept,
            purchase_id=batch_id
        )
        if success:
            messagebox.showinfo("Success", f"Supplied {supply_qty} units from Batch #{batch_id}.")
            self.refresh_table_from_db()
            self.medicine_var.set("")
            self.dept_var.set("")
            self.qty_var.set("")
            self.date_var.set(datetime.datetime.now().strftime('%d/%m/%Y'))
            self.batch_var.set("")
            if self.stock_section:
                self.stock_section.refresh_table_from_db()
        else:
            messagebox.showerror("Error", "Failed to record supply. Check your database or inputs.")

    def refresh_table_from_db(self):
        for item in self.table.get_children():
            self.table.delete(item)
        conn = get_db_connection()
        if conn:
            cursor = None
            try:
                cursor = conn.cursor()
                query = """
                    SELECT m.name, s.department, s.quantity, s.supply_date, s.purchase_id, p.expiry_date
                    FROM medicine_supplies s
                    JOIN medicines m ON s.medicine_id = m.id
                    LEFT JOIN medicine_purchases p ON s.purchase_id = p.id
                    ORDER BY s.supply_date DESC, s.id DESC
                    LIMIT 40
                """
                cursor.execute(query)
                rows = cursor.fetchall()
                today = datetime.date.today()
                for rec in rows:
                    name, department, quantity, date, batch_id, expiry = rec
                    if expiry:
                        exp_date = expiry if isinstance(expiry, datetime.date) else datetime.datetime.strptime(str(expiry), "%Y/%m/%d").date()
                        days_left = (exp_date - today).days
                        expiry_str = exp_date.strftime("%d/%m/%Y")
                    else:
                        days_left = "?"
                        expiry_str = ""
                    # Color settings
                    if isinstance(days_left, int):
                        if days_left < 0:
                            tag = 'expired'
                        elif days_left <= 15:
                            tag = 'red'
                        elif days_left <= 30:
                            tag = 'blue'
                        else:
                            tag = 'black'
                    else:
                        tag = 'black'
                    self.table.insert(
                        "", "end",
                        values=(name, department, quantity, date.strftime("%d/%m/%Y"), batch_id or "", expiry_str, days_left),
                        tags=(tag,)
                    )
            finally:
                if cursor:
                    cursor.close()
                conn.close()
    
    

class PurchaseMedicineSection:
    def __init__(self, parent):
        self.records = []

        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        # --- Purchase Form ---
        form = ttk.LabelFrame(frame, text="Record Medicine Purchase")
        form.pack(fill="x", pady=10)

        self.medicine_var = tk.StringVar()
        self.supplier_var = tk.StringVar()
        self.qty_var = tk.StringVar()
        self.date_var = tk.StringVar(value=datetime.datetime.now().strftime('%d/%m/%Y'))
        self.expiry_var = tk.StringVar()
        self.batch_number_var = tk.StringVar()

        ttk.Label(form, text="Medicine Name:").grid(row=0, column=0, padx=4, pady=3, sticky="e")
        ttk.Entry(form, textvariable=self.medicine_var, width=25).grid(row=0, column=1, padx=4, pady=3)

        ttk.Label(form, text="Supplier Name:").grid(row=1, column=0, padx=4, pady=3, sticky="e")
        ttk.Entry(form, textvariable=self.supplier_var, width=25).grid(row=1, column=1, padx=4, pady=3)

        ttk.Label(form, text="Quantity:").grid(row=2, column=0, padx=4, pady=3, sticky="e")
        ttk.Entry(form, textvariable=self.qty_var, width=25).grid(row=2, column=1, padx=4, pady=3)

        ttk.Label(form, text="Date:").grid(row=3, column=0, padx=4, pady=3, sticky="e")
        ttk.Entry(form, textvariable=self.date_var, width=25).grid(row=3, column=1, padx=4, pady=3)

        ttk.Label(form, text="Expiry Date (dd/mm/yy):").grid(row=4, column=0, padx=4, pady=3, sticky="e")
        ttk.Entry(form, textvariable=self.expiry_var, width=25).grid(row=4, column=1, padx=4, pady=3)

        ttk.Label(form, text="Batch Number:").grid(row=5, column=0, padx=4, pady=3, sticky="e")
        ttk.Entry(form, textvariable=self.batch_number_var, width=25).grid(row=5, column=1, padx=4, pady=3)

        ttk.Button(form, text="Record Purchase", command=self.record_purchase).grid(row=6, column=0, columnspan=2, pady=8)

        # --- Purchase Records Table ---
        ttk.Label(frame, text="Purchase Records", font=("Arial", 13, "bold")).pack(anchor="w", pady=(15, 5))
        columns = ("Medicine", "Supplier", "Quantity", "Date", "Expiry Date", "Batch Number")
        self.table = ttk.Treeview(frame, columns=columns, show="headings", height=7)
        style = ttk.Style()
        style.configure("mystyle.Treeview.Heading", font=('Arial', 11, 'bold'))
        style.configure("mystyle.Treeview", font=('Arial', 11), rowheight=26)
        self.table.configure(style="mystyle.Treeview")

        # Expanded width, but center alignment for all columns
        self.table.heading("Medicine", text="Medicine", anchor="center")
        self.table.column("Medicine", anchor="center", width=200)
        self.table.heading("Supplier", text="Supplier", anchor="center")
        self.table.column("Supplier", anchor="center", width=200)
        self.table.heading("Quantity", text="Quantity", anchor="center")
        self.table.column("Quantity", anchor="center", width=100)
        self.table.heading("Date", text="Date", anchor="center")
        self.table.column("Date", anchor="center", width=140)
        self.table.heading("Expiry Date", text="Expiry Date", anchor="center")
        self.table.column("Expiry Date", anchor="center", width=140)
        self.table.heading("Batch Number", text="Batch Number", anchor="center")
        self.table.column("Batch Number", anchor="center", width=120)
        self.table.pack(fill="x", pady=3)
        self.table["show"] = "headings"

        self.refresh_table_from_db()

    def record_purchase(self):
        name = self.medicine_var.get().strip()
        supplier = self.supplier_var.get().strip()
        qty = self.qty_var.get().strip()
        date = self.date_var.get().strip()
        expiry = self.expiry_var.get().strip()
        batch_number = self.batch_number_var.get().strip()

        # Validate inputs
        if not (name and supplier and qty and date and expiry and batch_number):
            messagebox.showerror("Input Error", "All fields are required.")
            return
        if not qty.isdigit():
            messagebox.showerror("Input Error", "Quantity must be a positive integer.")
            return

        # Validate date formats
        try:
            purchase_date_db = datetime.datetime.strptime(date, "%d/%m/%Y").strftime("%Y-%m-%d")
            expiry_date_db = datetime.datetime.strptime(expiry, "%d/%m/%Y").strftime("%Y-%m-%d")
        except Exception:
            messagebox.showerror("Input Error", "Dates must be in DD/MM/YYYY format.")
            return

        # Call DB function and show message
        success = add_medicine_purchase(
            medicine_name=name,
            supplier=supplier,
            quantity=int(qty),
            purchase_date=purchase_date_db,
            expiry_date=expiry_date_db,
            unit_price=None,
            batch_number=batch_number
        )
        if success:
            messagebox.showinfo("Success", "Medicine purchase recorded successfully.")
            self.refresh_table_from_db()
            self.medicine_var.set("")
            self.supplier_var.set("")
            self.qty_var.set("")
            self.date_var.set(datetime.datetime.now().strftime('%d/%m/%Y'))
            self.expiry_var.set("")
            self.batch_number_var.set("")
        else:
            messagebox.showerror("Error", "Failed to record medicine purchase.")

    def refresh_table_from_db(self):
        # Fetch from DB, not self.records!
        conn = get_db_connection()
        if conn:
            cursor = None
            try:
                cursor = conn.cursor()
                query = """
                    SELECT m.name, p.supplier, p.quantity, p.purchase_date, p.expiry_date, p.batch_number
                    FROM medicine_purchases p
                    JOIN medicines m ON p.medicine_id = m.id
                    ORDER BY p.purchase_date DESC
                """
                cursor.execute(query)
                rows = cursor.fetchall()
                # Clear table
                for item in self.table.get_children():
                    self.table.delete(item)
                # Insert all rows
                for rec in rows:
                    self.table.insert(
                        "", "end",
                        values=(
                            rec[0],
                            rec[1],
                            rec[2],
                            rec[3].strftime("%d/%m/%Y") if rec[3] else "",
                            rec[4].strftime("%d/%m/%Y") if rec[4] else "",
                            rec[5] or ""
                        )
                    )
            finally:
                if cursor:
                    cursor.close()
                conn.close()


class ExpiryMedicineSection:
    def __init__(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Medicine Expiry Table", font=("Arial", 13, "bold")).pack(anchor="w", pady=(15, 5))

        # --- Search bar ---
        search_frame = ttk.Frame(frame)
        search_frame.pack(fill="x", pady=5)
        self.search_var = tk.StringVar()
        ttk.Label(search_frame, text="Search Medicine:").pack(side="left", padx=(0, 5))
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=25)
        search_entry.pack(side="left")
        search_entry.bind("<Return>", lambda e: self.refresh_table_from_db())
        ttk.Button(search_frame, text="Search", command=self.refresh_table_from_db).pack(side="left", padx=(5, 5))
        ttk.Button(search_frame, text="Show All", command=self.clear_search).pack(side="left")

        # --- Expiry Table ---
        columns = ("Medicine", "Supplier", "Expiry Date", "Days Left")
        self.table = ttk.Treeview(frame, columns=columns, show="headings", height=15)
        for col in columns:
            self.table.heading(col, text=col, anchor="center")
            self.table.column(col, width=120, anchor="center")
        self.table.pack(fill="x", pady=3)

        # Row tag colors
        self.table.tag_configure('red', background='#FFCDD2', foreground='red')    # <= 15 days
        self.table.tag_configure('blue', background='#BBDEFB', foreground='blue')  # <= 30 days
        self.table.tag_configure('black', background='white', foreground='black')  # > 30 days
        self.table.tag_configure('expired', background='#B0BEC5', foreground='#616161') # already expired

        self.refresh_table_from_db()

    def clear_search(self):
        self.search_var.set("")
        self.refresh_table_from_db()

    def refresh_table_from_db(self):
        for item in self.table.get_children():
            self.table.delete(item)

        today = datetime.datetime.now().date()
        filter_text = self.search_var.get().strip().lower()
        conn = get_db_connection()
        if conn:
            cursor = None
            try:
                cursor = conn.cursor()
                # Query for medicines with in-stock quantity >= 1 and expiry date
                query = """
                    SELECT m.name, p.supplier, p.expiry_date, p.medicine_id,
                        (SELECT COALESCE(SUM(quantity),0) FROM medicine_purchases WHERE medicine_id = p.medicine_id) AS purchased,
                        (SELECT COALESCE(SUM(quantity),0) FROM medicine_supplies WHERE medicine_id = p.medicine_id) AS supplied
                    FROM medicine_purchases p
                    JOIN medicines m ON p.medicine_id = m.id
                    WHERE p.expiry_date IS NOT NULL
                    {}
                    GROUP BY m.name, p.supplier, p.expiry_date, p.medicine_id
                    ORDER BY p.expiry_date ASC
                """.format("AND LOWER(m.name) LIKE %s" if filter_text else "")
                params = (f"%{filter_text}%",) if filter_text else ()
                cursor.execute(query, params)
                rows = cursor.fetchall()
                for rec in rows:
                    name, supplier, expiry, med_id, purchased, supplied = rec
                    stock = (purchased or 0) - (supplied or 0)
                    if stock >= 1 and expiry:
                        exp_date = expiry if isinstance(expiry, datetime.date) else datetime.datetime.strptime(str(expiry), "%d/%m/%Y").date()
                        days_left = (exp_date - today).days
                        expiry_str = exp_date.strftime("%d/%m/%Y")
                        # Color settings
                        if days_left < 0:
                            tag = 'expired'
                        elif days_left <= 15:
                            tag = 'red'
                        elif days_left <= 30:
                            tag = 'blue'
                        else:
                            tag = 'black'
                        self.table.insert(
                            "", "end",
                            values=(name, supplier, expiry_str, days_left),
                            tags=(tag,)
                        )
            finally:
                if cursor:
                    cursor.close()
                conn.close()

class StockMedicineSection:
    def __init__(self, parent):
        self.parent = parent

        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Medicine Stock Table", font=("Arial", 13, "bold")).pack(anchor="w", pady=(15, 5))

        # --- Search bar ---
        search_frame = ttk.Frame(frame)
        search_frame.pack(fill="x", pady=5)
        ttk.Label(search_frame, text="Search Medicine:").pack(side="left", padx=(0, 5))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=25)
        search_entry.pack(side="left")
        search_entry.bind("<Return>", lambda e: self.refresh_table_from_db())
        ttk.Button(search_frame, text="Search", command=self.refresh_table_from_db).pack(side="left", padx=(5, 5))
        ttk.Button(search_frame, text="Show All", command=self.clear_search).pack(side="left")

        # --- Table ---
        columns = ("Medicine", "Purchased", "Supplied", "Stock")
        self.table = ttk.Treeview(frame, columns=columns, show="headings", height=15)
        for col in columns:
            self.table.heading(col, text=col, anchor="center")
            self.table.column(col, width=120, anchor="center")
        self.table.pack(fill="x", pady=3)

        # Stock tag colors
        self.table.tag_configure('red', background='#FFCDD2', foreground='red')      # Stock ≤ 10
        self.table.tag_configure('orange', background='#FFE0B2', foreground='#E65100')# Stock ≤ 25
        self.table.tag_configure('black', background='white', foreground='black')     # Stock > 25

       

        self.refresh_table_from_db()

    def clear_search(self):
        self.search_var.set("")
        self.refresh_table_from_db()

    def refresh_table_from_db(self):
        # Clear table
        for item in self.table.get_children():
            self.table.delete(item)

        filter_text = self.search_var.get().strip().lower()
        conn = get_db_connection()
        if conn:
            cursor = None
            try:
                cursor = conn.cursor()
                # Get all medicines or filter by search
                if filter_text:
                    cursor.execute("SELECT id, name FROM medicines WHERE LOWER(name) LIKE %s ORDER BY name ASC", (f"%{filter_text}%",))
                else:
                    cursor.execute("SELECT id, name FROM medicines ORDER BY name ASC")
                medicines = cursor.fetchall()
                for med_id, name in medicines:
                    # Get purchased
                    cursor.execute("SELECT COALESCE(SUM(quantity),0) FROM medicine_purchases WHERE medicine_id=%s", (med_id,))
                    purchased = cursor.fetchone()[0] or 0
                    # Get supplied
                    cursor.execute("SELECT COALESCE(SUM(quantity),0) FROM medicine_supplies WHERE medicine_id=%s", (med_id,))
                    supplied = cursor.fetchone()[0] or 0
                    stock = purchased - supplied
                    # Stock alert coloring
                    if stock <= 10:
                        tag = 'red'
                    elif stock <= 25:
                        tag = 'orange'
                    else:
                        tag = 'black'
                    self.table.insert(
                        "", "end",
                        values=(name, purchased, supplied, stock),
                        tags=(tag,)
                    )
            finally:
                if cursor:
                    cursor.close()
                conn.close()

class ReportingFrame(ttk.Frame):
    from database import get_all_users, save_cash_in_hand
    def __init__(self, master, current_user, current_role):
        super().__init__(master)
        self.current_user = current_user
        self.current_role = current_role
        self.configure(style="TFrame")
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('TFrame', background='#e0f2f7')
        self.style.configure('TLabel', background='#e0f2f7', font=('Inter', 11))
        self.style.configure('TButton', font=('Inter', 11, 'bold'), padding=8)
        self.style.map('TButton',
            background=[('active', '#81D4FA'), ('!disabled', '#2196F3')],
            foreground=[('active', 'white'), ('!disabled', 'white')]
        )
        self.style.configure('Treeview.Heading', font=('Inter', 11, 'bold'))
        self.style.configure('Treeview', rowheight=28, font=('Arial', 11))
        self.setup_widgets()

    def setup_widgets(self):
        filter_frame = ttk.Frame(self, style='TFrame')
        filter_frame.pack(fill="x", padx=24, pady=20)

        ttk.Label(filter_frame, text="From Date (DD/MM/YYYY):").pack(side="left", padx=4)
        self.from_date_var = tk.StringVar(value=datetime.date.today().strftime("%d/%m/%Y"))
        from_entry = ttk.Entry(filter_frame, textvariable=self.from_date_var, width=12)
        from_entry.pack(side="left", padx=4)

        ttk.Label(filter_frame, text="To Date (DD/MM/YYYY):").pack(side="left", padx=4)
        self.to_date_var = tk.StringVar(value=datetime.date.today().strftime("%d/%m/%Y"))
        to_entry = ttk.Entry(filter_frame, textvariable=self.to_date_var, width=12)
        to_entry.pack(side="left", padx=4)

        ttk.Label(filter_frame, text="User:").pack(side="left", padx=4)
        self.user_var = tk.StringVar()

        def fetch_user_list():
         users = get_all_users()
         return ["All"] + [u["username"] for u in users]

        user_list = fetch_user_list()
        user_combo = ttk.Combobox(
        filter_frame, textvariable=self.user_var,
        values=user_list, state="readonly", width=14)
        user_combo.pack(side="left", padx=4)

        def refresh_user_list():
         user_combo['values'] = fetch_user_list()
         self.user_var.set("All")

        # Optional: add a refresh button for admins
        if self.current_role == "admin":
           ttk.Button(filter_frame, text="🔄 Refresh Users", command=refresh_user_list).pack(side="left", padx=4)

        if self.current_role != "admin":
           self.user_var.set(self.current_user)
           user_combo.config(state="disabled")
        else:
           self.user_var.set("All")

        ttk.Label(filter_frame, text="Department:").pack(side="left", padx=4)
        self.dept_var = tk.StringVar()
        dept_list = ["All", "General Medicine", "Pediatrics", "Orthopedics", "Gynecology",
                     "Cardiology", "Neurology", "Surgery", "ENT", "Dermatology", "Psychiatry"]
        dept_combo = ttk.Combobox(
            filter_frame, textvariable=self.dept_var,
            values=dept_list, state="readonly", width=22)
        dept_combo.pack(side="left", padx=4)
        self.dept_var.set("All")

        ttk.Button(filter_frame, text="🔍 Load Report", command=self.load_report, width=16).pack(side="left", padx=10)

        action_frame = ttk.Frame(self, style='TFrame')
        action_frame.pack(fill="x", padx=24, pady=7)
        ttk.Button(action_frame, text="Export to CSV", command=self.export_csv, width=15).pack(side="left", padx=8)
        ttk.Button(action_frame, text="Import", command=self.start_import_in_background, width=15).pack(side="left", padx=8)
        ttk.Button(action_frame, text="Print", command=self.print_report, width=12).pack(side="left", padx=8)

        columns = ("Date", "Username", "Department", "OPD", "IPD", "EPD", "Total", "Cash in Hand", "Used Cash in Hand", "Paid OPD Count")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=16)
        for col in columns:
          self.tree.heading(col, text=col, anchor="center")
          self.tree.column(col, width=120 if col not in ["Department", "Used Cash in Hand", "Paid OPD Count"] else 180, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=24, pady=10)
        self.load_report()

    

    def load_report(self):
      from_date = self.from_date_var.get().strip()
      to_date = self.to_date_var.get().strip()
      user_filter = self.user_var.get().strip()
      dept_filter = self.dept_var.get().strip()

      def to_yyyy_mm_dd(date_str):
        try:
            if len(date_str) == 10 and date_str[2] == "/":
                dt = datetime.datetime.strptime(date_str, "%d/%m/%Y")
                return dt.strftime("%Y-%m-%d")
            elif len(date_str) == 10 and date_str[4] == "-":
                return date_str
        except Exception:
            pass
        return date_str

      from_date_db = to_yyyy_mm_dd(from_date)
      to_date_db = to_yyyy_mm_dd(to_date)

      for item in self.tree.get_children():
        self.tree.delete(item)

      conn = get_db_connection()
      if not conn:
        messagebox.showerror("Database Error", "Could not connect to database.")
        return

      try:
        cursor = conn.cursor(dictionary=True)

        # OPD
        where_opd = ["registration_date BETWEEN %s AND %s"]
        params_opd = [from_date_db, to_date_db]
        if user_filter != "All":
            where_opd.append("created_by = %s")
            params_opd.append(user_filter)
        if dept_filter != "All":
            where_opd.append("medical_department = %s")
            params_opd.append(dept_filter)
        cursor.execute(f"""
            SELECT registration_date AS date, 
                   created_by AS username,
                   medical_department AS department, COUNT(*) AS cnt
            FROM OPD_Patients
            WHERE {' AND '.join(where_opd)}
            GROUP BY registration_date, username, department
        """, params_opd)
        opd_rows = cursor.fetchall()

        # IPD
        where_ipd = ["admission_date BETWEEN %s AND %s"]
        params_ipd = [from_date_db, to_date_db]
        if user_filter != "All":
            where_ipd.append("created_by = %s")
            params_ipd.append(user_filter)
        if dept_filter != "All":
            where_ipd.append("medical_department = %s")
            params_ipd.append(dept_filter)
        cursor.execute(f"""
            SELECT admission_date AS date, 
                   created_by AS username,
                   medical_department AS department, COUNT(*) AS cnt
            FROM IPD_Patients
            WHERE {' AND '.join(where_ipd)}
            GROUP BY admission_date, username, department
        """, params_ipd)
        ipd_rows = cursor.fetchall()

        # EPD
        where_epd = ["date BETWEEN %s AND %s"]
        params_epd = [from_date_db, to_date_db]
        if user_filter != "All":
            where_epd.append("created_by = %s")
            params_epd.append(user_filter)
        if dept_filter != "All":
            where_epd.append("medical_department = %s")
            params_epd.append(dept_filter)
        cursor.execute(f"""
            SELECT date, 
                   created_by AS username,
                   medical_department AS department, COUNT(*) AS cnt
            FROM EPD_Patients
            WHERE {' AND '.join(where_epd)}
            GROUP BY date, username, department
        """, params_epd)
        epd_rows = cursor.fetchall()

        # Aggregate, handling None
        report = {}
        for row in opd_rows:
            key = (
                str(row['date']) if row['date'] is not None else 'Unknown',
                row['username'] if row['username'] is not None else 'Unknown',
                row['department'] if row['department'] is not None else 'Unknown'
            )
            if key not in report:
                report[key] = {'OPD': 0, 'IPD': 0, 'EPD': 0}
            report[key]['OPD'] += row['cnt']
        for row in ipd_rows:
            key = (
                str(row['date']) if row['date'] is not None else 'Unknown',
                row['username'] if row['username'] is not None else 'Unknown',
                row['department'] if row['department'] is not None else 'Unknown'
            )
            if key not in report:
                report[key] = {'OPD': 0, 'IPD': 0, 'EPD': 0}
            report[key]['IPD'] += row['cnt']
        for row in epd_rows:
            key = (
                str(row['date']) if row['date'] is not None else 'Unknown',
                row['username'] if row['username'] is not None else 'Unknown',
                row['department'] if row['department'] is not None else 'Unknown'
            )
            if key not in report:
                report[key] = {'OPD': 0, 'IPD': 0, 'EPD': 0}
            report[key]['EPD'] += row['cnt']

        for (date, user, dept), counts in sorted(report.items()):
          # Only show own row for non-admins
         if self.current_role != "admin" and user != self.current_user:
           continue  # skip displaying this row

         total = counts['OPD'] + counts['IPD'] + counts['EPD']
         row = [ut.to_ddmmyyyy(date), user, dept, counts['OPD'], counts['IPD'], counts['EPD'], total]

         date_db = ut.convert_to_db_date_format(date)
         cash_in_hand = get_cash_in_hand(user, date_db)
         row.append(cash_in_hand if cash_in_hand is not None else "")

         # --- Used Cash / Paid OPD ---
         used_cash = 0.0
         paid_opd_count = 0
         conn2 = get_db_connection()
         if conn2:
           cur2 = conn2.cursor()
           cur2.execute("""
            SELECT COUNT(*), COALESCE(SUM(registration_fee),0)
            FROM OPD_Patients
            WHERE registration_date = %s AND created_by = %s AND medical_department = %s
                AND payment_status = 'Paid' AND registration_fee >= 5.00
            """, (date, user, dept))
           paid_opd_count, used_cash = cur2.fetchone()
           cur2.close()
           conn2.close()
         row.append(used_cash)
         row.append(paid_opd_count)

         self.tree.insert("", "end", values=tuple(row))
        if not report:
            self.tree.insert("", "end", values=("No data found", "", "", "", "", "", ""))
      finally:
        conn.close()

    

    def export_csv(self):
        filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not filename:
            return
        with open(filename, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Date", "Username", "Department", "OPD", "IPD", "EPD", "Total"])
            for item in self.tree.get_children():
                row = self.tree.item(item)["values"]
                writer.writerow(row[:7])  # Only first 7 columns
        messagebox.showinfo("Export", f"Report exported to {filename}")

    def import_data(self, patient_type):
  
      import tkinter.filedialog as fd
      from tkinter import messagebox
      import os
      import csv

      filetypes = [("CSV or MDB files", "*.csv *.mdb"), ("All files", "*.*")]
      file_path = fd.askopenfilename(title="Select import file", filetypes=filetypes)
      if not file_path:
        return

      imported = 0
      errors = 0
      error_msgs = []

      try:
        if file_path.lower().endswith(".csv"):
            with open(file_path, newline='', encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    result, err = self._import_patient_row(row, patient_type)
                    if result:
                        imported += 1
                    else:
                        errors += 1
                        error_msgs.append(err)
        elif file_path.lower().endswith(".mdb"):
            try:
                import pyodbc
            except ImportError:
                messagebox.showerror("Missing Dependency", "pyodbc is required for MDB import.")
                return
            conn_str = (
                r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
                f"DBQ={file_path};"
            )
            try:
                mdb_conn = pyodbc.connect(conn_str)
                cur = mdb_conn.cursor()
                table_map = {"OPD": "OPD_Patients", "IPD": "IPD_Patients", "EPD": "EPD_Patients"}
                cur.execute(f"SELECT * FROM {table_map[patient_type]}")
                columns = [col[0] for col in cur.description]
                for row_vals in cur.fetchall():
                    row = dict(zip(columns, row_vals))
                    result, err = self._import_patient_row(row, patient_type)
                    if result:
                        imported += 1
                    else:
                        errors += 1
                        error_msgs.append(err)
                cur.close()
                mdb_conn.close()
            except Exception as e:
                messagebox.showerror("MDB Import Error", str(e))
                return
        else:
            messagebox.showerror("Invalid File", "Please select a CSV or MDB file.")
            return
      except Exception as e:
        messagebox.showerror("Import Error", str(e))
        return

      msg = f"Imported: {imported}\nErrors: {errors}"
      if errors:
        msg += f"\nFirst error: {error_msgs[0]}"
      messagebox.showinfo("Import Result", msg)

    def start_import_in_background(self):
        threading.Thread(target=self.import_data, daemon=True).start()

    def _import_patient_row(self, row, patient_type):
      import database
      import utils as ut
      import re
      import datetime

      def clean_str(val, default="Unknown"):
        # Treat empty, 'blank', 'null' as missing
        if val is None or str(val).strip().lower() in ["", "blank", "null"]:
            return default
        return str(val).strip()

      def clean_nullable_str(val):
        if val is None or str(val).strip().lower() in ["", "blank", "null"]:
            return None
        return str(val).strip()

      def clean_int(val):
        try:
            if val is None or str(val).strip().lower() in ["", "blank", "null"]:
                return 0
            return int(val)
        except Exception:
            return 0

      def clean_float(val):
        try:
            if val is None or str(val).strip().lower() in ["", "blank", "null"]:
                return 0.0
            return float(val)
        except Exception:
            return 0.0

      def clean_date(val):
        # Accepts DD-MM-YYYY, DD/MM/YYYY, YYYY-MM-DD, else today
        if not val or str(val).strip().lower() in ["", "blank", "null"]:
            return datetime.date.today().strftime('%Y-%m-%d')
        val = str(val).strip()
        # Try DD-MM-YYYY
        try:
            if "-" in val and len(val) == 10:
                dt = datetime.datetime.strptime(val, "%d-%m-%Y")
                return dt.strftime("%Y-%m-%d")
        except Exception:
            pass
        # Try DD/MM/YYYY
        try:
            if "/" in val and len(val) == 10:
                dt = datetime.datetime.strptime(val, "%d/%m/%Y")
                return dt.strftime("%Y-%m-%d")
        except Exception:
            pass
        # Try YYYY-MM-DD
        if len(val) == 10 and val[4] == "-":
            return val
        # Fallback: today
        return datetime.date.today().strftime('%Y-%m-%d')

      try:
        if patient_type == "OPD":
            fields = [
                "registration_number", "first_name", "last_name", "father_name", "abha_number",
                "age", "gender", "mobile_number", "email", "address", "post_office", "town",
                "state", "registration_fee", "payment_status", "registration_date",
                "medical_department", "created_by"
            ]
            args = {k: (row.get(k) if k in row else None) for k in fields}

            # Required fields with safe defaults
            args["first_name"] = clean_str(args.get("first_name"))
            args["father_name"] = clean_str(args.get("father_name"))
            args["age"] = clean_int(args.get("age"))
            args["gender"] = clean_str(args.get("gender"), default="Unknown")
            args["mobile_number"] = clean_str(args.get("mobile_number"), default="Unknown")
            args["address"] = clean_str(args.get("address"), default="Unknown")
            args["town"] = clean_str(args.get("town"), default="Unknown")
            args["state"] = clean_str(args.get("state"), default="Unknown")
            args["medical_department"] = clean_str(args.get("medical_department"), default="Unknown")
            # Optional fields
            args["last_name"] = clean_nullable_str(args.get("last_name"))
            args["abha_number"] = clean_nullable_str(args.get("abha_number"))
            args["email"] = clean_nullable_str(args.get("email"))
            args["post_office"] = clean_nullable_str(args.get("post_office"))
            args["registration_fee"] = clean_float(args.get("registration_fee"))
            args["payment_status"] = clean_str(args.get("payment_status"), default="Paid")
            args["registration_date"] = clean_date(args.get("registration_date"))
            if not args.get("created_by"):
                args["created_by"] = self.current_user
            if not args.get("registration_number"):
                args["registration_number"] = database.get_next_registration_number("opd")
            # Check for duplicate reg no
            if args["registration_number"]:
                existing = database.get_patient_by_reg_number(args["registration_number"])
                if existing:
                    return False, f"Duplicate registration_number {args['registration_number']}"
            result = database.add_opd_patient(**args)
            if result:
                return True, ""
        elif patient_type == "IPD":
            fields = [
                "registration_number", "first_name", "last_name", "father_name", "abha_number",
                "age", "gender", "mobile_number", "email", "address", "post_office", "town",
                "state", "medical_department", "police_case", "bed_number", "room_number",
                "admission_date", "discharge_date", "notes", "created_by"
            ]
            args = {k: (row.get(k) if k in row else None) for k in fields}
            args["first_name"] = clean_str(args.get("first_name"))
            args["father_name"] = clean_str(args.get("father_name"))
            args["age"] = clean_int(args.get("age"))
            args["gender"] = clean_str(args.get("gender"), default="Unknown")
            args["mobile_number"] = clean_str(args.get("mobile_number"), default="Unknown")
            args["address"] = clean_str(args.get("address"), default="Unknown")
            args["town"] = clean_str(args.get("town"), default="Unknown")
            args["state"] = clean_str(args.get("state"), default="Unknown")
            args["medical_department"] = clean_str(args.get("medical_department"), default="Unknown")
            args["bed_number"] = clean_str(args.get("bed_number"), default="Unknown")
            args["room_number"] = clean_str(args.get("room_number"), default="Unknown")
            args["police_case"] = clean_str(args.get("police_case"), default="No")
            # Optional fields
            args["last_name"] = clean_nullable_str(args.get("last_name"))
            args["abha_number"] = clean_nullable_str(args.get("abha_number"))
            args["email"] = clean_nullable_str(args.get("email"))
            args["post_office"] = clean_nullable_str(args.get("post_office"))
            args["admission_date"] = clean_date(args.get("admission_date"))
            args["discharge_date"] = clean_date(args.get("discharge_date"))
            args["notes"] = clean_nullable_str(args.get("notes"))
            if not args.get("created_by"):
                args["created_by"] = self.current_user
            if not args.get("registration_number"):
                args["registration_number"] = database.get_next_registration_number("ipd")
            # Check for duplicate reg no
            if args["registration_number"]:
                conn = database.get_db_connection()
                if conn:
                    try:
                        cur = conn.cursor()
                        cur.execute("SELECT COUNT(*) FROM IPD_Patients WHERE registration_number=%s", (args["registration_number"],))
                        if cur.fetchone()[0] > 0:
                            return False, f"Duplicate registration_number {args['registration_number']}"
                    finally:
                        cur.close()
                        conn.close()
            result = database.add_ipd_patient(**args)
            if result:
                return True, ""
        elif patient_type == "EPD":
            fields = [
                "registration_number", "first_name", "last_name", "father_name", "abha_number",
                "age", "gender", "mobile_number", "email", "address", "post_office", "town",
                "state", "medical_department", "police_case", "emergency_type", "arrival_mode",
                "arrival_datetime", "triage_level", "attending_doctor", "discharge_datetime",
                "outcome", "notes", "date", "created_by"
            ]
            args = {k: (row.get(k) if k in row else None) for k in fields}
            args["first_name"] = clean_str(args.get("first_name"))
            args["father_name"] = clean_str(args.get("father_name"))
            args["age"] = clean_int(args.get("age"))
            args["gender"] = clean_str(args.get("gender"), default="Unknown")
            args["mobile_number"] = clean_str(args.get("mobile_number"), default="Unknown")
            args["address"] = clean_str(args.get("address"), default="Unknown")
            args["town"] = clean_str(args.get("town"), default="Unknown")
            args["state"] = clean_str(args.get("state"), default="Unknown")
            args["medical_department"] = clean_str(args.get("medical_department"), default="Unknown")
            args["police_case"] = clean_str(args.get("police_case"), default="No")
            # Optional fields
            args["last_name"] = clean_nullable_str(args.get("last_name"))
            args["abha_number"] = clean_nullable_str(args.get("abha_number"))
            args["email"] = clean_nullable_str(args.get("email"))
            args["post_office"] = clean_nullable_str(args.get("post_office"))
            args["emergency_type"] = clean_nullable_str(args.get("emergency_type"))
            args["arrival_mode"] = clean_nullable_str(args.get("arrival_mode"))
            args["arrival_datetime"] = clean_date(args.get("arrival_datetime"))
            args["triage_level"] = clean_nullable_str(args.get("triage_level"))
            args["attending_doctor"] = clean_nullable_str(args.get("attending_doctor"))
            args["discharge_datetime"] = clean_date(args.get("discharge_datetime"))
            args["outcome"] = clean_nullable_str(args.get("outcome"))
            args["notes"] = clean_nullable_str(args.get("notes"))
            args["date"] = clean_date(args.get("date"))
            if not args.get("created_by"):
                args["created_by"] = self.current_user
            if not args.get("registration_number"):
                args["registration_number"] = database.get_next_registration_number("epd")
            # Check for duplicate reg no
            if args["registration_number"]:
                conn = database.get_db_connection()
                if conn:
                    try:
                        cur = conn.cursor()
                        cur.execute("SELECT COUNT(*) FROM EPD_Patients WHERE registration_number=%s", (args["registration_number"],))
                        if cur.fetchone()[0] > 0:
                            return False, f"Duplicate registration_number {args['registration_number']}"
                    finally:
                        cur.close()
                        conn.close()
            result = database.add_epd_patient(**args)
            if result:
                return True, ""
        return False, f"Failed to add row (maybe duplicate or missing required fields): {row}"
      except Exception as e:
        return False, str(e)
      
    def show_progress_dialog(self):
        self.progress_dialog = tk.Toplevel(self)
        self.progress_dialog.title("Importing...")
        self.progress_dialog.geometry("280x90")
        self.progress_dialog.transient(self)
        self.progress_dialog.grab_set()
        ttk.Label(self.progress_dialog, text="Importing data, please wait...").pack(pady=(18, 6))
        self.progress_bar = ttk.Progressbar(self.progress_dialog, mode='indeterminate')
        self.progress_bar.pack(fill='x', padx=20, pady=(0, 16))
        self.progress_bar.start()

    def close_progress_dialog(self):
        if hasattr(self, 'progress_dialog') and self.progress_dialog.winfo_exists():
            self.progress_bar.stop()
            self.progress_dialog.grab_release()
            self.progress_dialog.destroy()

    def start_import_in_background(self):
      import tkinter.simpledialog as sd
      from tkinter import messagebox

      # Prompt user for patient type on main thread!
      patient_type = sd.askstring("Patient Type", "Import into which table? (OPD, IPD, or EPD)")
      if not patient_type:
        return
      patient_type = patient_type.strip().upper()
      if patient_type not in ("OPD", "IPD", "EPD"):
        messagebox.showerror("Invalid Type", "Please select OPD, IPD, or EPD.")
        return

      self.show_progress_dialog()
      threading.Thread(target=self._run_import_with_progress, args=(patient_type,), daemon=True).start()

    def _run_import_with_progress(self, patient_type):
      try:
        self.import_data(patient_type)
      finally:
        self.after(0, self.close_progress_dialog)

    def print_report(self):
        print_win = tk.Toplevel(self)
        print_win.title("Report Print Preview")
        print_win.geometry("900x600")
        print_win.config(bg="white")
        title = tk.Label(
            print_win,
            text="Reporting Summary",
            font=('Arial', 19, 'bold'),
            fg="#0D47A1",
            bg="white",
            pady=16
        )
        title.pack(fill="x")
        from_date = ut.to_ddmmyyyy(self.from_date_var.get())
        to_date = ut.to_ddmmyyyy(self.to_date_var.get())
        filters = []
        if self.user_var.get() and self.user_var.get() != "All":
            filters.append(f"User: {self.user_var.get()}")
        if self.dept_var.get() and self.dept_var.get() != "All":
            filters.append(f"Department: {self.dept_var.get()}")
        if from_date or to_date:
            filters.append(f"Date: {from_date} to {to_date}")
        filter_text = " | ".join(filters)
        tk.Label(
            print_win,
            text=f"Filter Applied : {filter_text}" if filter_text else "",
            font=('Arial', 12),
            bg="white",
            fg="#1976D2"
        ).pack(fill="x")

        table_frame = tk.Frame(print_win, bg="white")
        table_frame.pack(padx=28, pady=16, fill="both", expand=True)
        headers = ["Date", "Username", "Department", "OPD", "IPD", "EPD", "Total"]
        for col, text in enumerate(headers):
            tk.Label(
                table_frame,
                text=text,
                font=('Arial', 12, 'bold'),
                bg="#e3f0fa",
                fg="#0D47A1",
                width=15,
                borderwidth=1,
                relief="solid"
            ).grid(row=0, column=col, sticky="nsew", padx=1, pady=1)
            table_frame.columnconfigure(col, weight=1)

        for i, item in enumerate(self.tree.get_children(), 1):
            values = self.tree.item(item)["values"]
            row_values = list(values[:7])
            if row_values and row_values[0] not in ("No data found", ""):
                row_values[0] = ut.to_ddmmyyyy(row_values[0])
            for col, val in enumerate(row_values):
                tk.Label(
                    table_frame,
                    text=val,
                    font=('Arial', 11),
                    bg="white" if i % 2 == 0 else "#f7fbff",
                    fg="#212121",
                    width=15,
                    borderwidth=1,
                    relief="solid"
                ).grid(row=i, column=col, sticky="nsew", padx=1, pady=1)

        total_entries = sum(
            int(self.tree.item(item)["values"][-1]) for item in self.tree.get_children()
            if str(self.tree.item(item)["values"][-1]).isdigit()
        )
        tk.Label(
            print_win,
            text=f"Total Entries: {total_entries}",
            font=('Arial', 12, 'bold'),
            bg="white",
            fg="#1976D2",
            pady=8
        ).pack(anchor="e", padx=32)

        btn_frame = tk.Frame(print_win, bg="white")
        btn_frame.pack(pady=12)
        ttk.Button(btn_frame, text="Print", command=lambda: self._actual_print_report()).pack(side="left", padx=12)
        ttk.Button(btn_frame, text="Close", command=print_win.destroy).pack(side="left", padx=12)

    def _actual_print_report(self):
      from tkinter import messagebox
      from dot_matrix_print_utils import print_reporting_summary_a4
      # Gather report data exactly as displayed
      report_data = []
      for item in self.tree.get_children():
        values = self.tree.item(item)["values"]
        if values and values[0] not in ("No data found", ""):
            report_data.append({
                "Date": str(values[0]),
                "User": str(values[1]),
                "Department": str(values[2]),
                "OPD": str(values[3]),
                "IPD": str(values[4]),
                "EPD": str(values[5]),
                "Total": str(values[6]),
            })
      from_date = self.from_date_var.get().strip()
      to_date = self.to_date_var.get().strip()
      user_filter = self.user_var.get().strip()
      dept_filter = self.dept_var.get().strip()
      try:
        print_reporting_summary_a4(report_data, from_date, to_date, user_filter, dept_filter)
        messagebox.showinfo("Print", "Report print job sent!")
      except Exception as e:
        messagebox.showerror("Print Error", f"Printing failed: {e}")



def main():
    root = tk.Tk()
    app = PatientRegistrationApp(root)
    root.protocol("WM_DELETE_WINDOW", app.close_app)
    root.mainloop()

if __name__ == "__main__":
    main()