import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool
import bcrypt
import logging
import os
import datetime
from dotenv import load_dotenv

# --- Logging ---
logging.basicConfig(level=logging.INFO, filename='patient_app.log')
logger = logging.getLogger(__name__)

load_dotenv()  # Loads environment variables from .env
SESSION_TIMEOUT_MINUTES = int(os.environ.get("SESSION_TIMEOUT_MINUTES", "10"))

# --- Configuration ---
DATABASE_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASS' ),  # Removed hardcoded default  
    'database': os.environ.get('DB_NAME'),
    'connect_timeout': 10
}

POOL_CONFIG = {
    'pool_name': 'patient_pool',
    'pool_size': 20,
    'autocommit': True,
    **DATABASE_CONFIG
}

try:
    connection_pool = MySQLConnectionPool(**POOL_CONFIG)
except mysql.connector.Error as e:
    logger.error(f"Error creating connection pool: {e}")
    raise

def get_db_connection():
    """Get a connection from the pool, or None on failure."""
    try:
        return connection_pool.get_connection()
    except Exception as e:
        logger.error(f"Failed to get database connection: {e}")
        return None

def create_tables():
    """Create essential tables if not present. Returns (success, info)."""
    conn = get_db_connection()
    if not conn:
        logger.error("Cannot connect to database for table creation.")
        return False, "Cannot connect to database."
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'user',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                is_logged_in BOOLEAN NOT NULL DEFAULT FALSE,
                last_login_time DATETIME DEFAULT NULL,
            )
        """)
        cursor.execute("SHOW COLUMNS FROM users LIKE 'role'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'")
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
        if cursor.fetchone()[0] == 0:
            default_password = "admin123"
            hashed_password = bcrypt.hashpw(default_password.encode('utf-8'), bcrypt.gensalt())
            cursor.execute("""
                INSERT INTO users (username, password_hash, role)
                VALUES (%s, %s, %s)
            """, ('admin', hashed_password.decode('utf-8'), 'admin'))
        # You may want to add more tables here as needed.
        conn.commit()
        return True, "Tables created successfully."
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating tables: {e}")
        return False, f"Error creating tables: {e}"
    finally:
        cursor.close()
        conn.close()

# --- User Management ---
def add_user(username, password, role='user'):
    """Add a user if not exists. Returns (success, info)."""
    conn = get_db_connection()
    if not conn:
        logger.error("Database connection error on add_user")
        return False, "DB connection error"
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = %s", (username,))
        if cursor.fetchone()[0] > 0:
            return False, "User already exists"
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        # Save both hash and plain
        cursor.execute(
            "INSERT INTO users (username, password_hash, plain_password, role,is_logged_in, last_login_time) VALUES (%s, %s, %s, %s,%s,%s)",
            (username, hashed_password, password, role,False, None)
        )
        conn.commit()
        return True, "User added"
    except Exception as e:
        conn.rollback()
        logger.error(f"Error adding user: {e}")
        return False, f"Error adding user: {e}"
    finally:
        cursor.close()
        conn.close()

def get_all_users():
    """Return list of all users as dicts, including plaintext password for admin view."""
    conn = get_db_connection()
    if not conn:
        logger.error("Database connection error on get_all_users")
        return []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT user_id, username, plain_password, role, created_at FROM users ORDER BY user_id ASC")
        users = cursor.fetchall()
        return users
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def delete_user(username):
    """Delete a user by username unless admin. Returns (success, info)."""
    if username == 'admin':
        return False, "Cannot delete default admin"
    conn = get_db_connection()
    if not conn:
        logger.error("Database connection error on delete_user")
        return False, "DB connection error"
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM users WHERE username = %s", (username,))
        conn.commit()
        return True, "User deleted"
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting user: {e}")
        return False, f"Error deleting user: {e}"
    finally:
        cursor.close()
        conn.close()


def authenticate_user(username: str, password: str):
    """
    Authenticate and ensure single active session using an atomic UPDATE.
    Returns:
      - True on successful login
      - "already_logged_in" if another active session blocks login
      - False on failure (invalid credentials or DB error)
    """
    conn = get_db_connection()
    if not conn:
        logger.error("DB connection error on authenticate_user_atomic")
        return False
    cur = conn.cursor(dictionary=True)
    try:
        # 1) Fetch password_hash for verification
        cur.execute("SELECT password_hash, last_login_time, is_logged_in FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        if not user:
            return False

        # verify password
        if not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            return False

        # 2) Try to atomically acquire login slot:
        # We allow login if is_logged_in = FALSE OR last_login_time <= NOW() - INTERVAL timeout MINUTE
        # Build SQL to update only when allowed and check affected rows
        sql = f"""
            UPDATE users
            SET is_logged_in = TRUE, last_login_time = NOW()
            WHERE username = %s
              AND (
                    is_logged_in = FALSE
                    OR last_login_time <= DATE_SUB(NOW(), INTERVAL %s MINUTE)
                  )
        """
        cur2 = conn.cursor()
        cur2.execute(sql, (username, SESSION_TIMEOUT_MINUTES))
        conn.commit()
        if cur2.rowcount > 0:
            cur2.close()
            return True
        else:
            # No rows updated: someone else has active session within timeout
            cur2.close()
            return "already_logged_in"
    except Exception as e:
        logger.exception("authenticate_user_atomic error: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass

def logout_user(username):
    conn = get_db_connection()
    if not conn:
        logger.error("Database connection error on logout_user")
        return False
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET is_logged_in = FALSE WHERE username = %s", (username,))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Error logging out user: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def save_cash_in_hand(username, cash_value, date=None):
    import datetime
    # Ensure date is always set and correct format
    if not date or (isinstance(date, str) and not date.strip()):
        date = datetime.date.today()
    elif isinstance(date, str):
        # Try parsing string, fallback to today if parsing fails
        try:
            date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
        except Exception:
            date = datetime.date.today()
    conn = get_db_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT IGNORE INTO user_cash_log (username, date, cash_in_hand)
            VALUES (%s, %s, %s)
        """, (username, date, cash_value))
        conn.commit()
        return True
    finally:
        cursor.close()
        conn.close()

# --- Registration Sequence ---
def get_next_registration_number(reg_type):
 
    conn = get_db_connection()
    if not conn:
        logger.error("DB connection error in get_next_registration_number")
        print("DB connection error in get_next_registration_number")
        return None
    conn.autocommit = True  # <--- MAKE SURE THIS IS HERE!
    
    conn.rollback()  # optional debug, try if stuck
    cursor = conn.cursor()
    try:
        args = [reg_type, None]
        results = cursor.callproc('lifo_generate_registration_number', args)
        reg_no = results[1]
        
        return reg_no
    except Exception as e:
        logger.error(f"Error generating registration number: {e}")
        
        return None
    finally:
        cursor.close()
        conn.close()



# --- Patient CRUD ---
def add_opd_patient(
    registration_number, first_name, last_name, father_name, abha_number,
    age, gender, mobile_number, email, address, post_office, town,
    state, registration_fee, payment_status, registration_date, medical_department, created_by
):
    """
    Add an OPD patient. Returns registration_number or None.
    Shows error dialog on failure.
    """
    import datetime
    from tkinter import messagebox

    # --- Convert registration_date to DB format ---
    if registration_date:
        try:
            if isinstance(registration_date, str):
                if '/' in registration_date:
                    registration_date = datetime.datetime.strptime(registration_date, "%d/%m/%Y").strftime("%Y-%m-%d")
                elif '-' in registration_date:
                    datetime.datetime.strptime(registration_date, "%Y-%m-%d")
        except Exception as e:
            logger.error(f"Date conversion error for OPD patient: {e}")
            messagebox.showerror("Database Error", f"Invalid registration date: {e}")
            return None

    # --- Ensure optional fields are None if empty ---
    def none_if_empty(val):
        return val if val not in ("", None) else None

    last_name = none_if_empty(last_name)
    father_name = none_if_empty(father_name)
    abha_number = none_if_empty(abha_number)
    email = none_if_empty(email)
    address = none_if_empty(address)
    post_office = none_if_empty(post_office)
    town = none_if_empty(town)
    state = none_if_empty(state)
    medical_department = none_if_empty(medical_department)
    created_by = none_if_empty(created_by)

    # --- DB Insert ---
    conn = get_db_connection()
    if not conn:
        logger.error("DB connection error on add_opd_patient")
        messagebox.showerror("Database Error", "Unable to connect to database.")
        return None
    cursor = conn.cursor()
    try:
        sql = """INSERT INTO OPD_Patients (
            registration_number, first_name, last_name, father_name, abha_number, age, gender,
            mobile_number, email, address, post_office, town, state, registration_fee, payment_status,
            registration_date, medical_department, created_by
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s
        )"""
        values = (
            registration_number, first_name, last_name, father_name, abha_number, age, gender,
            mobile_number, email, address, post_office, town, state, registration_fee, payment_status,
            registration_date, medical_department, created_by
        )
        cursor.execute(sql, values)
        conn.commit()
        logger.info(f"Added OPD patient: {registration_number}")
        return registration_number
    except Exception as e:
        conn.rollback()
        logger.error(f"Error adding OPD patient: {e}")
        messagebox.showerror("Database Error", f"Error adding OPD patient: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

def add_epd_patient(
    registration_number,
    first_name, last_name=None, father_name=None, abha_number=None, age=None, gender=None,
    mobile_number=None, email=None, address=None, post_office=None, town=None, state=None,
    medical_department=None, police_case=None, emergency_type=None, arrival_mode=None,
    arrival_datetime=None, triage_level=None, attending_doctor=None, discharge_datetime=None,
    outcome=None, notes=None, date=None, created_by=None
):
    """Add EPD patient. Returns registration_number or None."""
    conn = get_db_connection()
    if not conn:
        logger.error("DB connection error on add_epd_patient")
        return None
    cursor = conn.cursor()
    try:
        sql = """INSERT INTO EPD_Patients (
            registration_number, first_name, last_name, father_name, abha_number, age, gender,
            mobile_number, email, address, post_office, town, state, medical_department,
            police_case, emergency_type, arrival_mode, arrival_datetime, date, triage_level,
            attending_doctor, discharge_datetime, outcome, notes, created_by
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )"""
        values = (
            registration_number, first_name, last_name, father_name, abha_number, age, gender,
            mobile_number, email, address, post_office, town, state, medical_department,
            police_case, emergency_type, arrival_mode, arrival_datetime, date, triage_level,
            attending_doctor, discharge_datetime, outcome, notes, created_by
        )
        cursor.execute(sql, values)
        conn.commit()
        logger.info(f"Added EPD patient: {registration_number}")
        return registration_number
    except Exception as e:
        conn.rollback()
        logger.error(f"Error adding EPD patient: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

def add_ipd_patient(
    registration_number, first_name, last_name, father_name, abha_number, age, gender,
    mobile_number, email, address, post_office, town, state, medical_department,
    police_case, bed_number, room_number, admission_date, discharge_date, notes, created_by
):
    """Add IPD patient. Returns registration_number or None."""
    conn = get_db_connection()
    if not conn:
        logger.error("DB connection error on add_ipd_patient")
        return None
    cursor = conn.cursor()
    try:
        sql = """INSERT INTO IPD_Patients (
            registration_number, first_name, last_name, father_name, abha_number, age, gender,
            mobile_number, email, address, post_office, town, state, medical_department,
            police_case, bed_number, room_number, admission_date, discharge_date, notes, created_by
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )"""
        values = (
            registration_number, first_name, last_name, father_name, abha_number, age, gender,
            mobile_number, email, address, post_office, town, state, medical_department,
            police_case, bed_number, room_number, admission_date, discharge_date, notes, created_by
        )
        cursor.execute(sql, values)
        conn.commit()
        logger.info(f"Added IPD patient: {registration_number}")
        return registration_number
    except Exception as e:
        conn.rollback()
        logger.error(f"Error adding IPD patient: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

def update_patient(registration_number, registration_date, **fields):
    """
    Update OPD patient fields by registration_number and registration_date. Returns True/False.
    """
    import datetime
    conn = get_db_connection()
    if not conn:
        logger.error("DB connection error on update_patient")
        return False
    cursor = conn.cursor()
    try:
        updates = []
        params = []
        for k, v in fields.items():
            if v is not None:
                updates.append(f"{k} = %s")
                params.append(v)
        if not updates:
            return False
        sql = f"UPDATE OPD_Patients SET {', '.join(updates)} WHERE registration_number = %s AND registration_date = %s"
        params.append(registration_number)
        params.append(registration_date)
        cursor.execute(sql, tuple(params))
        conn.commit()
        logger.info(f"Update SQL: {sql} ; Params: {params} ; Rowcount: {cursor.rowcount}")
        return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating OPD patient: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def update_epd_patient(registration_number, **fields):
    """Update EPD patient fields by registration_number. Returns True/False."""
    conn = get_db_connection()
    if not conn:
        logger.error("DB connection error on update_epd_patient")
        return False
    cursor = conn.cursor()
    try:
        updates = []
        params = []
        for k, v in fields.items():
            if v is not None:
                updates.append(f"{k} = %s")
                params.append(v)
        if not updates:
            return False
        sql = f"UPDATE EPD_Patients SET {', '.join(updates)} WHERE registration_number = %s"
        params.append(registration_number)
        cursor.execute(sql, tuple(params))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating EPD patient: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def update_ipd_patient(registration_number, **fields):
    """Update IPD patient fields by registration_number. Returns True/False."""
    conn = get_db_connection()
    if not conn:
        logger.error("DB connection error on update_ipd_patient")
        return False
    cursor = conn.cursor()
    try:
        updates = []
        params = []
        for k, v in fields.items():
            if v is not None:
                updates.append(f"{k} = %s")
                params.append(v)
        if not updates:
            return False
        sql = f"UPDATE IPD_Patients SET {', '.join(updates)} WHERE registration_number = %s"
        params.append(registration_number)
        cursor.execute(sql, tuple(params))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating IPD patient: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def get_all_patients(page=1, page_size=100):
    """Return paginated list of all patients (OPD, EPD, IPD)."""
    conn = get_db_connection()
    if not conn:
        logger.error("DB connection error on get_all_patients")
        return []
    cursor = conn.cursor(dictionary=True)
    offset = (page - 1) * page_size
    try:
        cursor.execute("""
            SELECT * FROM (
                SELECT o.registration_number, o.first_name, o.last_name, o.mobile_number, o.gender, o.age, 'OPD' AS patient_type
                FROM OPD_Patients o WHERE o.registration_number NOT IN (SELECT registration_number FROM IPD_Patients WHERE registration_number IS NOT NULL)
                UNION
                SELECT e.registration_number, e.first_name, e.last_name, e.mobile_number, e.gender, e.age, 'EPD' AS patient_type
                FROM EPD_Patients e WHERE (e.registration_number NOT IN (SELECT registration_number FROM IPD_Patients WHERE registration_number IS NOT NULL) OR e.registration_number IS NULL)
                UNION
                SELECT i.registration_number, i.first_name, i.last_name, i.mobile_number, i.gender, i.age, 'IPD' AS patient_type
                FROM IPD_Patients i
            ) AS unified
            ORDER BY registration_number
            LIMIT %s OFFSET %s
        """, (page_size, offset))
        patients = cursor.fetchall()
        return patients
    except Exception as e:
        logger.error(f"Error fetching all patients: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def search_patients(
    registration_number="", name="", father_name="", phone="", department="",
    town="", state="", gender="", age="", from_date="", to_date="", patient_type="",
    page=1, page_size=100
):
    """
    Search patients with filters. Returns (list, info_msg).
    """
    conn = get_db_connection()
    if not conn:
        logger.error("DB connection error on search_patients")
        return [], "DB connection error"
    cursor = conn.cursor(dictionary=True)
    offset = (page - 1) * page_size

    def build_where(date_field):
        clauses = []
        params = []
        if registration_number.strip():
            clauses.append("registration_number = %s")
            params.append(registration_number.strip())
        if name.strip():
            like_term = f"%{name.strip().lower()}%"
            clauses.append("(LOWER(first_name) LIKE %s OR LOWER(last_name) LIKE %s)")
            params.extend([like_term, like_term])
        if father_name.strip():
            like_term = f"%{father_name.strip().lower()}%"
            clauses.append("LOWER(father_name) LIKE %s")
            params.append(like_term)
        if phone.strip():
            clauses.append("mobile_number = %s")
            params.append(phone.strip())
        if department.strip():
            clauses.append("medical_department = %s")
            params.append(department.strip())
        if town.strip():
            clauses.append("LOWER(town) LIKE %s")
            params.append(f"%{town.strip().lower()}%")
        if state.strip():
            clauses.append("LOWER(state) LIKE %s")
            params.append(f"%{state.strip().lower()}%")
        if gender.strip():
            clauses.append("gender = %s")
            params.append(gender.strip())
        if age.strip():
            try:
                age_val = int(age)
                clauses.append("age BETWEEN %s AND %s")
                params.extend([age_val - 2, age_val + 2])
            except ValueError:
                pass
        date_format = "%d/%m/%Y"
        db_format = "%Y-%m-%d"
        if from_date.strip():
            try:
                date_from = datetime.datetime.strptime(from_date.strip(), date_format).strftime(db_format)
                clauses.append(f"{date_field} >= %s")
                params.append(date_from)
            except Exception:
                pass
        if to_date.strip():
            try:
                date_to = datetime.datetime.strptime(to_date.strip(), date_format).strftime(db_format)
                clauses.append(f"{date_field} <= %s")
                params.append(date_to)
            except Exception:
                pass
        where_sql = " AND ".join(clauses)
        return where_sql, params

    queries = []
    params_list = []
    types_to_search = []
    if not patient_type or patient_type.lower() == "all":
        types_to_search = ["OPD", "EPD", "IPD"]
    else:
        types_to_search = [patient_type.upper()]
    if "OPD" in types_to_search:
        opd_where, opd_params = build_where("registration_date")
        queries.append(f"""
            SELECT o.registration_number, o.first_name, o.last_name, o.mobile_number, o.gender, o.age, 'OPD' AS patient_type,
                o.registration_date, o.medical_department, o.town, o.state
            FROM OPD_Patients o
            {'WHERE ' + opd_where if opd_where else ''}
        """)
        params_list.extend(opd_params)
    if "EPD" in types_to_search:
        epd_where, epd_params = build_where("date")
        queries.append(f"""
            SELECT e.registration_number, e.first_name, e.last_name, e.mobile_number, e.gender, e.age, 'EPD' AS patient_type,
                e.date AS registration_date, e.medical_department, e.town, e.state
            FROM EPD_Patients e
            {'WHERE ' + epd_where if epd_where else ''}
        """)
        params_list.extend(epd_params)
    if "IPD" in types_to_search:
        ipd_where, ipd_params = build_where("admission_date")
        queries.append(f"""
            SELECT i.registration_number, i.first_name, i.last_name, i.mobile_number, i.gender, i.age, 'IPD' AS patient_type,
                i.admission_date AS registration_date, i.medical_department, i.town, i.state
            FROM IPD_Patients i
            {'WHERE ' + ipd_where if ipd_where else ''}
        """)
        params_list.extend(ipd_params)
    query = " UNION ALL ".join(queries) + "\nORDER BY registration_number LIMIT %s OFFSET %s"
    params_list += [page_size, offset]
    try:
        cursor.execute(query, params_list)
        patients = cursor.fetchall()
        found_count = len(patients)
        info_msg = f"{found_count} patient(s) found." if found_count else "No patients found with the given criteria."
        return patients, info_msg
    except Exception as e:
        logger.error(f"Error searching patients: {e}")
        return [], "Error searching patients."
    finally:
        cursor.close()
        conn.close()

def get_patient_by_reg_number(registration_number):
    """Get OPD patient by registration number."""
    conn = get_db_connection()
    if not conn:
        logger.error("DB connection error on get_patient_by_reg_number")
        return None
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM OPD_Patients WHERE registration_number = %s", (registration_number,))
        patient = cursor.fetchone()
        return patient
    except Exception as e:
        logger.error(f"Error getting patient by reg number: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

# --- Medicine Management ---
def add_medicine(name, generic_name=None, manufacturer=None, description=None):
    """Add medicine to medicines table. Returns id or None."""
    conn = get_db_connection()
    if not conn:
        logger.error("DB connection error on add_medicine")
        return None
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO medicines (name, generic_name, manufacturer, description) VALUES (%s, %s, %s, %s)",
            (name, generic_name, manufacturer, description)
        )
        conn.commit()
        med_id = cursor.lastrowid
        return med_id
    except Exception as e:
        conn.rollback()
        logger.error(f"Error adding medicine: {e}")
        return None
    finally:
        cursor.close()
        

def add_medicine_purchase(medicine_name, supplier, quantity, purchase_date, expiry_date, unit_price=None, batch_number=None):
    """Add a medicine purchase. Returns True/False."""
    conn = get_db_connection()
    if not conn:
        logger.error("DB connection error on add_medicine_purchase")
        return False
    cursor = conn.cursor()
    try:
        # Find medicine ID (case-insensitive)
        cursor.execute("SELECT id FROM medicines WHERE LOWER(name) = LOWER(%s)", (medicine_name,))
        result = cursor.fetchone()
        if not result:
            # Close the cursor before calling add_medicine (it will open its own connection)
            cursor.close()
            medicine_id = add_medicine(medicine_name)
            if not medicine_id:
                conn.close()
                return False
            # Re-open cursor for this connection
            cursor = conn.cursor()
        else:
            medicine_id = result[0]
        # Insert purchase
        cursor.execute("""
            INSERT INTO medicine_purchases (medicine_id, purchase_date, quantity, supplier, unit_price, expiry_date, batch_number)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (medicine_id, purchase_date, quantity, supplier, unit_price, expiry_date, batch_number))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Error recording medicine purchase: {e}")
        return False
    finally:
        cursor.close()
        conn.close()
     

def add_medicine_supply(medicine_name, supply_date, quantity, department, purchase_id, supplied_to=None):
    """Add medicine supply. Returns True/False."""
    conn = get_db_connection()
    if not conn:
        logger.error("DB connection error on add_medicine_supply")
        return False
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM medicines WHERE LOWER(name) = LOWER(%s)", (medicine_name,))
        result = cursor.fetchone()
        if not result:
            return False
        medicine_id = result[0]
        cursor.execute("""
            INSERT INTO medicine_supplies (medicine_id, purchase_id, supply_date, quantity, department, supplied_to)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (medicine_id, purchase_id, supply_date, quantity, department, supplied_to))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Error recording medicine supply: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def get_current_stock(medicine_name):
    """Return current stock of a medicine (int) or None if not found."""
    conn = get_db_connection()
    if not conn:
        logger.error("DB connection error on get_current_stock")
        return None
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM medicines WHERE LOWER(name)=LOWER(%s)", (medicine_name,))
        med_row = cursor.fetchone()
        if not med_row:
            return None
        medicine_id = med_row[0]
        cursor.execute("SELECT COALESCE(SUM(quantity),0) FROM medicine_purchases WHERE medicine_id=%s", (medicine_id,))
        purchased = cursor.fetchone()[0] or 0
        cursor.execute("SELECT COALESCE(SUM(quantity),0) FROM medicine_supplies WHERE medicine_id=%s", (medicine_id,))
        supplied = cursor.fetchone()[0] or 0
        return purchased - supplied
    except Exception as e:
        logger.error(f"Error getting current stock: {e}")
        return None
    finally:
        cursor.close()
        conn.close()
def update_user_sections(username, sections):
    """
    Update allowed sections for a user.
    Sections is a list of section names (strings).
    """
    conn = get_db_connection()
    if not conn:
        return False, "DB connection error"
    cursor = conn.cursor()
    try:
        sections_str = ','.join(sections)
        cursor.execute("UPDATE users SET sections_allowed = %s WHERE username = %s", (sections_str, username))
        conn.commit()
        return True, "Sections updated"
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating user sections: {e}")
        return False, f"Error updating sections: {e}"
    finally:
        cursor.close()
        conn.close()



def get_user_by_username(username):
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        return cursor.fetchone()
    except Exception as e:
        logger.error(f"Error fetching user: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

def get_batchwise_stock(medicine_name):
    """
    Return list of (batch_id, supplier, expiry_date, purchased_qty, supplied_qty, stock_left)
    for batches with stock_left > 0.
    """
    conn = get_db_connection()
    if not conn:
        logger.error("DB connection error on get_batchwise_stock")
        return []
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM medicines WHERE LOWER(name)=LOWER(%s)", (medicine_name,))
        med_row = cursor.fetchone()
        if not med_row:
            return []
        medicine_id = med_row[0]
        query = """
            SELECT 
                p.id AS batch_id,
                p.supplier,
                p.expiry_date,
                p.quantity AS purchased_qty,
                COALESCE(SUM(s.quantity), 0) AS supplied_qty,
                (p.quantity - COALESCE(SUM(s.quantity), 0)) AS stock_left
            FROM medicine_purchases p
            LEFT JOIN medicine_supplies s ON s.purchase_id = p.id
            WHERE p.medicine_id = %s
            GROUP BY p.id, p.supplier, p.expiry_date, p.quantity
            HAVING stock_left > 0
            ORDER BY p.expiry_date ASC
        """
        cursor.execute(query, (medicine_id,))
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting batchwise stock: {e}")
        return []
    finally:
        cursor.close()
        conn.close()