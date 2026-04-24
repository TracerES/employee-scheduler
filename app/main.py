
from datetime import date, datetime, timedelta
import calendar
from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from .db import Base, engine, get_db
from .models import User, Shift, LeaveRequest
from .auth import create_session, read_session, SESSION_NAME
from .seed import seed_data

app = FastAPI(title="Employee Scheduler")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
Base.metadata.create_all(bind=engine)

@app.on_event("startup")
def startup():
    db = next(get_db())
    try: seed_data(db)
    finally: db.close()

def current_user(request, db):
    token = request.cookies.get(SESSION_NAME)
    if not token: return None
    data = read_session(token)
    if not data: return None
    return db.query(User).filter(User.id == data["user_id"]).first()

def week_dates():
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return [monday + timedelta(days=i) for i in range(7)]

def month_grid(anchor):
    return calendar.Calendar(firstweekday=0).monthdatescalendar(anchor.year, anchor.month)

@app.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if user: return RedirectResponse("/admin" if user.role=="admin" else "/employee", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": ""})

@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": ""})

@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user or user.password != password:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid email or password"})
    r = RedirectResponse("/admin" if user.role=="admin" else "/employee", status_code=303)
    r.set_cookie(SESSION_NAME, create_session(user.id, user.role, user.name), httponly=True)
    return r

@app.get("/logout")
def logout():
    r = RedirectResponse("/login", status_code=303)
    r.delete_cookie(SESSION_NAME)
    return r

@app.get("/admin")
def admin(request: Request, view: str = "week", month: str = "", db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role != "admin": return RedirectResponse("/login", status_code=303)
    employees = db.query(User).filter(User.role=="employee").order_by(User.name).all()
    leave_requests = db.query(LeaveRequest).order_by(LeaveRequest.start_date.desc()).all()
    anchor = date.today()
    if month:
        try: anchor = datetime.strptime(month + "-01", "%Y-%m-%d").date()
        except: anchor = date.today().replace(day=1)
    if view == "month":
        shifts = db.query(Shift).all()
        by = {}
        for s in shifts:
            by.setdefault(s.shift_date.isoformat(), []).append({"employee": s.employee.name, "time": f"{s.start_time}-{s.end_time}", "note": s.note or ""})
        weeks = [[{"date": d, "in_month": d.month == anchor.month, "items": by.get(d.isoformat(), [])} for d in w] for w in month_grid(anchor)]
        return templates.TemplateResponse("admin.html", {"request":request,"user":user,"employees":employees,"leave_requests":leave_requests,"view":"month","anchor":anchor,"calendar_weeks":weeks})
    dates = week_dates()
    shifts = db.query(Shift).order_by(Shift.shift_date, Shift.start_time).all()
    grouped = {d.isoformat(): [] for d in dates}
    for s in shifts:
        if s.shift_date.isoformat() in grouped: grouped[s.shift_date.isoformat()].append(s)
    days = [{"date": d, "items": grouped[d.isoformat()]} for d in dates]
    return templates.TemplateResponse("admin.html", {"request":request,"user":user,"employees":employees,"leave_requests":leave_requests,"view":"week","days":days,"anchor":anchor})

@app.post("/admin/employees/add")
def add_employee(request: Request, name: str = Form(...), email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role != "admin": return RedirectResponse("/login", status_code=303)
    if not db.query(User).filter(User.email==email).first():
        db.add(User(name=name, email=email, password=password, role="employee")); db.commit()
    return RedirectResponse("/admin", status_code=303)

@app.post("/admin/shifts/add")
def add_shift(request: Request, employee_id: int = Form(...), shift_date: str = Form(...), start_time: str = Form(...), end_time: str = Form(...), note: str = Form(""), repeat_weeks: int = Form(1), db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role != "admin": return RedirectResponse("/login", status_code=303)
    base = datetime.strptime(shift_date, "%Y-%m-%d").date()
    for i in range(max(1, min(int(repeat_weeks), 52))):
        db.add(Shift(employee_id=employee_id, shift_date=base+timedelta(days=7*i), start_time=start_time, end_time=end_time, note=note))
    db.commit()
    return RedirectResponse("/admin", status_code=303)

@app.post("/admin/shifts/update/{shift_id}")
def update_shift(shift_id: int, request: Request, employee_id: int = Form(...), shift_date: str = Form(...), start_time: str = Form(...), end_time: str = Form(...), note: str = Form(""), db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role != "admin": return RedirectResponse("/login", status_code=303)
    s = db.query(Shift).filter(Shift.id==shift_id).first()
    if s:
        s.employee_id=employee_id; s.shift_date=datetime.strptime(shift_date,"%Y-%m-%d").date(); s.start_time=start_time; s.end_time=end_time; s.note=note; db.commit()
    return RedirectResponse("/admin", status_code=303)

@app.post("/admin/shifts/delete/{shift_id}")
def delete_shift(shift_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role != "admin": return RedirectResponse("/login", status_code=303)
    s = db.query(Shift).filter(Shift.id==shift_id).first()
    if s: db.delete(s); db.commit()
    return RedirectResponse("/admin", status_code=303)

@app.post("/admin/shifts/move/{shift_id}")
def move_shift(shift_id: int, request: Request, target_date: str = Form(...), db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role != "admin": return {"ok": False}
    s = db.query(Shift).filter(Shift.id==shift_id).first()
    if s: s.shift_date = datetime.strptime(target_date, "%Y-%m-%d").date(); db.commit()
    return {"ok": True}

@app.post("/admin/leave/{leave_id}/status")
def leave_status(leave_id: int, request: Request, status: str = Form(...), db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role != "admin": return RedirectResponse("/login", status_code=303)
    l = db.query(LeaveRequest).filter(LeaveRequest.id==leave_id).first()
    if l and status in {"pending","approved","rejected"}: l.status=status; db.commit()
    return RedirectResponse("/admin", status_code=303)

@app.get("/employee")
def employee(request: Request, view: str = "week", month: str = "", db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role != "employee": return RedirectResponse("/login", status_code=303)
    leave_requests = db.query(LeaveRequest).filter(LeaveRequest.employee_id==user.id).order_by(LeaveRequest.start_date.desc()).all()
    anchor = date.today()
    if month:
        try: anchor = datetime.strptime(month+"-01","%Y-%m-%d").date()
        except: anchor = date.today().replace(day=1)
    if view == "month":
        shifts = db.query(Shift).filter(Shift.employee_id==user.id).all()
        by = {}
        for s in shifts: by.setdefault(s.shift_date.isoformat(), []).append({"time": f"{s.start_time}-{s.end_time}", "note": s.note or ""})
        weeks = [[{"date": d, "in_month": d.month == anchor.month, "items": by.get(d.isoformat(), [])} for d in w] for w in month_grid(anchor)]
        return templates.TemplateResponse("employee.html", {"request":request,"user":user,"view":"month","anchor":anchor,"calendar_weeks":weeks,"leave_requests":leave_requests})
    dates = week_dates()
    shifts = db.query(Shift).filter(Shift.employee_id==user.id).order_by(Shift.shift_date, Shift.start_time).all()
    grouped = {d.isoformat(): [] for d in dates}
    for s in shifts:
        if s.shift_date.isoformat() in grouped: grouped[s.shift_date.isoformat()].append(s)
    days = [{"date": d, "items": grouped[d.isoformat()]} for d in dates]
    return templates.TemplateResponse("employee.html", {"request":request,"user":user,"view":"week","days":days,"anchor":anchor,"leave_requests":leave_requests})

@app.post("/employee/leave/add")
def add_leave(request: Request, start_date: str = Form(...), end_date: str = Form(...), reason: str = Form(""), db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role != "employee": return RedirectResponse("/login", status_code=303)
    db.add(LeaveRequest(employee_id=user.id, start_date=datetime.strptime(start_date,"%Y-%m-%d").date(), end_date=datetime.strptime(end_date,"%Y-%m-%d").date(), reason=reason, status="pending"))
    db.commit()
    return RedirectResponse("/employee", status_code=303)
