from flask import Flask, render_template, request, make_response, session
from datetime import datetime, timedelta
from xhtml2pdf import pisa
from io import BytesIO
import os
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

def get_intervals(age_months):
    if age_months < 3:
        return 3, 2, None   # milk hrs, diaper hrs, food interval None
    elif age_months < 5:
        return 4, 3, None
    elif age_months < 7:
        return 5, 4, 4  # food every 4 hrs (sample recommendation)
    else:
        return 6, 4, 4

def generate_schedule(last_milk, last_diaper, last_food, age_months):
    milk_interval, diaper_interval, food_interval = get_intervals(age_months)
    schedule = []
    today = last_milk.date()
    end_day = last_milk.replace(hour=23, minute=59)
    next_milk = last_milk
    next_diaper = last_diaper
    next_food = last_food if food_interval else None
    while True:
        times_to_consider = []
        if next_milk <= end_day and not (0 <= next_milk.hour < 6):
            times_to_consider.append((next_milk, "Milk"))
        if next_diaper <= end_day and not (0 <= next_diaper.hour < 6):
            times_to_consider.append((next_diaper, "Diaper"))
        if food_interval and next_food and next_food <= end_day and not (0 <= next_food.hour < 6):
            times_to_consider.append((next_food, "Food"))
        if not times_to_consider:
            break
        for t, kind in times_to_consider:
            schedule.append((t, kind))
        next_milk += timedelta(hours=milk_interval)
        next_diaper += timedelta(hours=diaper_interval)
        if food_interval and next_food:
            next_food += timedelta(hours=food_interval)
    schedule.sort(key=lambda x: x[0])
    return schedule

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        age_months = int(request.form["age"])
        milk_time_str = request.form["milk_time"]
        diaper_time_str = request.form["diaper_time"]
        food_time_str = request.form.get("food_time") if age_months >= 5 else None

        today = datetime.today()
        milk_time = datetime.strptime(milk_time_str, "%H:%M").replace(year=today.year, month=today.month, day=today.day)
        diaper_time = datetime.strptime(diaper_time_str, "%H:%M").replace(year=today.year, month=today.month, day=today.day)
        food_time = None
        if food_time_str:
            food_time = datetime.strptime(food_time_str, "%H:%M").replace(year=today.year, month=today.month, day=today.day)

        schedule = generate_schedule(milk_time, diaper_time, food_time, age_months)
        session['milk_time'] = milk_time_str
        session['diaper_time'] = diaper_time_str
        session['food_time'] = food_time_str if food_time_str else ''
        session['age'] = age_months
        return render_template("schedule.html", 
                               schedule=schedule, 
                               age=age_months,
                               milk_time=milk_time_str,
                               diaper_time=diaper_time_str,
                               food_time=food_time_str)
    return render_template("index.html")

@app.route("/pdf")
def pdf():
    age = int(session.get('age') or request.args.get("age", 0))
    milk_time_str = session.get('milk_time') or request.args.get("milk")
    diaper_time_str = session.get('diaper_time') or request.args.get("diaper")
    food_time_str = session.get('food_time') or request.args.get("food") if age >= 5 else None
    if not milk_time_str or not diaper_time_str:
        return "Missing parameters for PDF generation", 400
    today = datetime.today()
    milk = datetime.strptime(milk_time_str, "%H:%M").replace(year=today.year, month=today.month, day=today.day)
    diaper = datetime.strptime(diaper_time_str, "%H:%M").replace(year=today.year, month=today.month, day=today.day)
    food = None
    if food_time_str:
        food = datetime.strptime(food_time_str, "%H:%M").replace(year=today.year, month=today.month, day=today.day)
    schedule = generate_schedule(milk, diaper, food, age)
    html = render_template("pdf.html", 
                          schedule=schedule, 
                          age=age,
                          milk_time=milk_time_str,
                          diaper_time=diaper_time_str,
                          food_time=food_time_str,
                          today=today)
    pdf_buffer = BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=pdf_buffer)
    if pisa_status.err:
        return "Error generating PDF", 500
    pdf_buffer.seek(0)
    pdf_data = pdf_buffer.getvalue()
    pdf_buffer.close()
    response = make_response(pdf_data)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=baby_schedule.pdf"
    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)