from flask import Flask, render_template, request, make_response, session
from datetime import datetime, timedelta
from xhtml2pdf import pisa
from io import BytesIO
import os
app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this for production!
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
def get_intervals(age_months):
    if age_months < 3:
        return 3, 2   # milk hrs, diaper hrs
    elif age_months < 6:
        return 4, 3
    else:
        return 5, 4

def generate_schedule(last_milk, last_diaper, age_months):
    milk_interval, diaper_interval = get_intervals(age_months)
    
    schedule = []
    end_day = last_milk.replace(hour=23, minute=59)
    
    next_milk = last_milk
    next_diaper = last_diaper
    
    while next_milk <= end_day or next_diaper <= end_day:
        if next_milk <= end_day and not (0 <= next_milk.hour < 6):
            schedule.append((next_milk, "Milk"))
            next_milk += timedelta(hours=milk_interval)
        else:
            next_milk += timedelta(hours=milk_interval)
        
        if next_diaper <= end_day and not (0 <= next_diaper.hour < 6):
            schedule.append((next_diaper, "Diaper"))
            next_diaper += timedelta(hours=diaper_interval)
        else:
            next_diaper += timedelta(hours=diaper_interval)
    
    schedule.sort(key=lambda x: x[0])
    return schedule

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        milk_time_str = request.form["milk_time"]
        diaper_time_str = request.form["diaper_time"]
        age_months = int(request.form["age"])
        
        milk_time = datetime.strptime(milk_time_str, "%H:%M")
        diaper_time = datetime.strptime(diaper_time_str, "%H:%M")
        
        today = datetime.today()
        milk_time = milk_time.replace(year=today.year, month=today.month, day=today.day)
        diaper_time = diaper_time.replace(year=today.year, month=today.month, day=today.day)
        
        schedule = generate_schedule(milk_time, diaper_time, age_months)
        
        # Store in session for PDF generation
        session['milk_time'] = milk_time_str
        session['diaper_time'] = diaper_time_str
        session['age'] = age_months
        
        return render_template("schedule.html", 
                               schedule=schedule, 
                               age=age_months,
                               milk_time=milk_time_str,
                               diaper_time=diaper_time_str)
    
    return render_template("index.html")

@app.route("/pdf")
def pdf():
    # Get parameters from session or query string
    milk_time_str = session.get('milk_time') or request.args.get("milk")
    diaper_time_str = session.get('diaper_time') or request.args.get("diaper")
    age = int(session.get('age') or request.args.get("age", 0))
    
    if not milk_time_str or not diaper_time_str:
        return "Missing parameters for PDF generation", 400
    
    milk = datetime.strptime(milk_time_str, "%H:%M")
    diaper = datetime.strptime(diaper_time_str, "%H:%M")
    today = datetime.today()
    
    milk = milk.replace(year=today.year, month=today.month, day=today.day)
    diaper = diaper.replace(year=today.year, month=today.month, day=today.day)
    
    schedule = generate_schedule(milk, diaper, age)
    
    html = render_template("pdf.html", 
                          schedule=schedule, 
                          age=age,
                          milk_time=milk_time_str,
                          diaper_time=diaper_time_str,
                          today=today)
    
    # Create PDF using xhtml2pdf
    pdf_buffer = BytesIO()
    
    # Convert HTML to PDF
    pisa_status = pisa.CreatePDF(html, dest=pdf_buffer)
    
    # Check for errors
    if pisa_status.err:
        return "Error generating PDF", 500
    
    # Get PDF value from buffer
    pdf_buffer.seek(0)
    pdf_data = pdf_buffer.getvalue()
    pdf_buffer.close()
    
    response = make_response(pdf_data)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=baby_schedule.pdf"
    return response

if __name__ == "__main__":
    # For Render deployment
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)