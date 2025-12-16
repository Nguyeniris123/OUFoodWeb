from functools import wraps
from flask_login import current_user
from flask import redirect, abort
from app.models import Role
from flask_login import login_required


def logged_in_user(f):
    @wraps(f)
    def decorated_func(*args, **kwargs):
        if current_user.is_authenticated:
            return redirect("/")
        return f(*args, **kwargs)

    return decorated_func


def logged_in_customer(f):
    @wraps(f)
    def decorated_func(*args, **kwargs):
        if current_user.is_authenticated and current_user.role == Role.CUSTOMER:
            abort(403)
        return f(*args, **kwargs)

    return decorated_func


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_func(*args, **kwargs):
        if current_user.role != Role.ADMIN:
            abort(403)
        return f(*args, **kwargs)

    return decorated_func


def manager_required(f):
    @wraps(f)
    @login_required
    def decorated_func(*args, **kwargs):
        if current_user.role != Role.MANAGER:
            abort(403)
        return f(*args, **kwargs)

    return decorated_func


def admin_or_manager_required(f):
    @wraps(f)
    @login_required
    def decorated_func(*args, **kwargs):
        if current_user.role not in [Role.ADMIN, Role.MANAGER]:
            abort(403)
        return f(*args, **kwargs)

    return decorated_func
