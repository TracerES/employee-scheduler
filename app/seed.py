
from datetime import date, timedelta
from sqlalchemy.orm import Session
from .models import User, Shift, LeaveRequest

def seed_data(db: Session):
    admin = db.query(User).filter_by(email="admin@example.com").first()
    if not admin:
        db.add(User(name="Admin", email="admin@example.com", password="admin123", role="admin"))
    employee = db.query(User).filter_by(email="jane@example.com").first()
    if not employee:
        db.add(User(name="Jane Worker", email="jane@example.com", password="employee123", role="employee"))
    db.commit()

    employee = db.query(User).filter_by(email="jane@example.com").first()
    if db.query(Shift).filter_by(employee_id=employee.id).count() == 0:
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        db.add_all([
            Shift(employee_id=employee.id, shift_date=monday, start_time="08:00", end_time="16:00", note="Front desk"),
            Shift(employee_id=employee.id, shift_date=monday + timedelta(days=2), start_time="09:00", end_time="17:00", note="Warehouse"),
            Shift(employee_id=employee.id, shift_date=monday + timedelta(days=4), start_time="10:00", end_time="18:00", note="Late shift"),
        ])
        db.commit()
