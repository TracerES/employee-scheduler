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
    try:
        seed_data(db)
    finally:
        db.close()

def current_user(request, db):
    token = request.cookies.get(SESSION_NAME)
    if not token:
        return None
    data = read_session(token)
    if not data:
        return None
    return db.query(User).filter(User.id == data["user_id"]).first()

def parse_week(week: str = ""):
    if week:
        try:
            anchor = datetime.strptime(week, "%Y-%m-%d").date()
        except Exception:
            anchor = date.today()
    else:
        anchor = date.today()
    monday = anchor - timedelta(days=anchor.weekday())
    return monday

def parse_month(month: str = ""):
    if month:
        try:
            return datetime.strptime(month + "-01", "%Y-%m-%d").date()
        except Exception:
            pass
    return date.today().replace(day=1)

def month_grid(anchor):
    return calendar.Calendar(firstweekday=0).monthdatescalendar(anchor.year, anchor.month)

def add_months(d: date, months: int):
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)

def approved_leave_items(db: Session, start: date, end: date, employee_id: int | None = None):
    q = db.query(LeaveRequest).filter(
        LeaveRequest.status == "approved",
        LeaveRequest.start_date <= end,
        LeaveRequest.end_date >= start,
    )
    if employee_id is not None:
        q = q.filter(LeaveRequest.employee_id == employee_id)
    by_date = {}
    for leave in q.all():
        d = max(leave.start_date, start)
        last = min(leave.end_date, end)
        while d <= last:
            by_date.setdefault(d.isoformat(), []).append({
                "employee": leave.employee.name,
                "label": f"{leave.employee.name} — Leave",
                "reason": leave.reason or "",
            })
            d += timedelta(days=1)
    return by_date

def admin_calendar_context(db: Session, view: str, week: str = "", month: str = ""):
    if view == "month":
        anchor = parse_month(month)
        grid = month_grid(anchor)
        start, end = grid[0][0], grid[-1][-1]
        shifts = db.query(Shift).filter(Shift.shift_date >= start, Shift.shift_date <= end).order_by(Shift.shift_date, Shift.start_time).all()
        shift_by = {}
        for s in shifts:
            shift_by.setdefault(s.shift_date.isoformat(), []).append(s)
        leave_by = approved_leave_items(db, start, end)
        weeks = [[{
            "date": d,
            "in_month": d.month == anchor.month,
            "shifts": shift_by.get(d.isoformat(), []),
            "leaves": leave_by.get(d.isoformat(), []),
        } for d in w] for w in grid]
        return {
            "view": "month",
            "anchor": anchor,
            "calendar_weeks": weeks,
            "prev_month": add_months(anchor, -1).strftime("%Y-%m"),
            "next_month": add_months(anchor, 1).strftime("%Y-%m"),
        }

    monday = parse_week(week)
    dates = [monday + timedelta(days=i) for i in range(7)]
    shifts = db.query(Shift).filter(Shift.shift_date >= dates[0], Shift.shift_date <= dates[-1]).order_by(Shift.shift_date, Shift.start_time).all()
    shift_by = {d.isoformat(): [] for d in dates}
    for s in shifts:
        shift_by.setdefault(s.shift_date.isoformat(), []).append(s)
    leave_by = approved_leave_items(db, dates[0], dates[-1])
    days = [{"date": d, "shifts": shift_by.get(d.isoformat(), []), "leaves": leave_by.get(d.isoformat(), [])} for d in dates]
    return {
        "view": "week",
        "anchor": monday,
        "days": days,
        "prev_week": (monday - timedelta(days=7)).isoformat(),
        "next_week": (monday + timedelta(days=7)).isoformat(),
    }

def employee_calendar_context(db: Session, user: User, view: str, week: str = "", month: str = ""):
    if view == "month":
        anchor = parse_month(month)
        grid = month_grid(anchor)
        start, end = grid[0][0], grid[-1][-1]
        shifts = db.query(Shift).filter(Shift.employee_id == user.id, Shift.shift_date >= start, Shift.shift_date <= end).order_by(Shift.shift_date, Shift.start_time).all()
        shift_by = {}
        for s in shifts:
            shift_by.setdefault(s.shift_date.isoformat(), []).append(s)
        leave_by = approved_leave_items(db, start, end, user.id)
        weeks = [[{
            "date": d,
            "in_month": d.month == anchor.month,
            "shifts": shift_by.get(d.isoformat(), []),
            "leaves": leave_by.get(d.isoformat(), []),
        } for d in w] for w in grid]
        return {
            "view": "month",
            "anchor": anchor,
            "calendar_weeks": weeks,
            "prev_month": add_months(anchor, -1).strftime("%Y-%m"),
            "next_month": add_months(anchor, 1).strftime("%Y-%m"),
        }

    monday = parse_week(week)
    dates = [monday + timedelta(days=i) for i in range(7)]
    shifts = db.query(Shift).filter(Shift.employee_id == user.id, Shift.shift_date >= dates[0], Shift.shift_date <= dates[-1]).order_by(Shift.shift_date, Shift.start_time).all()
    shift_by = {d.isoformat(): [] for d in dates}
    for s in shifts:
        shift_by.setdefault(s.shift_date.isoformat(), []).append(s)
    leave_by = approved_leave_items(db, dates[0], dates[-1], user.id)
    days = [{"date": d, "shifts": shift_by.get(d.isoformat(), []), "leaves": leave_by.get(d.isoformat(), [])} for d in dates]
    return {
        "view": "week",
        "anchor": monday,
        "days": days,
        "prev_week": (monday - timedelta(days=7)).isoformat(),
        "next_week": (monday + timedelta(days=7)).isoformat(),
    }

@app.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if user:
        return RedirectResponse("/admin" if user.role == "admin" else "/employee", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": ""})

@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": ""})

@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user or user.password != password:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid email or password"})
    r = RedirectResponse("/admin" if user.role == "admin" else "/employee", status_code=303)
    r.set_cookie(SESSION_NAME, create_session(user.id, user.role, user.name), httponly=True)
    return r

@app.get("/logout")
def logout():
    r = RedirectResponse("/login", status_code=303)
    r.delete_cookie(SESSION_NAME)
    return r

@app.get("/admin")
def admin(request: Request, view: str = "week", week: str = "", month: str = "", db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role != "admin":
        return RedirectResponse("/login", status_code=303)
    employees = db.query(User).filter(User.role == "employee").order_by(User.name).all()
    ctx = admin_calendar_context(db, view, week, month)
    ctx.update({"request": request, "user": user, "employees": employees})
    return templates.TemplateResponse("admin.html", ctx)

@app.get("/admin/employees")
def admin_employees(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role != "admin":
        return RedirectResponse("/login", status_code=303)
    employees = db.query(User).filter(User.role == "employee").order_by(User.name).all()
    return templates.TemplateResponse("admin_employees.html", {"request": request, "user": user, "employees": employees})

@app.get("/admin/shifts")
def admin_shifts(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role != "admin":
        return RedirectResponse("/login", status_code=303)
    employees = db.query(User).filter(User.role == "employee").order_by(User.name).all()
    return templates.TemplateResponse("admin_shifts.html", {"request": request, "user": user, "employees": employees})

@app.get("/admin/leave")
def admin_leave(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role != "admin":
        return RedirectResponse("/login", status_code=303)
    leave_requests = db.query(LeaveRequest).order_by(LeaveRequest.start_date.desc()).all()
    return templates.TemplateResponse("admin_leave.html", {"request": request, "user": user, "leave_requests": leave_requests})

@app.post("/admin/employees/add")
def add_employee(request: Request, name: str = Form(...), email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role != "admin":
        return RedirectResponse("/login", status_code=303)
    if not db.query(User).filter(User.email == email).first():
        db.add(User(name=name, email=email, password=password, role="employee"))
        db.commit()
    return RedirectResponse("/admin/employees", status_code=303)

@app.post("/admin/shifts/add")
def add_shift(request: Request, employee_id: int = Form(...), shift_date: str = Form(...), start_time: str = Form(...), end_time: str = Form(...), note: str = Form(""), repeat_weeks: int = Form(1), db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role != "admin":
        return RedirectResponse("/login", status_code=303)
    base = datetime.strptime(shift_date, "%Y-%m-%d").date()
    for i in range(max(1, min(int(repeat_weeks), 52))):
        db.add(Shift(employee_id=employee_id, shift_date=base + timedelta(days=7 * i), start_time=start_time, end_time=end_time, note=note))
    db.commit()
    return RedirectResponse("/admin/shifts", status_code=303)

@app.post("/admin/shifts/update/{shift_id}")
def update_shift(shift_id: int, request: Request, employee_id: int = Form(...), shift_date: str = Form(...), start_time: str = Form(...), end_time: str = Form(...), note: str = Form(""), db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role != "admin":
        return RedirectResponse("/login", status_code=303)
    s = db.query(Shift).filter(Shift.id == shift_id).first()
    if s:
        s.employee_id = employee_id
        s.shift_date = datetime.strptime(shift_date, "%Y-%m-%d").date()
        s.start_time = start_time
        s.end_time = end_time
        s.note = note
        db.commit()
    return RedirectResponse("/admin", status_code=303)

@app.post("/admin/shifts/delete/{shift_id}")
def delete_shift(shift_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role != "admin":
        return RedirectResponse("/login", status_code=303)
    s = db.query(Shift).filter(Shift.id == shift_id).first()
    if s:
        db.delete(s)
        db.commit()
    return RedirectResponse("/admin", status_code=303)

@app.post("/admin/shifts/move/{shift_id}")
def move_shift(shift_id: int, request: Request, target_date: str = Form(...), db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role != "admin":
        return {"ok": False}
    s = db.query(Shift).filter(Shift.id == shift_id).first()
    if s:
        s.shift_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        db.commit()
    return {"ok": True}

@app.post("/admin/leave/{leave_id}/status")
def leave_status(leave_id: int, request: Request, status: str = Form(...), db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role != "admin":
        return RedirectResponse("/login", status_code=303)
    l = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if l and status in {"pending", "approved", "rejected"}:
        l.status = status
        db.commit()
    return RedirectResponse("/admin/leave", status_code=303)

@app.get("/employee")
def employee(request: Request, view: str = "week", week: str = "", month: str = "", db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role != "employee":
        return RedirectResponse("/login", status_code=303)
    leave_requests = db.query(LeaveRequest).filter(LeaveRequest.employee_id == user.id).order_by(LeaveRequest.start_date.desc()).all()
    ctx = employee_calendar_context(db, user, view, week, month)
    ctx.update({"request": request, "user": user, "leave_requests": leave_requests})
    return templates.TemplateResponse("employee.html", ctx)

@app.post("/employee/leave/add")
def add_leave(request: Request, start_date: str = Form(...), end_date: str = Form(...), reason: str = Form(""), db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.role != "employee":
        return RedirectResponse("/login", status_code=303)
    db.add(LeaveRequest(employee_id=user.id, start_date=datetime.strptime(start_date, "%Y-%m-%d").date(), end_date=datetime.strptime(end_date, "%Y-%m-%d").date(), reason=reason, status="pending"))
    db.commit()
    return RedirectResponse("/employee", status_code=303)
