from ai_models.core.errors import ValidationError
from flask import Blueprint, jsonify
from routes.helpers import Timer, body, identity, optional_text, page_args, services

bp = Blueprint("chat", __name__)
MAX_CONTEXT_KEYS = 10


@bp.route("/chat/sessions", methods=["POST"])
def create_session():
    user = identity()
    data = body()
    context = data.get("context") or {}
    if not isinstance(context, dict):
        raise ValidationError("context must be an object")
    session = services().repo.create_session(
        user["user_id"],
        optional_text(data.get("session_name"), "session_name"),
        context,
    )
    return jsonify(session), 201


@bp.route("/chat/sessions", methods=["GET"])
def list_sessions():
    user = identity()
    page, per_page = page_args()
    return jsonify(services().repo.list_sessions(user["user_id"], page, per_page))


@bp.route("/chat/sessions/<session_id>", methods=["GET"])
def get_session(session_id: str):
    user = identity()
    svc = services()
    session = svc.repo.get_session(user["user_id"], session_id)
    session["messages"] = svc.repo.list_messages(session_id)
    return jsonify(session)


@bp.route("/chat/sessions/<session_id>/messages", methods=["GET"])
def list_messages(session_id: str):
    user = identity()
    svc = services()
    svc.repo.get_session(user["user_id"], session_id)
    return jsonify({"messages": svc.repo.list_messages(session_id)})


@bp.route("/chat/sessions/<session_id>", methods=["DELETE"])
def close_session(session_id: str):
    user = identity()
    services().repo.close_session(user["user_id"], session_id)
    return jsonify({"message": "Session closed"})


@bp.route("/chat/sessions/<session_id>/messages", methods=["POST"])
def send_message(session_id: str):
    user = identity()
    data = body()
    svc = services()
    session = svc.repo.get_session(user["user_id"], session_id)
    context = dict(session["context"])
    extra = data.get("context")
    if extra is not None:
        if not isinstance(extra, dict):
            raise ValidationError("context must be an object")
        context.update(extra)
        if len(context) > MAX_CONTEXT_KEYS:
            raise ValidationError(f"context may hold at most {MAX_CONTEXT_KEYS} keys")
        svc.repo.update_session_context(session_id, context)
    message = data.get("message")
    effective = dict(context)
    if effective.get("source") == "payments":
        transactions = svc.payments.transactions(user["user_id"])
        effective.setdefault("transactions", transactions)
        effective.setdefault("historical_data", {"transactions": transactions})
        effective.setdefault("financial_data", {"transactions": transactions})
    with Timer() as timer:
        reply = svc.assistant.respond(message, effective)
    user_message = svc.repo.add_message(session_id, "user", message, None, None)
    assistant_message = svc.repo.add_message(
        session_id,
        "assistant",
        reply["content"],
        {
            k: reply.get(k)
            for k in (
                "intent",
                "matched_terms",
                "data",
                "suggested_actions",
                "requires_data",
            )
        },
        timer.ms,
    )
    return (
        jsonify(
            {
                "user_message": user_message,
                "assistant_message": assistant_message,
                "reply": reply,
            }
        ),
        201,
    )
