-- Contact Form Database DDL Script
-- For Oracle SQL*Plus

-- Create sequence for submission IDs
CREATE SEQUENCE submission_seq
  START WITH 1
  INCREMENT BY 1
  NOCACHE
  NOCYCLE;

-- Create STUDENTS table to store student information
CREATE TABLE STUDENTS (
    student_id VARCHAR2(20),
    name VARCHAR2(100) NOT NULL,
    email VARCHAR2(100) NOT NULL,
    CONSTRAINT pk_students PRIMARY KEY (student_id),
    CONSTRAINT stud_email_unique UNIQUE (email)
);

-- Add comment to table
COMMENT ON TABLE STUDENTS IS 'Stores information about students who submit contact forms';

-- Create SUBJECTS table to store predefined subjects
CREATE TABLE SUBJECTS (
    subject_id NUMBER,
    subject_name VARCHAR2(200) NOT NULL,
    department VARCHAR2(100),
    priority NUMBER(1) DEFAULT 3,
    CONSTRAINT pk_subjects PRIMARY KEY (subject_id),
    CONSTRAINT chk_priority CHECK (priority BETWEEN 1 AND 5)
);

-- Add comment to table
COMMENT ON TABLE SUBJECTS IS 'Lookup table for contact form subjects';

-- Create CONTACT_SUBMISSIONS table to store form submissions
CREATE TABLE CONTACT_SUBMISSIONS (
    submission_id NUMBER DEFAULT submission_seq.NEXTVAL,
    student_id VARCHAR2(20),
    subject_id NUMBER,
    details CLOB NOT NULL,
    submission_date TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
    status VARCHAR2(20) DEFAULT 'New' NOT NULL,
    last_updated TIMESTAMP,
    CONSTRAINT pk_contact_submissions PRIMARY KEY (submission_id),
    CONSTRAINT fk_student FOREIGN KEY (student_id) REFERENCES STUDENTS(student_id),
    CONSTRAINT fk_subject FOREIGN KEY (subject_id) REFERENCES SUBJECTS(subject_id),
    CONSTRAINT chk_status CHECK (status IN ('New', 'In Progress', 'Resolved', 'Closed'))
);

-- Add comment to table
COMMENT ON TABLE CONTACT_SUBMISSIONS IS 'Stores details of contact form submissions';

-- Create indexes for performance enhancement
CREATE INDEX idx_submission_date ON CONTACT_SUBMISSIONS(submission_date);
CREATE INDEX idx_submission_status ON CONTACT_SUBMISSIONS(status);
CREATE INDEX idx_student_name ON STUDENTS(name);

-- Create a trigger to update last_updated timestamp when a submission is modified
CREATE OR REPLACE TRIGGER trg_update_submission
BEFORE UPDATE ON CONTACT_SUBMISSIONS
FOR EACH ROW
BEGIN
    :NEW.last_updated := SYSTIMESTAMP;
END;
/

-- Insert sample data for SUBJECTS table
INSERT INTO SUBJECTS (subject_id, subject_name, department, priority) 
VALUES (1, 'Technical Issue', 'IT Support', 2);

INSERT INTO SUBJECTS (subject_id, subject_name, department, priority) 
VALUES (2, 'Academic Question', 'Academic Affairs', 3);

INSERT INTO SUBJECTS (subject_id, subject_name, department, priority) 
VALUES (3, 'Administrative Request', 'Administration', 3);

INSERT INTO SUBJECTS (subject_id, subject_name, department, priority) 
VALUES (4, 'Urgent Help Needed', 'Student Services', 1);

INSERT INTO SUBJECTS (subject_id, subject_name, department, priority) 
VALUES (5, 'Feedback', 'Quality Assurance', 4);

-- Create a view for easy access to submission information
CREATE OR REPLACE VIEW vw_contact_submissions AS
SELECT 
    cs.submission_id,
    s.name AS student_name,
    s.student_id,
    s.email AS student_email,
    sub.subject_name,
    sub.department,
    sub.priority,
    cs.details,
    cs.submission_date,
    cs.status,
    cs.last_updated
FROM 
    CONTACT_SUBMISSIONS cs,
    STUDENTS s,
    SUBJECTS sub
WHERE 
    cs.student_id = s.student_id
    AND cs.subject_id = sub.subject_id;

-- Create a procedure to add a new contact submission
CREATE OR REPLACE PROCEDURE proc_add_submission (
    p_student_id IN VARCHAR2,
    p_name IN VARCHAR2,
    p_email IN VARCHAR2,
    p_subject_name IN VARCHAR2,
    p_details IN CLOB
) AS
    v_subject_id NUMBER;
    v_student_exists NUMBER;
BEGIN
    -- Check if student exists
    SELECT COUNT(*) INTO v_student_exists FROM STUDENTS WHERE student_id = p_student_id;
    
    -- If not, insert new student
    IF v_student_exists = 0 THEN
        INSERT INTO STUDENTS (student_id, name, email)
        VALUES (p_student_id, p_name, p_email);
    END IF;
    
    -- Get subject ID based on name
    BEGIN
        SELECT subject_id INTO v_subject_id FROM SUBJECTS WHERE subject_name = p_subject_name;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            -- Use a default subject if not found
            SELECT subject_id INTO v_subject_id FROM SUBJECTS WHERE ROWNUM = 1;
    END;
    
    -- Insert submission
    INSERT INTO CONTACT_SUBMISSIONS (student_id, subject_id, details)
    VALUES (p_student_id, v_subject_id, p_details);
    
    COMMIT;
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE;
END proc_add_submission;
/

-- End of script