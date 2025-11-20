from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from db_connect import connection, get_connection
from functools import wraps
from datetime import datetime
import requests
import hashlib
import logging
import os
import csv
import io
from config import Config

#added comment to test DEMO#
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fallback_secret")


# Asset redirect routes for Squarespace-style paths
# These map /css/, /js/, /images/, /assets/ to Flask's static folder
@app.route('/css/<path:filename>')
def serve_css(filename):
    return send_from_directory('static/css', filename)

@app.route('/js/<path:filename>')
def serve_js(filename):
    return send_from_directory('static/js', filename)

@app.route('/images/<path:filename>')
def serve_images(filename):
    return send_from_directory('static/images', filename)

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory('static/assets', filename)

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Zapier webhook helper function
def send_to_zapier(evaluation_id):
    """
    Send evaluation data to Zapier webhook after a peer evaluation is submitted.
    Uses signature-based authentication for security.
    
    Args:
        evaluation_id: The PeerEvalID of the evaluation record
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Query the evaluation data with all related information
        cursor = connection.cursor()
        cursor.execute("""
            SELECT 
                p.StudentEvaluator,
                p.CourseID,
                e1.Email AS evaluator_email,
                e2.Email AS evaluatee_email,
                CONCAT(c.CourseCode, '-', c.Semester, '-', c.Year, '-', REPLACE(c.CourseTime, ' ', '')) AS course_id,
                p.Contribution,
                p.Collaboration,
                p.Communication,
                p.Planning,
                p.Inclusivity,
                p.Overall
            FROM peerevaluation p
            JOIN student e1 ON p.StudentEvaluator = e1.StudentID
            JOIN student e2 ON p.StudentEvaluatee = e2.StudentID
            JOIN course c ON p.CourseID = c.CourseID
            WHERE p.PeerEvalID = %s
        """, (evaluation_id,))
        
        result = cursor.fetchone()
        cursor.close()
        
        if not result:
            print(f"ERROR: No evaluation found with PeerEvalID {evaluation_id}")
            return False
        
        # Extract data from query result
        student_id = result[0]
        course_id = result[1]
        
        # Build the payload dictionary
        data = {
            "student_id": student_id,
            "peer_eval_id": evaluation_id,
            "course_id": course_id,
            "event": "peer_evaluation_submitted",
            "evaluator_email": result[2],
            "evaluatee_email": result[3],
            "course_identifier": result[4],
            "contribution": result[5],
            "collaboration": result[6],
            "communication": result[7],
            "planning": result[8],
            "inclusivity": result[9],
            "overall": result[10]
        }
        
        # Generate signature for authentication
        secret = "smu_sched_pe_9f4c8d2b71e54c39"
        signature = hashlib.sha256(
            f"{data['student_id']}{data['peer_eval_id']}{secret}".encode()
        ).hexdigest()
        data["signature"] = signature
        
        # Send POST request to Zapier webhook
        zapier_webhook_url = "https://hooks.zapier.com/hooks/catch/24454226/us4sgr4/"
        response = requests.post(zapier_webhook_url, json=data, timeout=5)
        response.raise_for_status()
        
        print("✅ Zapier webhook triggered successfully after peer evaluation submission.")
        print(f"   Student ID: {student_id} | PeerEvalID: {evaluation_id} | CourseID: {course_id}")
        return True
            
    except Exception as e:
        print(f"⚠️ Zapier webhook error: {e}")
        return False

# Home route
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('home'))

@app.route('/confirmation-screens')
@login_required
def confirmation_screens():
    return render_template('confirmation-screens.html')

@app.route('/confirmation-screens-2')
def confirmation_screens_2():
    return render_template('confirmation-screens-2.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            email = request.form['email']
            password = request.form['password']
            
            # First, check if email exists in student table
            cursor = connection.cursor()
            cursor.execute("SELECT StudentID, Name, Email FROM student WHERE Email = %s", (email,))
            student = cursor.fetchone()
            
            if student:
                # Student found, create session
                session['user_id'] = student[0]  # StudentID
                session['user_name'] = student[1]  # Name
                session['user_email'] = student[2]  # Email
                session['user_type'] = 'student'
                session['logged_in'] = True
                cursor.close()
                
                flash('Login successful! Welcome back.', 'success')
                return redirect(url_for('student_dashboard'))
            
            # If not found in student table, check professor table
            cursor.execute("SELECT ProfessorID, Name, Email, Department FROM professor WHERE Email = %s AND Password = %s", (email, password))
            professor = cursor.fetchone()
            cursor.close()
            
            if professor:
                # Professor found, create session
                session['professor_id'] = professor[0]  # ProfessorID
                session['name'] = professor[1]  # Name
                session['user_email'] = professor[2]  # Email
                session['department'] = professor[3]  # Department
                session['user_type'] = 'professor'
                session['logged_in'] = True
                
                flash('Login successful! Welcome, Professor.', 'success')
                return redirect(url_for('professor_dashboard'))
            
            # No match in either table
            flash('Invalid email or password. Please try again.', 'error')
            return render_template('login.html')
                
        except Exception as e:
            flash(f'Login error: {str(e)}', 'error')
            return render_template('login.html')
    
    return render_template('login.html')

@app.route('/get-started', methods=['GET', 'POST'])
def get_started():
    if request.method == 'POST':
        try:
            # Get form data from the existing form in get-started.html
            fname = request.form['fname']
            lname = request.form['lname']
            email = request.form['email']
            
            # Combine first and last name
            full_name = f"{fname} {lname}"
            
            # Insert student data into the database
            cursor = connection.cursor()
            
            # Try the standard insert first
            try:
                cursor.execute("INSERT INTO student (Name, Email) VALUES (%s, %s)", (full_name, email))
            except Exception as db_error:
                # If StudentID auto-increment is not working, try with explicit NULL
                if "doesn't have a default value" in str(db_error):
                    cursor.execute("INSERT INTO student (StudentID, Name, Email) VALUES (NULL, %s, %s)", (full_name, email))
                else:
                    raise db_error
            
            connection.commit()
            cursor.close()
            
            flash('Account created successfully! You can now log in.', 'success')
            return redirect(url_for('home'))
            
        except Exception as e:
            flash(f'Error creating account: {str(e)}', 'error')
            return render_template('get-started.html')
    
    return render_template('get-started.html')

@app.route('/peer_evaluation/<int:peer_eval_id>', methods=['GET', 'POST'])
@login_required
def peer_evaluation(peer_eval_id):
    print(f"PEER EVAL: Loaded route with PeerEvalID={peer_eval_id}")
    student_id = session.get('user_id')
    
    # POST: Submit evaluation
    if request.method == 'POST':
        try:
            print(f"POST: Submitting evaluation for PeerEvalID={peer_eval_id}")
            
            # Server-side validation: Check all required fields
            required_fields = ['contribution', 'collaboration', 'planning', 'communication', 'inclusivity', 'overall']
            values = {}
            
            for field in required_fields:
                raw = request.form.get(field)
                
                # Check if field is missing or empty
                if raw is None or raw == '':
                    print(f"VALIDATION ERROR: Missing field '{field}'")
                    flash("Please complete all questions before submitting.", 'error')
                    return redirect(url_for('peer_evaluation', peer_eval_id=peer_eval_id))
                
                # Convert to integer and validate range
                try:
                    v = int(raw)
                    if v < 0 or v > 4:
                        print(f"VALIDATION ERROR: Field '{field}' value {v} out of range")
                        flash("Ratings must be between 0 and 4.", 'error')
                        return redirect(url_for('peer_evaluation', peer_eval_id=peer_eval_id))
                    values[field] = v
                except ValueError:
                    print(f"VALIDATION ERROR: Field '{field}' is not a valid integer")
                    flash("Invalid rating value provided.", 'error')
                    return redirect(url_for('peer_evaluation', peer_eval_id=peer_eval_id))
            
            print(f"VALIDATION PASSED: All fields valid for PeerEvalID={peer_eval_id}")
            
            # Simple UPDATE by PeerEvalID
            cursor = connection.cursor()
            cursor.execute("""
                UPDATE peerevaluation
                SET Contribution = %s, Collaboration = %s, Communication = %s,
                    Planning = %s, Inclusivity = %s, Overall = %s
                WHERE PeerEvalID = %s
            """, (values['contribution'], values['collaboration'], values['communication'], 
                  values['planning'], values['inclusivity'], values['overall'], peer_eval_id))
            
            rows_updated = cursor.rowcount
            print(f"ROWS UPDATED: {rows_updated}")
            
            connection.commit()
            cursor.close()
            
            # Send to Zapier
            zapier_success = send_to_zapier(peer_eval_id)
            if not zapier_success:
                print("Warning: Zapier webhook failed, but evaluation saved")
            
            flash('Evaluation submitted successfully!', 'success')
            return redirect(url_for('confirmation_screens'))
            
        except Exception as e:
            print(f"POST ERROR: {e}")
            import traceback
            traceback.print_exc()
            flash('There was a problem saving your evaluation. Please try again.', 'error')
            return redirect(url_for('peer_evaluation', peer_eval_id=peer_eval_id))
    
    # GET: Load evaluation form
    try:
        print(f"GET: Loading form for PeerEvalID={peer_eval_id}")
        cursor = connection.cursor()
        cursor.execute("""
            SELECT
                s.Name AS EvaluateeName,
                c.CourseCode,
                c.CourseName,
                c.CourseTime,
                p.EvalDueDate
            FROM peerevaluation p
            JOIN student s ON p.StudentEvaluatee = s.StudentID
            JOIN course c ON p.CourseID = c.CourseID
            WHERE p.PeerEvalID = %s
        """, (peer_eval_id,))
        
        eval_data = cursor.fetchone()
        cursor.close()
        
        if not eval_data:
            print(f"GET ERROR: No data found for PeerEvalID={peer_eval_id}")
            flash('Invalid evaluation ID.', 'error')
            return redirect(url_for('student_dashboard'))
        
        evaluation = {
            'PeerEvalID': peer_eval_id,
            'EvaluateeName': eval_data[0],
            'CourseCode': eval_data[1],
            'CourseName': eval_data[2],
            'CourseTime': eval_data[3],
            'EvalDueDate': eval_data[4]
        }
        
        print(f"GET SUCCESS: Rendering form for {evaluation['EvaluateeName']}")
        return render_template('peer-evaluation.html', evaluation=evaluation)
        
    except Exception as e:
        print(f"GET ERROR: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading evaluation form.', 'error')
        return redirect(url_for('student_dashboard'))

@app.route('/student-dashboard')
@login_required
def student_dashboard():
    try:
        # Get the logged-in student's ID from session
        student_id = session.get('user_id')
        
        # Query evaluations for the logged-in student (Sprint 1: Show ALL assignments)
        cursor = connection.cursor()
        cursor.execute("""
            SELECT
                p.PeerEvalID,
                c.CourseCode,
                c.CourseName,
                c.CourseTime,
                s.Name AS EvaluateeName,
                p.EvalDueDate
            FROM peerevaluation p
            JOIN student s ON p.StudentEvaluatee = s.StudentID
            JOIN course c ON p.CourseID = c.CourseID
            WHERE p.StudentEvaluator = %s
            ORDER BY COALESCE(p.EvalDueDate, '2999-12-31') ASC
        """, (student_id,))
        
        print(f"DASHBOARD: Fetching evaluations for student {student_id}")
        
        evaluations = cursor.fetchall()
        cursor.close()
        
        print(f"DASHBOARD: Found {len(evaluations)} evaluations")
        for i, eval in enumerate(evaluations):
            print(f"  [{i}] PeerEvalID={eval[0]}, {eval[1]} - {eval[2]}, Evaluatee={eval[4]}")
        
        return render_template('student-dashboard.html', evaluations=evaluations)
        
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return render_template('student-dashboard.html', 
                             evaluations=[],
                             student_name=session.get('user_name'),
                             evaluation_count=0)

@app.route('/team')
def team():
    return render_template('team.html')

# Professor dashboard - View and manage peer evaluations
@app.route('/professor-dashboard')
def professor_dashboard():
    # Check if professor is logged in
    if 'professor_id' not in session:
        flash('Please log in to access the professor dashboard.', 'error')
        return redirect(url_for('login'))
    
    try:
        # Fetch courses assigned to this professor
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM course WHERE ProfessorID = %s", (session['professor_id'],))
        courses = cursor.fetchall()
        cursor.close()
        
        return render_template('professor-dashboard.html', courses=courses)
    except Exception as e:
        flash(f'Error loading courses: {str(e)}', 'error')
        return render_template('professor-dashboard.html', courses=[])

# Assign peer evaluation - Create new evaluation assignments
@app.route('/assign-evaluations', methods=['GET', 'POST'])
def assign_evaluations():
    # Get course_id from URL parameter or form
    course_id = request.args.get('course_id') or request.form.get('course_id')
    print("DEBUG: CourseID from request =", course_id)  # <--- DEBUG
    
    # Validate course_id exists
    if not course_id:
        flash('Missing course ID.', 'error')
        return redirect(url_for('professor_dashboard'))
    
    # Fetch course details from database
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM course WHERE CourseID = %s", (course_id,))
    course = cursor.fetchone()
    cursor.close()
    
    # If no course found, show error
    if not course:
        print("DEBUG: No course found for CourseID =", course_id)
        flash('Course not found.', 'error')
        return redirect(url_for('professor_dashboard'))
    
    # Handle form submission
    if request.method == 'POST':
        print("DEBUG: POST reached:", request.form)  # <--- DEBUG
        raw_due_date = request.form.get('due_date')
        raw_time = request.form.get('time')
        print("DEBUG: Raw due date from form =", raw_due_date)  # <--- DEBUG
        print("DEBUG: Raw time from form =", raw_time)  # <--- DEBUG
        
        # Convert browser input to yyyy-mm-dd format for MySQL
        try:
            if '/' in raw_due_date:
                formatted_due_date = datetime.strptime(raw_due_date, '%m/%d/%Y').strftime('%Y-%m-%d')
            else:
                formatted_due_date = datetime.strptime(raw_due_date, '%Y-%m-%d').strftime('%Y-%m-%d')
        except Exception as e:
            print("DEBUG: Date parsing error ->", e)
            flash('Invalid date format.', 'error')
            return redirect(request.url)
        
        print("DEBUG: Formatted due date =", formatted_due_date)  # <--- DEBUG
        
        # Update the database
        cursor = connection.cursor()
        cursor.execute("UPDATE course SET EvalDueDate = %s WHERE CourseID = %s", (formatted_due_date, course_id))
        connection.commit()
        
        print("DEBUG: Rows affected =", cursor.rowcount)  # <--- DEBUG
        cursor.close()
        
        # Trigger Zapier webhook to notify all students enrolled in this course
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT s.Email AS StudentEmail
                FROM student s
                JOIN enrollment e ON s.StudentID = e.StudentID
                WHERE e.CourseID = %s
            """, (course_id,))
            student_emails = [row['StudentEmail'] for row in cursor.fetchall()]
            cursor.close()
            
            # Capture due_time from form (even if not stored in database)
            eval_due_time = request.form.get('time') or request.form.get('eval_due_time')
            
            # Build the Zapier payload using the new simplified structure
            data = {
                "secret_key": "smu_sched_pe_9f4c8d2b71e54c39",
                "course_id": int(course_id),
                "due_date": formatted_due_date,
                "due_time": eval_due_time if eval_due_time else "",
                "student_emails": student_emails
            }
            
            # Send POST request to Zapier
            zapier_webhook_url = "https://hooks.zapier.com/hooks/catch/24454226/us4sgr4/"
            response = requests.post(zapier_webhook_url, json=data, timeout=5)
            response.raise_for_status()
            
            print(f"✅ Zapier webhook triggered for course {course_id} — notifying {len(student_emails)} students.")
            
        except Exception as e:
            print(f"⚠️ Zapier webhook error: {e}")
        
        flash('Evaluation due date successfully updated!', 'success')
        
        # Redirect to static evaluation-analysis page
        print("DEBUG: Redirecting to evaluation-analysis (static page)")  # <--- DEBUG
        return redirect(url_for('evaluation_analysis'))
    
    # GET request: render the form
    return render_template('confirmation-screens-1.html', course=course)

# Evaluation analysis - View and analyze evaluation results
@app.route('/evaluation-analysis')
def evaluation_analysis():
    """
    Static evaluation analysis page — temporarily disabled dynamic database logic.
    This route should always render the page directly.
    """
    return render_template('evaluation-analysis.html')

@app.route('/import-course-roster', methods=['GET', 'POST'])
def import_course_roster():
    # Check if professor is logged in
    if 'professor_id' not in session:
        flash('Please log in to access this page.', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Get form data
        course_code = request.form.get('course_code')
        csv_file = request.files.get('csv_file')
        
        # Validate inputs
        if not course_code:
            flash('Course code is required.', 'error')
            return redirect(request.url)
        
        if not csv_file or csv_file.filename == '':
            flash('No file selected.', 'error')
            return redirect(request.url)
        
        try:
            # Read CSV file content
            # Decode the file stream to handle encoding properly
            stream = io.TextIOWrapper(csv_file.stream, encoding='utf-8-sig')  # utf-8-sig handles BOM
            
            # Parse CSV using DictReader
            reader = csv.DictReader(stream)
            
            # Get database connection
            cursor = connection.cursor()
            
            # Check if course exists, if not create it
            cursor.execute("SELECT CourseID FROM course WHERE CourseCode = %s", (course_code,))
            course_row = cursor.fetchone()
            
            if not course_row:
                # Course doesn't exist, create it
                cursor.execute(
                    "INSERT INTO course (CourseCode, ProfessorID) VALUES (%s, %s)",
                    (course_code, session['professor_id'])
                )
                connection.commit()
                course_id = cursor.lastrowid
                print(f"Created new course: {course_code} with CourseID: {course_id}")
            else:
                course_id = course_row[0]
                print(f"Found existing course: {course_code} with CourseID: {course_id}")
            
            # Process each row in the CSV
            students_added = 0
            enrollments_added = 0
            
            for row in reader:
                # Extract data from CSV row
                # Handle potential column name variations (case-insensitive)
                student_id = None
                name = None
                email = None
                
                for key, value in row.items():
                    key_lower = key.strip().lower()
                    if 'student' in key_lower and 'id' in key_lower:
                        student_id = value.strip()
                    elif key_lower == 'name':
                        name = value.strip()
                    elif key_lower == 'email':
                        email = value.strip()
                
                # Validate required fields
                if not student_id or not name or not email:
                    print(f"Warning: Skipping row with missing data: {row}")
                    continue
                
                # Check if student exists, if not create them
                cursor.execute("SELECT StudentID FROM student WHERE StudentID = %s", (student_id,))
                if not cursor.fetchone():
                    cursor.execute(
                        "INSERT INTO student (StudentID, Name, Email) VALUES (%s, %s, %s)",
                        (student_id, name, email)
                    )
                    students_added += 1
                    print(f"Added new student: {name} (ID: {student_id})")
                else:
                    print(f"Student already exists: {name} (ID: {student_id})")
                
                # Create enrollment record (INSERT IGNORE to avoid duplicates)
                cursor.execute(
                    "INSERT IGNORE INTO enrollment (CourseID, StudentID) VALUES (%s, %s)",
                    (course_id, student_id)
                )
                if cursor.rowcount > 0:
                    enrollments_added += 1
                    print(f"Enrolled student {student_id} in course {course_code}")
            
            # Commit all changes
            connection.commit()
            cursor.close()
            
            flash(f'Roster imported successfully! Added {students_added} new students and {enrollments_added} enrollments.', 'success')
            print(f"Import complete: {students_added} students added, {enrollments_added} enrollments created")
            
            # Store course_id in session for groups-in-your-class page
            session['selected_course_id'] = course_id
            
            return redirect(url_for('creating_groups', course_id=course_id))
            
        except csv.Error as e:
            flash(f'Error reading CSV file: {str(e)}', 'error')
            print(f"CSV parsing error: {e}")
            return redirect(request.url)
        except Exception as e:
            # Rollback on any error
            connection.rollback()
            flash(f'Error processing file: {str(e)}', 'error')
            print(f"Error processing roster: {e}")
            import traceback
            traceback.print_exc()
            return redirect(request.url)
    
    # GET request: render the form
    return render_template('import-course-roster.html')

@app.route('/creating-groups/<int:course_id>', methods=['GET', 'POST'])
def creating_groups(course_id):
    # Check if professor is logged in
    if 'professor_id' not in session:
        flash('Please log in to access this page.', 'error')
        return redirect(url_for('login'))
    
    # Handle POST form submission
    if request.method == 'POST':
        conn = None
        cursor = None
        try:
            # Get form data
            selected_group_name = request.form.get('group_select')
            selected_students = request.form.getlist('student_select')
            
            if not selected_group_name:
                flash('Please select a group.', 'error')
                return redirect(url_for('creating_groups', course_id=course_id))
            
            if not selected_students:
                flash('Please select at least one student.', 'error')
                return redirect(url_for('creating_groups', course_id=course_id))
            
            # Get database connection
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Get CourseCode to format group name
            cursor.execute("SELECT CourseCode FROM course WHERE CourseID = %s", (course_id,))
            course_result = cursor.fetchone()
            course_code = course_result['CourseCode'] if course_result and course_result.get('CourseCode') else None
            
            if not course_code:
                course_code = "UnknownCourse"
            
            # Extract group number from selected_group_name (e.g., "Group 1" -> "1")
            import re
            match = re.search(r'(\d+)', selected_group_name)
            group_number = match.group(1) if match else None
            
            if not group_number:
                flash('Could not determine group number.', 'error')
                return redirect(url_for('creating_groups', course_id=course_id))
            
            # Format group name as {CourseCode}-Group{number}
            formatted_group_name = f"{course_code}-Group{group_number}"
            
            # 1️⃣ Generate a unique GroupID
            cursor.execute("SELECT MAX(GroupID) AS MaxGroupID FROM studentgroup")
            result = cursor.fetchone()
            next_group_id = (result['MaxGroupID'] or 999) + 1  # start from 1000 if none exist
            
            # 2️⃣ Check if group already exists for this course
            cursor.execute("SELECT GroupID FROM studentgroup WHERE CourseID = %s AND GroupName = %s", 
                         (course_id, formatted_group_name))
            existing_group = cursor.fetchone()
            
            if existing_group:
                group_id = existing_group['GroupID']
            else:
                cursor.execute("INSERT INTO studentgroup (GroupID, CourseID, GroupName) VALUES (%s, %s, %s)", 
                             (next_group_id, course_id, formatted_group_name))
                group_id = next_group_id
            
            # 3️⃣ Add students to groupmembers (prevent duplicates)
            students_added = 0
            for student_id in selected_students:
                if student_id:  # Skip empty values
                    cursor.execute("SELECT * FROM groupmembers WHERE GroupID = %s AND StudentID = %s", 
                                 (group_id, student_id))
                    if not cursor.fetchone():
                        cursor.execute("INSERT INTO groupmembers (GroupID, StudentID) VALUES (%s, %s)", 
                                     (group_id, student_id))
                        students_added += 1
            
            conn.commit()
            
            # Store course_id in session for groups-in-your-class page
            session['selected_course_id'] = course_id
            
            # Prepare success message
            success_message = f"✅ {formatted_group_name} successfully created!"
            
            # Re-fetch course and students for template rendering
            cursor.execute("SELECT CourseCode FROM course WHERE CourseID = %s", (course_id,))
            course = cursor.fetchone()
            
            cursor.execute("""
                SELECT s.StudentID, s.Name
                FROM student s
                JOIN enrollment e ON s.StudentID = e.StudentID
                WHERE e.CourseID = %s
                ORDER BY s.Name ASC
            """, (course_id,))
            students = cursor.fetchall()
            
            return render_template('creating-groups.html', 
                                 course=course, 
                                 students=students, 
                                 course_id=course_id,
                                 success_message=success_message)
            
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Error processing form submission: {e}")
            import traceback
            traceback.print_exc()
            
            # Re-fetch course and students for template rendering
            try:
                if not conn:
                    conn = get_connection()
                if not cursor:
                    cursor = conn.cursor(dictionary=True)
                
                cursor.execute("SELECT CourseCode FROM course WHERE CourseID = %s", (course_id,))
                course = cursor.fetchone()
                
                cursor.execute("""
                    SELECT s.StudentID, s.Name
                    FROM student s
                    JOIN enrollment e ON s.StudentID = e.StudentID
                    WHERE e.CourseID = %s
                    ORDER BY s.Name ASC
                """, (course_id,))
                students = cursor.fetchall()
                
                return render_template('creating-groups.html', 
                                     course=course, 
                                     students=students, 
                                     course_id=course_id,
                                     error_message=f'Error creating group: {str(e)}')
            except Exception as e2:
                print(f"Error loading template after error: {e2}")
                return redirect(url_for('creating_groups', course_id=course_id))
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    # Handle GET request - display the form
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Fetch course info
        cursor.execute("SELECT CourseCode FROM course WHERE CourseID = %s", (course_id,))
        course = cursor.fetchone()
        
        if not course:
            flash('Course not found.', 'error')
            return redirect(url_for('professor_dashboard'))
        
        # Fetch all enrolled students
        cursor.execute("""
            SELECT s.StudentID, s.Name
            FROM student s
            JOIN enrollment e ON s.StudentID = e.StudentID
            WHERE e.CourseID = %s
            ORDER BY s.Name ASC
        """, (course_id,))
        students = cursor.fetchall()
        
        return render_template('creating-groups.html', course=course, students=students, course_id=course_id)
        
    except Exception as e:
        print(f"Error loading creating-groups page: {e}")
        flash(f'Error loading course data: {str(e)}', 'error')
        import traceback
        traceback.print_exc()
        return redirect(url_for('professor_dashboard'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/groups-in-your-class')
def groups_in_your_class():
    # Check if professor is logged in
    if 'professor_id' not in session:
        flash('Please log in to access this page.', 'error')
        return redirect(url_for('login'))
    
    conn = None
    cursor = None
    try:
        professor_id = session.get('professor_id')
        # Get course_id from session or query parameters
        course_id = session.get('selected_course_id') or request.args.get('course_id')
        
        if not course_id:
            flash('No course selected. Please import a course roster or create groups first.', 'error')
            return redirect(url_for('professor_dashboard'))
        
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get selected course info
        cursor.execute("""
            SELECT CourseID, CourseCode
            FROM course
            WHERE CourseID = %s AND ProfessorID = %s
        """, (course_id, professor_id))
        course = cursor.fetchone()
        
        if not course:
            flash('Course not found or not assigned to this professor.', 'error')
            return redirect(url_for('professor_dashboard'))
        
        # Fetch all groups for this course
        cursor.execute("""
            SELECT GroupID, GroupName
            FROM studentgroup
            WHERE CourseID = %s
            ORDER BY GroupName ASC
        """, (course_id,))
        groups = cursor.fetchall()
        
        all_groups = []
        for group in groups:
            group_id = group['GroupID']
            
            # Get students in each group
            cursor.execute("""
                SELECT s.StudentID, s.Name
                FROM groupmembers gm
                JOIN student s ON gm.StudentID = s.StudentID
                WHERE gm.GroupID = %s
                ORDER BY s.Name ASC
            """, (group_id,))
            students = cursor.fetchall()
            
            all_groups.append({
                'GroupName': group['GroupName'],
                'GroupID': group_id,
                'Students': students
            })
        
        return render_template(
            'groups-in-your-class.html',
            course=course,
            all_groups=all_groups
        )
        
    except Exception as e:
        print(f"Error loading groups-in-your-class: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Error loading groups: {str(e)}', 'error')
        return render_template('groups-in-your-class.html', course=None, all_groups=[])
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        try:
            name = request.form['name']
            email = request.form['email']
            
            # Insert student data into the database
            cursor = connection.cursor()
            cursor.execute("INSERT INTO student (Name, Email) VALUES (%s, %s)", (name, email))
            connection.commit()
            cursor.close()
            
            flash('Account created successfully! You can now log in.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            flash(f'Error creating account: {str(e)}', 'error')
            return render_template('signup.html')
    
    return render_template('signup.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5002))
    app.run(host='0.0.0.0', port=port, debug=True)
