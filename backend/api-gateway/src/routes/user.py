"""
API Gateway - user route helpers (not registered; gateway proxies to user-service).
"""

from flask import Blueprint

user_bp = Blueprint("user", __name__)
