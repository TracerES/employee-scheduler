Employee Scheduler Render Ready

Features:
- Admin login
- Employee login
- Add employees
- Create shifts
- Edit shifts
- Delete shifts
- Recurring shifts
- Leave requests
- Approve/reject leave
- Drag-and-drop admin week calendar
- Week and month views
- Mobile-friendly layout
- Render PostgreSQL deployment ready

Run locally:
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload

Open:
http://127.0.0.1:8000
