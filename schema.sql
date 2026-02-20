-- First, drop the database if it exists
DROP DATABASE IF EXISTS new_db;

-- Then, create the database and use it, as in your original script
CREATE DATABASE IF NOT EXISTS new_db;
USE new_db;

-- Creating States table for normalization
CREATE TABLE IF NOT EXISTS States (
    state_id INT AUTO_INCREMENT PRIMARY KEY,
    state_name VARCHAR(100) NOT NULL UNIQUE
) ENGINE=InnoDB;

-- Creating Towns table for normalization
CREATE TABLE IF NOT EXISTS Towns (
    town_id INT AUTO_INCREMENT PRIMARY KEY,
    town_name VARCHAR(100) NOT NULL,
    state_id INT NOT NULL,
    FOREIGN KEY (state_id) REFERENCES States(state_id) ON DELETE RESTRICT,
    UNIQUE (town_name, state_id)
) ENGINE=InnoDB;

-- Creating Patients table with 'age' instead of 'date_of_birth'
-- and 'registration_number' as an auto-incrementing integer.
CREATE TABLE IF NOT EXISTS Patients (
    patient_id INT AUTO_INCREMENT PRIMARY KEY,
    -- Changed registration_number to INT AUTO_INCREMENT for sequential numbering
    -- It will now automatically generate 1, 2, 3, etc.
    registration_number INT AUTO_INCREMENT UNIQUE,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    father_name VARCHAR(100),
    abha_number VARCHAR(20),
    -- Replaced date_of_birth with age
    age INT,
    gender ENUM('Male', 'Female', 'Other'),
    mobile_number VARCHAR(10),
    email VARCHAR(100),
    address VARCHAR(255),
    post_office VARCHAR(100),
    town_id INT,
    state_id INT,
    registration_fee DECIMAL(10,2) DEFAULT 5.00,
    payment_status ENUM('Paid', 'Free') NOT NULL DEFAULT 'Paid',
    registration_date DATE NOT NULL,
    medical_condition TEXT,
    FOREIGN KEY (state_id) REFERENCES States(state_id) ON DELETE SET NULL,
    FOREIGN KEY (town_id) REFERENCES Towns(town_id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- Creating Visits table without partitioning
CREATE TABLE IF NOT EXISTS Visits (
    visit_id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL,
    visit_date DATE NOT NULL,
    reason_for_visit TEXT,
    notes TEXT,
    FOREIGN KEY (patient_id) REFERENCES Patients(patient_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Creating Diagnoses table
CREATE TABLE IF NOT EXISTS Diagnoses (
    diagnosis_id INT AUTO_INCREMENT PRIMARY KEY,
    visit_id INT NOT NULL,
    diagnosis_text TEXT NOT NULL,
    FOREIGN KEY (visit_id) REFERENCES Visits(visit_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Creating Treatments table
CREATE TABLE IF NOT EXISTS Treatments (
    treatment_id INT AUTO_INCREMENT PRIMARY KEY,
    visit_id INT NOT NULL,
    treatment_text TEXT NOT NULL,
    medication VARCHAR(255),
    dosage VARCHAR(100),
    FOREIGN KEY (visit_id) REFERENCES Visits(visit_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Creating indexes for performance
CREATE INDEX idx_patients_name ON Patients (last_name, first_name);
CREATE INDEX idx_patients_mobile ON Patients (mobile_number);
-- Index on registration_number (now INT)
CREATE INDEX idx_patients_reg_num ON Patients (registration_number);
CREATE INDEX idx_visits_patient_id ON Visits (patient_id);
CREATE INDEX idx_visits_date ON Visits (visit_date);
-- Updated FULLTEXT index as registration_number is now INT and not suitable for text search
CREATE FULLTEXT INDEX idx_patients_search ON Patients (first_name, last_name);

-- Trigger to validate mobile_number and set registration_date
DELIMITER //
CREATE TRIGGER before_insert_patient
BEFORE INSERT ON Patients
FOR EACH ROW
BEGIN
    IF NEW.mobile_number IS NOT NULL AND (LENGTH(NEW.mobile_number) != 10 OR NEW.mobile_number REGEXP '[^0-9]') THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Mobile number must be exactly 10 digits';
    END IF;
    IF NEW.registration_date IS NULL THEN
        SET NEW.registration_date = CURDATE();
    END IF;
    -- No need to handle registration_number here, it's AUTO_INCREMENT
    -- No need to handle date_of_birth, as it's replaced by age
END//
DELIMITER ;

-- Trigger to validate visit_date
DELIMITER //
CREATE TRIGGER before_insert_visit
BEFORE INSERT ON Visits
FOR EACH ROW
BEGIN
    IF NEW.visit_date IS NULL THEN
        SET NEW.visit_date = CURDATE();
    END IF;
END//
DELIMITER ;

-- Stored Procedure: Add a new patient
-- Removed p_registration_number as it's auto-generated
-- Changed p_date_of_birth to p_age
DELIMITER //
CREATE PROCEDURE AddPatient(
    IN p_first_name VARCHAR(50),
    IN p_last_name VARCHAR(50),
    IN p_father_name VARCHAR(100),
    IN p_abha_number VARCHAR(20),
    IN p_age INT, -- Changed from p_date_of_birth DATE
    IN p_gender ENUM('Male', 'Female', 'Other'),
    IN p_mobile_number VARCHAR(10),
    IN p_email VARCHAR(100),
    IN p_address VARCHAR(255),
    IN p_post_office VARCHAR(100),
    IN p_town_id INT,
    IN p_state_id INT,
    IN p_registration_fee DECIMAL(10,2),
    IN p_payment_status ENUM('Paid', 'Free'),
    IN p_registration_date DATE,
    IN p_medical_condition TEXT,
    OUT p_patient_id INT,
    OUT p_generated_registration_number INT -- Output the auto-generated reg number
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Error adding patient';
    END;

    INSERT INTO Patients (
        first_name, last_name, father_name, abha_number,
        age, gender, mobile_number, email, address, post_office, -- Changed date_of_birth to age
        town_id, state_id, registration_fee, payment_status, registration_date,
        medical_condition
    )
    VALUES (
        NULLIF(p_first_name, ''), NULLIF(p_last_name, ''),
        NULLIF(p_father_name, ''), NULLIF(p_abha_number, ''), p_age, -- Using p_age
        p_gender, NULLIF(p_mobile_number, ''), NULLIF(p_email, ''),
        NULLIF(p_address, ''), NULLIF(p_post_office, ''), p_town_id,
        p_state_id, IFNULL(p_registration_fee, 5.00), p_payment_status,
        IFNULL(p_registration_date, CURDATE()), NULLIF(p_medical_condition, '')
    );

    SET p_patient_id = LAST_INSERT_ID();
    -- Retrieve the auto-generated registration_number
    SELECT registration_number INTO p_generated_registration_number FROM Patients WHERE patient_id = p_patient_id;
END//
DELIMITER ;

-- Stored Procedure: Update a patient
-- Changed p_date_of_birth to p_age
DELIMITER //
CREATE PROCEDURE UpdatePatient(
    IN p_patient_id INT,
    IN p_first_name VARCHAR(50),
    IN p_last_name VARCHAR(50),
    IN p_father_name VARCHAR(100),
    IN p_abha_number VARCHAR(20),
    IN p_age INT, -- Changed from p_date_of_birth DATE
    IN p_gender ENUM('Male', 'Female', 'Other'),
    IN p_mobile_number VARCHAR(10),
    IN p_email VARCHAR(100),
    IN p_address VARCHAR(255),
    IN p_post_office VARCHAR(100),
    IN p_town_id INT,
    IN p_state_id INT,
    IN p_payment_status ENUM('Paid', 'Free'),
    IN p_medical_condition TEXT
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Error updating patient';
    END;

    UPDATE Patients
    SET
        first_name = NULLIF(p_first_name, ''),
        last_name = NULLIF(p_last_name, ''),
        father_name = NULLIF(p_father_name, ''),
        abha_number = NULLIF(p_abha_number, ''),
        age = p_age, -- Using p_age
        gender = p_gender,
        mobile_number = NULLIF(p_mobile_number, ''),
        email = NULLIF(p_email, ''),
        address = NULLIF(p_address, ''),
        post_office = NULLIF(p_post_office, ''),
        town_id = p_town_id,
        state_id = p_state_id,
        payment_status = p_payment_status,
        medical_condition = NULLIF(p_medical_condition, '')
    WHERE patient_id = p_patient_id;
END//
DELIMITER ;

-- Stored Procedure: Delete a patient
DELIMITER //
CREATE PROCEDURE DeletePatient(
    IN p_patient_id INT
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Error deleting patient';
    END;

    DELETE FROM Patients WHERE patient_id = p_patient_id;
END//
DELIMITER ;

-- Stored Procedure: Get patient by registration_number
-- Changed p_registration_number to INT
DELIMITER //
CREATE PROCEDURE GetPatientByRegNumber(
    IN p_registration_number INT
)
BEGIN
    SELECT * FROM Patients
    WHERE registration_number = p_registration_number;
END//
DELIMITER ;

-- Stored Procedure: Get all patients with pagination
DELIMITER //
CREATE PROCEDURE GetAllPatients(
    IN p_page INT,
    IN p_page_size INT
)
BEGIN
    DECLARE v_offset INT;
    SET v_offset = (p_page - 1) * p_page_size;

    SELECT * FROM Patients
    ORDER BY last_name, first_name
    LIMIT p_page_size OFFSET v_offset;
END//
DELIMITER ;

-- Stored Procedure: Search patients with pagination
-- Removed registration_number from MATCH AGAINST as it's now INT
DELIMITER //
CREATE PROCEDURE SearchPatients(
    IN p_search_term VARCHAR(100),
    IN p_page INT,
    IN p_page_size INT
)
BEGIN
    DECLARE v_offset INT;
    SET v_offset = (p_page - 1) * p_page_size;

    SELECT * FROM Patients
    WHERE MATCH(first_name, last_name) AGAINST (p_search_term IN BOOLEAN MODE)
    ORDER BY last_name, first_name
    LIMIT p_page_size OFFSET v_offset;
END//
DELIMITER ;

-- Stored Procedure: Add a visit
DELIMITER //
CREATE PROCEDURE AddVisit(
    IN p_patient_id INT,
    IN p_visit_date DATE,
    IN p_reason_for_visit TEXT,
    IN p_notes TEXT,
    OUT p_visit_id INT
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Error adding visit';
    END;

    INSERT INTO Visits (patient_id, visit_date, reason_for_visit, notes)
    VALUES (p_patient_id, IFNULL(p_visit_date, CURDATE()), NULLIF(p_reason_for_visit, ''), NULLIF(p_notes, ''));

    SET p_visit_id = LAST_INSERT_ID();
END//
DELIMITER ;

-- Stored Procedure: Get visits by patient_id
DELIMITER //
CREATE PROCEDURE GetVisitsByPatientId(
    IN p_patient_id INT
)
BEGIN
    SELECT * FROM Visits
    WHERE patient_id = p_patient_id
    ORDER BY visit_date DESC;
END//
DELIMITER ;

-- Stored Procedure: Update a visit
DELIMITER //
CREATE PROCEDURE UpdateVisit(
    IN p_visit_id INT,
    IN p_visit_date DATE,
    IN p_reason_for_visit TEXT,
    IN p_notes TEXT
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Error updating visit';
    END;

    UPDATE Visits
    SET
        visit_date = p_visit_date,
        reason_for_visit = NULLIF(p_reason_for_visit, ''),
        notes = NULLIF(p_notes, '')
    WHERE visit_id = p_visit_id;
END//
DELIMITER ;

-- Stored Procedure: Delete a visit
DELIMITER //
CREATE PROCEDURE DeleteVisit(
    IN p_visit_id INT
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Error deleting visit';
    END;

    DELETE FROM Visits WHERE visit_id = p_visit_id;
END//
DELIMITER ;

-- Stored Procedure: Add a diagnosis
DELIMITER //
CREATE PROCEDURE AddDiagnosis(
    IN p_visit_id INT,
    IN p_diagnosis_text TEXT,
    OUT p_diagnosis_id INT
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Error adding diagnosis';
    END;

    INSERT INTO Diagnoses (visit_id, diagnosis_text)
    VALUES (p_visit_id, p_diagnosis_text);

    SET p_diagnosis_id = LAST_INSERT_ID();
END//
DELIMITER ;

-- Stored Procedure: Get diagnoses by visit_id
DELIMITER //
CREATE PROCEDURE GetDiagnosesByVisitId(
    IN p_visit_id INT
)
BEGIN
    SELECT * FROM Diagnoses
    WHERE visit_id = p_visit_id;
END//
DELIMITER ;

-- Stored Procedure: Update a diagnosis
DELIMITER //
CREATE PROCEDURE UpdateDiagnosis(
    IN p_diagnosis_id INT,
    IN p_diagnosis_text TEXT
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Error updating diagnosis';
    END;

    UPDATE Diagnoses
    SET diagnosis_text = p_diagnosis_text
    WHERE diagnosis_id = p_diagnosis_id;
END//
DELIMITER ;

-- Stored Procedure: Delete a diagnosis
DELIMITER //
CREATE PROCEDURE DeleteDiagnosis(
    IN p_diagnosis_id INT
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Error deleting diagnosis';
    END;

    DELETE FROM Diagnoses WHERE diagnosis_id = p_diagnosis_id;
END//
DELIMITER ;

-- Stored Procedure: Add a treatment
DELIMITER //
CREATE PROCEDURE AddTreatment(
    IN p_visit_id INT,
    IN p_treatment_text TEXT,
    IN p_medication VARCHAR(255),
    IN p_dosage VARCHAR(100),
    OUT p_treatment_id INT
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Error adding treatment';
    END;

    INSERT INTO Treatments (visit_id, treatment_text, medication, dosage)
    VALUES (p_visit_id, p_treatment_text, NULLIF(p_medication, ''), NULLIF(p_dosage, ''));

    SET p_treatment_id = LAST_INSERT_ID();
END//
DELIMITER ;

-- Stored Procedure: Get treatments by visit_id
DELIMITER //
CREATE PROCEDURE GetTreatmentsByVisitId(
    IN p_visit_id INT
)
BEGIN
    SELECT * FROM Treatments
    WHERE visit_id = p_visit_id;
END//
DELIMITER ;

-- Stored Procedure: Update a treatment
DELIMITER //
CREATE PROCEDURE UpdateTreatment(
    IN p_treatment_id INT,
    IN p_treatment_text TEXT,
    IN p_medication VARCHAR(255),
    IN p_dosage VARCHAR(100)
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Error updating treatment';
    END;

    UPDATE Treatments
    SET
        treatment_text = p_treatment_text,
        medication = NULLIF(p_medication, ''),
        dosage = NULLIF(p_dosage, '')
    WHERE treatment_id = p_treatment_id;
END//
DELIMITER ;

-- Stored Procedure: Delete a treatment
DELIMITER //
CREATE PROCEDURE DeleteTreatment(
    IN p_treatment_id INT
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Error deleting treatment';
    END;

    DELETE FROM Treatments WHERE treatment_id = p_treatment_id;
END//
DELIMITER ;

-- Stored Procedure: Bulk insert patients (for testing/scalability)
-- Removed registration_number generation and insertion
-- Changed date_of_birth to age
DELIMITER //
CREATE PROCEDURE BulkInsertPatients(
    IN p_batch_size INT
)
BEGIN
    DECLARE v_counter INT DEFAULT 0;
    DECLARE v_first_name VARCHAR(50);
    DECLARE v_last_name VARCHAR(50);

    START TRANSACTION;

    WHILE v_counter < p_batch_size DO
        SET v_first_name = CONCAT('First', v_counter);
        SET v_last_name = CONCAT('Last', v_counter);

        INSERT INTO Patients (
            first_name, last_name, age, gender, -- Changed date_of_birth to age
            mobile_number, registration_fee, payment_status, registration_date
        )
        VALUES (
            v_first_name, v_last_name, 30, 'Male', -- Sample age instead of date_of_birth
            CONCAT('123456', LPAD(v_counter % 10000, 4, '0')), 5.00, 'Paid', CURDATE()
        );

        SET v_counter = v_counter + 1;
    END WHILE;

    COMMIT;
END//
DELIMITER ;

-- Insert sample data for States and Towns
INSERT INTO States (state_name) VALUES
    ('Karnataka'),
    ('Maharashtra'),
    ('Delhi');

-- Using subqueries to get state_id dynamically
INSERT INTO Towns (town_name, state_id) VALUES
    ('Bangalore', (SELECT state_id FROM States WHERE state_name = 'Karnataka')),
    ('Mumbai', (SELECT state_id FROM States WHERE state_name = 'Maharashtra')),
    ('New Delhi', (SELECT state_id FROM States WHERE state_name = 'Delhi'));


