-- SQL Server setup script for Contact Form database
-- This script creates or modifies the contact_submissions table with enhanced security

USE [Wlv];
GO

-- Check if the table exists and create it if it doesn't
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[contact_submissions]') AND type in (N'U'))
BEGIN
    CREATE TABLE [dbo].[contact_submissions](
        [id] [int] IDENTITY(1,1) NOT NULL,
        [name] [nvarchar](100) NOT NULL,
        [student_id] [nvarchar](20) NULL,
        [email] [nvarchar](120) NOT NULL,
        [subject] [nvarchar](200) NOT NULL,
        [details] [nvarchar](max) NOT NULL,
        [submission_date] [datetime] NOT NULL DEFAULT GETDATE(),
        [ip_address] [varchar](45) NULL,
        [processed] [bit] NOT NULL DEFAULT 0,
        [processed_by] [nvarchar](100) NULL,
        [processed_date] [datetime] NULL,
        PRIMARY KEY CLUSTERED ([id] ASC)
    );
    
    PRINT 'contact_submissions table created successfully';
END
ELSE
BEGIN
    -- Check if we need to add any new columns to the existing table
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID(N'[dbo].[contact_submissions]') AND name = 'submission_date')
    BEGIN
        ALTER TABLE [dbo].[contact_submissions] ADD [submission_date] [datetime] NOT NULL DEFAULT GETDATE();
        PRINT 'Added submission_date column';
    END
    
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID(N'[dbo].[contact_submissions]') AND name = 'ip_address')
    BEGIN
        ALTER TABLE [dbo].[contact_submissions] ADD [ip_address] [varchar](45) NULL;
        PRINT 'Added ip_address column';
    END
    
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID(N'[dbo].[contact_submissions]') AND name = 'processed')
    BEGIN
        ALTER TABLE [dbo].[contact_submissions] ADD [processed] [bit] NOT NULL DEFAULT 0;
        PRINT 'Added processed column';
    END
    
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID(N'[dbo].[contact_submissions]') AND name = 'processed_by')
    BEGIN
        ALTER TABLE [dbo].[contact_submissions] ADD [processed_by] [nvarchar](100) NULL;
        PRINT 'Added processed_by column';
    END
    
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID(N'[dbo].[contact_submissions]') AND name = 'processed_date')
    BEGIN
        ALTER TABLE [dbo].[contact_submissions] ADD [processed_date] [datetime] NULL;
        PRINT 'Added processed_date column';
    END
    
    PRINT 'contact_submissions table updated successfully';
END
GO

-- Create an index on email for faster lookups
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='IX_contact_submissions_email' AND object_id = OBJECT_ID('contact_submissions'))
BEGIN
    CREATE INDEX IX_contact_submissions_email ON contact_submissions (email);
    PRINT 'Created index on email column';
END
GO

-- Create a table to track form submission attempts for additional rate limiting
IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[submission_attempts]') AND type in (N'U'))
BEGIN
    CREATE TABLE [dbo].[submission_attempts](
        [id] [int] IDENTITY(1,1) NOT NULL,
        [ip_address] [varchar](45) NOT NULL,
        [attempt_time] [datetime] NOT NULL DEFAULT GETDATE(),
        [success] [bit] NOT NULL DEFAULT 0,
        PRIMARY KEY CLUSTERED ([id] ASC)
    );
    
    CREATE INDEX IX_submission_attempts_ip ON submission_attempts (ip_address);
    PRINT 'submission_attempts table created successfully';
END
GO

-- Create a view that excludes sensitive data for reporting purposes
IF NOT EXISTS (SELECT * FROM sys.views WHERE name = 'vw_contact_submissions_safe')
BEGIN
    EXEC('
    CREATE VIEW vw_contact_submissions_safe AS
    SELECT 
        id,
        -- First character of name followed by asterisks
        LEFT(name, 1) + REPLICATE(''*'', LEN(name) - 1) AS name,
        -- Safe version of email (username@domain.com becomes u***@d***.com)
        LEFT(email, 1) + REPLICATE(''*'', CHARINDEX(''@'', email) - 2) + 
        ''@'' + LEFT(SUBSTRING(email, CHARINDEX(''@'', email) + 1, LEN(email)), 1) + 
        REPLICATE(''*'', CHARINDEX(''.'', SUBSTRING(email, CHARINDEX(''@'', email) + 1, LEN(email))) - 2) +
        SUBSTRING(SUBSTRING(email, CHARINDEX(''@'', email) + 1, LEN(email)), 
                  CHARINDEX(''.'', SUBSTRING(email, CHARINDEX(''@'', email) + 1, LEN(email))), 
                  LEN(SUBSTRING(email, CHARINDEX(''@'', email) + 1, LEN(email)))) AS email,
        subject,
        CONVERT(date, submission_date) AS submission_date,
        processed,
        processed_date
    FROM contact_submissions
    ');
    PRINT 'Created safe view for reporting';
END
GO

-- Create a stored procedure to safely insert submissions
IF EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[sp_insert_submission]') AND type in (N'P'))
BEGIN
    DROP PROCEDURE [dbo].[sp_insert_submission];
    PRINT 'Dropped existing sp_insert_submission procedure';
END
GO

CREATE PROCEDURE [dbo].[sp_insert_submission]
    @name NVARCHAR(100),
    @student_id NVARCHAR(20) = NULL,
    @email NVARCHAR(120),
    @subject NVARCHAR(200),
    @details NVARCHAR(MAX),
    @ip_address VARCHAR(45) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Validate inputs
    IF LEN(@name) = 0 OR LEN(@name) > 100
    BEGIN
        RAISERROR('Invalid name', 16, 1);
        RETURN;
    END
    
    IF @student_id IS NOT NULL AND (LEN(@student_id) < 7 OR LEN(@student_id) > 20)
    BEGIN
        RAISERROR('Invalid student ID', 16, 1);
        RETURN;
    END
    
    IF LEN(@email) = 0 OR LEN(@email) > 120 OR @email NOT LIKE '%@%.%'
    BEGIN
        RAISERROR('Invalid email', 16, 1);
        RETURN;
    END
    
    IF LEN(@subject) = 0 OR LEN(@subject) > 200
    BEGIN
        RAISERROR('Invalid subject', 16, 1);
        RETURN;
    END
    
    IF LEN(@details) = 0 OR LEN(@details) > 4000
    BEGIN
        RAISERROR('Invalid details', 16, 1);
        RETURN;
    END
    
    -- Insert submission
    INSERT INTO contact_submissions (name, student_id, email, subject, details, submission_date, ip_address)
    VALUES (@name, @student_id, @email, @subject, @details, GETDATE(), @ip_address);
    
    -- Log successful attempt
    IF @ip_address IS NOT NULL
    BEGIN
        INSERT INTO submission_attempts (ip_address, success)
        VALUES (@ip_address, 1);
    END
END
GO

PRINT 'Successfully created sp_insert_submission stored procedure';
GO

-- Create admin user to manage access (don't use this user in the application)
IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = 'contact_admin')
BEGIN
    CREATE USER [contact_admin] WITHOUT LOGIN;
    GRANT SELECT, INSERT, UPDATE ON [dbo].[contact_submissions] TO [contact_admin];
    GRANT SELECT ON [dbo].[vw_contact_submissions_safe] TO [contact_admin];
    GRANT EXECUTE ON [dbo].[sp_insert_submission] TO [contact_admin];
    PRINT 'Created contact_admin database user';
END
GO

-- Create application user with limited permissions
IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = 'contact_app')
BEGIN
    CREATE USER [contact_app] WITHOUT LOGIN;
    GRANT EXECUTE ON [dbo].[sp_insert_submission] TO [contact_app];
    GRANT SELECT ON [dbo].[vw_contact_submissions_safe] TO [contact_app];
    PRINT 'Created contact_app database user with limited permissions';
END
GO

PRINT 'Database setup complete';
GO