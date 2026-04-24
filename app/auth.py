
from itsdangerous import URLSafeSerializer
SECRET_KEY = "replace-this-secret-before-production"
SESSION_NAME = "scheduler_session"
serializer = URLSafeSerializer(SECRET_KEY, salt="scheduler-auth")
def create_session(user_id: int, role: str, name: str):
    return serializer.dumps({"user_id": user_id, "role": role, "name": name})
def read_session(token: str):
    try:
        return serializer.loads(token)
    except Exception:
        return None
