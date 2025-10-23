from flask import Flask, render_template, request, redirect, url_for, flash, session
from db_connect import connection
from functools import wraps

app = Flask(__name__)
app.secret_key = '23320398123'  # Required for flash messages

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            email = request.form['email']
            password = request.form['password']  # We'll use this for future password functionality
            
            # Check if email exists in the database
            cursor = connection.cursor()
            cursor.execute("SELECT StudentID, Name, Email FROM student WHERE Email = %s", (email,))
            student = cursor.fetchone()
            cursor.close()
            
            if student:
                # Email exists, create session
                session['user_id'] = student[0]  # StudentID
                session['user_name'] = student[1]  # Name
                session['user_email'] = student[2]  # Email
                session['logged_in'] = True
                
                flash('Login successful! Welcome back.', 'success')
                return redirect(url_for('student_dashboard'))
            else:
                # Email doesn't exist
                flash('Email not found. Please check your email or sign up for an account.', 'error')
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

@app.route('/peer-evaluation', methods=['GET', 'POST'])
@login_required
def peer_evaluation():
    if request.method == 'POST':
        try:
            # Debug: Print all form data
            print("DEBUG: Form data received:")
            for key, value in request.form.items():
                print(f"  {key}: {value}")
            
            # Debug: Print request method and content type
            print(f"DEBUG: Request method: {request.method}")
            print(f"DEBUG: Content type: {request.content_type}")
            print(f"DEBUG: Form keys: {list(request.form.keys())}")
            
            # Get form data
            contribution = request.form.get('contribution')
            collaboration = request.form.get('collaboration')
            communication = request.form.get('communication')
            planning = request.form.get('planning')
            inclusivity = request.form.get('inclusivity')
            overall = request.form.get('overall')
            evaluatee = request.form.get('evaluatee')
            student_id = session.get('user_id')
            
            # Debug: Print retrieved values
            print(f"DEBUG: Retrieved values:")
            print(f"  contribution: {contribution}")
            print(f"  collaboration: {collaboration}")
            print(f"  communication: {communication}")
            print(f"  planning: {planning}")
            print(f"  inclusivity: {inclusivity}")
            print(f"  overall: {overall}")
            print(f"  evaluatee: {evaluatee}")
            print(f"  student_id: {student_id}")
            
            # Validate that we have all required data
            if not all([contribution, collaboration, communication, planning, inclusivity, overall, evaluatee, student_id]):
                flash('Missing required form data. Please fill out all fields.', 'error')
                return redirect(url_for('peer_evaluation'))
            
            # Check database connection
            if not connection.is_connected():
                print("DEBUG: Database connection lost, attempting to reconnect...")
                connection.reconnect()
            
            # First, check if the evaluation record exists and get its current values
            cursor = connection.cursor()
            cursor.execute("""
                SELECT PeerEvalID, Contribution, Collaboration, Communication, Planning, Inclusivity, Overall 
                FROM peerevaluation 
                WHERE StudentEvaluator = %s AND StudentEvaluatee = %s
            """, (student_id, evaluatee))
            
            existing_record = cursor.fetchone()
            print(f"DEBUG: Existing record found: {existing_record}")
            
            if not existing_record:
                cursor.close()
                flash(f'No evaluation record found for evaluator {student_id} and evaluatee {evaluatee}. Please check your selection.', 'error')
                return redirect(url_for('peer_evaluation'))
            
            # Update the peerevaluation table
            
            # Debug: Print the SQL query and parameters
            print(f"DEBUG: Executing UPDATE query with parameters:")
            print(f"  StudentEvaluator: {student_id}")
            print(f"  StudentEvaluatee: {evaluatee}")
            print(f"  Contribution: {contribution}")
            print(f"  Collaboration: {collaboration}")
            print(f"  Communication: {communication}")
            print(f"  Planning: {planning}")
            print(f"  Inclusivity: {inclusivity}")
            print(f"  Overall: {overall}")
            
            try:
                cursor.execute("""
                    UPDATE peerevaluation
                    SET
                        Contribution = %s,
                        Collaboration = %s,
                        Communication = %s,
                        Planning = %s,
                        Inclusivity = %s,
                        Overall = %s
                    WHERE StudentEvaluator = %s AND StudentEvaluatee = %s
                """, (contribution, collaboration, communication, planning, inclusivity, overall, student_id, evaluatee))
            except Exception as db_error:
                print(f"DEBUG: Database error occurred: {str(db_error)}")
                cursor.close()
                flash(f'Database error: {str(db_error)}', 'error')
                return redirect(url_for('peer_evaluation'))
            
            # Check if any rows were affected
            rows_affected = cursor.rowcount
            print(f"DEBUG: Rows affected by update: {rows_affected}")
            
            connection.commit()
            cursor.close()
            
            if rows_affected > 0:
                flash('Evaluation submitted successfully!', 'success')
                return redirect(url_for('confirmation_screens'))
            else:
                flash('No evaluation record found to update. Please check your selection.', 'error')
                return redirect(url_for('peer_evaluation'))
            
        except Exception as e:
            print(f"DEBUG: Error occurred: {str(e)}")
            flash(f'Error submitting evaluation: {str(e)}', 'error')
            return redirect(url_for('peer_evaluation'))
    
    # GET request - load form data
    try:
        student_id = session.get('user_id')
        
        # Get evaluation data for the logged-in student
        cursor = connection.cursor()
        cursor.execute("""
            SELECT 
                p.PeerEvalID,
                s.StudentID AS EvaluateeID,
                s.Name AS EvaluateeName,
                c.CourseCode,
                c.CourseName,
                pr.Name AS ProfessorName,
                c.Semester,
                c.Year,
                c.CourseTime,
                p.EvalDueDate
            FROM peerevaluation p
            JOIN student s ON p.StudentEvaluatee = s.StudentID
            JOIN course c ON p.CourseID = c.CourseID
            JOIN professor pr ON c.ProfessorID = pr.ProfessorID
            WHERE p.StudentEvaluator = %s
        """, (student_id,))
        
        evaluations = cursor.fetchall()
        cursor.close()
        
        # Convert to list of dictionaries for easier template access
        evaluation_list = []
        evaluatees = []
        
        for eval_item in evaluations:
            evaluation_data = {
                'PeerEvalID': eval_item[0],
                'EvaluateeID': eval_item[1],
                'EvaluateeName': eval_item[2],
                'CourseCode': eval_item[3],
                'CourseName': eval_item[4],
                'ProfessorName': eval_item[5],
                'Semester': eval_item[6],
                'Year': eval_item[7],
                'CourseTime': eval_item[8],
                'EvalDueDate': eval_item[9]
            }
            evaluation_list.append(evaluation_data)
            evaluatees.append({
                'StudentID': eval_item[1],
                'Name': eval_item[2]
            })
        
        # Get the first evaluation's course info (assuming all evaluations are for the same course)
        course_info = evaluation_list[0] if evaluation_list else None
        
        return render_template('peer-evaluation.html', 
                             evaluations=evaluation_list,
                             evaluatees=evaluatees,
                             course=course_info)
        
    except Exception as e:
        flash(f'Error loading evaluation form: {str(e)}', 'error')
        return render_template('peer-evaluation.html', 
                             evaluations=[],
                             evaluatees=[],
                             course=None)

@app.route('/student-dashboard')
@login_required
def student_dashboard():
    try:
        # Get the logged-in student's ID from session
        student_id = session.get('user_id')
        
        # Query evaluations for the logged-in student
        cursor = connection.cursor()
        cursor.execute("""
            SELECT 
                p.PeerEvalID,
                c.CourseCode,
                c.CourseName,
                p.EvalDueDate
            FROM peerevaluation p
            JOIN course c ON p.CourseID = c.CourseID
            WHERE p.StudentEvaluator = %s
            ORDER BY COALESCE(p.EvalDueDate, '2999-12-31') ASC
        """, (student_id,))
        
        evaluations = cursor.fetchall()
        cursor.close()
        
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
    app.run(debug=True, port=5002)
