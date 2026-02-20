# Hospital Management System

This is a comprehensive Hospital Management System (HMS) built with Python (Tkinter for the UI) and MySQL for the backend.  
It supports OPD, IPD, EPD patient management, user roles, medicine stock, reporting, and more.


---

![Python](https://img.shields.io/badge/Python-3.8+-blue)
![License](https://img.shields.io/badge/License-Educational-lightgrey)
![GitHub stars](https://img.shields.io/github/stars/Princyyy9/Hospital-Database-Management-System?style=social)

---
## Project Structure

```
PatientPython/
├── main.py
├── ui.py
├── database.py
├── utils.py
├── dot_matrix_print_utils.py
├── printer_manager.py
├── printer_selector.py
├── schema.sql
├── .env.example
├── partition.mdb
└── README.md
```
## Features

- **User Authentication:** Admin and User roles, with password hashing (bcrypt).
- **Daily Cash In Hand Logging:** Per-user, per-day, only first entry counts.
- **Patient Registration:** OPD, IPD, EPD registration & update with thorough validation.
- **Bulk Import/Export:** Import from CSV/MDB, Export to CSV.
- **Advanced Search:** Search/filter patients by multiple criteria with paging.
- **Medicine Management:** Purchases, supplies, expiry, batch tracking, and live stock tables.
- **Reporting:** Daily, per-user, per-department reporting with export/print.
- **User Management:** Admin panel for user CRUD and tab permission assignment.

---

## Installation & Setup

### 1. **Python & Dependencies**

- Python 3.8+
- [pip](https://pip.pypa.io/en/stable/installing/)
- Install requirements:
  ```sh
  pip install mysql-connector-python bcrypt pillow tkcalendar
  ```

### 2. **MySQL Setup**

- Install MySQL Server.
- Create a database (default: `new_db`) and user.
- Import the SQL schema (`schema.sql` or run the provided SQL statements).
- **IMPORTANT:**  
  Do **not** use the `root` user in production!  
  Create a dedicated user with a strong password and only required permissions.

### 3. **Environment Variables**

Edit `database.py` or set as environment variables:
- `DB_HOST` (default: `localhost`)
- `DB_USER` (default: `root`)
- `DB_PASS` (set your password)
- `DB_NAME` (default: `new_db`)

**Example:**
```sh
export DB_USER=hms_user
export DB_PASS=yoursecurepassword
export DB_NAME=new_db
```

### 4. **Initial Admin Login**

- Username: `admin`
- Password: `admin123`
- (Change this password after first login!)

---

## Running the App

```sh
python ui.py
```

- The app will launch with a role selection screen (Admin/User).
- Log in, enter your cash in hand (required), and proceed to the main dashboard.

---

## Notes for Production

- **Remove plaintext password storage**: Remove the `plain_password` column and its usage for maximum security.
- **Back up your database regularly.**
- **Add new partitions every year** to the patient tables for best performance.  
  Example to add 2027:
  ```sql
  ALTER TABLE OPD_Patients ADD PARTITION (PARTITION p2027 VALUES LESS THAN (2028));
  ALTER TABLE IPD_Patients ADD PARTITION (PARTITION p2027 VALUES LESS THAN (2028));
  ALTER TABLE EPD_Patients ADD PARTITION (PARTITION p2027 VALUES LESS THAN (2028));
  ```
- **Never store passwords in source code or logs.**

---

## User Guide

- **Reception/Registration:** Add new patients, search records, print cards.
- **Medicine:** Record purchases, supplies, monitor stock/expiry.
- **Reporting:** Filter by date, user, department; export/print.
- **User Management:** (Admin only) Add/remove users, assign tab permissions.

---

## Troubleshooting

- **Can't connect to MySQL:**  
  - Check your DB credentials and that MySQL is running.
  - Check user permissions.
- **Tkinter or other import errors:**  
  - Ensure all required Python packages are installed.
- **Cash in Hand not showing:**  
  - Ensure you log in each day and enter the value at login. Only the first entry per user per day is saved/displayed.

---

## Customization

- **Logo/Icons:** Place `admin_icon.png`, `user_icon.png`, and `back_icon.png` in the project folder.
- **Hospital Name:** Edit it in the code (search for `"Hospital & Research Center"`).
- **Departments:** To add/remove medical departments, update the department lists in the UI and DB as needed.

---

## Security Best Practices

- Change the default admin password after first login.
- Restrict database user permissions in production.
- Never share database credentials publicly.
- Regularly update dependencies for security patches.

---

## Security Consideration

Passwords are hashed using bcrypt for authentication.

Plaintext password storage was implemented due to a specific client requirement for administrative recovery purposes. In a production environment, this would be replaced with a secure password reset mechanism.

---

## Tech Stack

- Python 3.8+
- Tkinter (GUI)
- MySQL (Database)
- mysql-connector-python
- bcrypt (Password Hashing)
- tkcalendar
- Pillow

---

## Technical Highlights

- Implemented MySQL connection pooling for optimized performance
- Atomic login session control with timeout logic
- Role-based access control with section permissions
- Batch-wise medicine stock tracking
- Paginated search queries for performance
- Database partitioning strategy for long-term scalability

---

## Architecture

The application follows a modular structure:
- UI Layer (ui.py)
- Business Logic & Database Layer (database.py)
- Utility & Print Modules
- MySQL Backend

---

## Support

For bugs or feature requests, contact your developer or open an issue.

---

## License

This project is intended for educational and demonstration purposes.
