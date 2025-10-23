from flask import Flask, render_template, request, redirect, url_for, flash, session
from db_connect import connection
from functools import wraps
import requests
import logging

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

# Zapier webhook helper function
def send_to_zapier(evaluation_id):
    """
    Send evaluation data to Zapier webhook after a new record is inserted/updated.
    
    Args:
        evaluation_id: The EvaluationID (or PeerEvalID) of the evaluation record
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Query the evaluation data with all related information
        cursor = connection.cursor()
        cursor.execute("""
            SELECT 
                e1.Email AS evaluator_email,
                e2.Email AS evaluatee_email,
                CONCAT(c.course_code, '-', c.semester, '-', c.year, '-', REPLACE(c.course_time, ' ', '')) AS course_id,
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
        
        # Build the payload dictionary
        payload = {
            "evaluator_email": result[0],
            "evaluatee_email": result[1],
            "course_id": result[2],
            "contribution": result[3],
            "collaboration": result[4],
            "communication": result[5],
            "planning": result[6],
            "inclusivity": result[7],
            "overall": result[8],
            "webhook_secret": "smu_pe_6f9c1b3e2a6f4f1e"
        }
        
        # Send POST request to Zapier webhook
        webhook_url = "https://hooks.zapier.com/hooks/catch/24454226/ursjm8o/"
        response = requests.post(webhook_url, json=payload, timeout=30)
        
        print(f"Zapier response: {response.status_code} - {response.text}")
        
        if response.status_code == 200:
            print("Successfully sent evaluation data to Zapier webhook")
            return True
        else:
            print(f"Zapier webhook returned non-200 status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Error sending data to Zapier webhook: {str(e)}")
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
