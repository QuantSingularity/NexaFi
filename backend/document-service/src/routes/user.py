import os
import uuid
from datetime import datetime
from functools import wraps
from typing import Any

from flask import Blueprint, jsonify, request, send_file
from models.user import Document, DocumentShare, DocumentTemplate, DocumentVersion

document_bp = Blueprint("document", __name__)
DOCUMENT_STORAGE_PATH = "/NexaFi/backend/document-service/storage"


def require_user_id(f: Any) -> Any:
    """Decorator to extract user_id from request headers"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = request.headers.get("X-User-ID")
        if not user_id:
            return (jsonify({"error": "User ID is required in headers"}), 401)
        request.user_id = user_id
        return f(*args, **kwargs)

    return decorated_function


@document_bp.route("/documents", methods=["GET"])
@require_user_id
def get_documents() -> Any:
    """Get all documents for the current user."""
    try:
        documents = Document.find_all("user_id = ?", (request.user_id,))
        return (jsonify([d.to_dict() for d in documents]), 200)
    except Exception as e:
        return (jsonify({"error": "Failed to fetch documents", "details": str(e)}), 500)


@document_bp.route("/documents", methods=["POST"])
@require_user_id
def upload_document() -> Any:
    """Upload a new document (simulated file handling)."""
    try:
        os.makedirs(DOCUMENT_STORAGE_PATH, exist_ok=True)
        data = request.get_json()
        if not data or "file_content" not in data:
            return (jsonify({"error": "Missing file_content in request"}), 400)
        doc_id = str(uuid.uuid4())
        file_name = data.get("file_name", f"document_{doc_id}.txt")
        file_path = os.path.join(DOCUMENT_STORAGE_PATH, doc_id, file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        file_content = data["file_content"]
        with open(file_path, "w") as f:
            f.write(file_content)
        new_document = Document(
            id=doc_id,
            user_id=request.user_id,
            document_type=data.get("document_type", "general"),
            title=data.get("title", file_name),
            file_name=file_name,
            file_path=file_path,
            mime_type=data.get("mime_type", "text/plain"),
            file_size=len(file_content),
            status="uploaded",
            metadata=data.get("metadata", "{}"),
            extracted_data=data.get("extracted_data", "{}"),
            uploaded_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )
        new_document.save()
        initial_version = DocumentVersion(
            id=str(uuid.uuid4()),
            document_id=doc_id,
            version_number=1,
            file_path=file_path,
            file_size=len(file_content),
            created_at=datetime.utcnow().isoformat(),
        )
        initial_version.save()
        return (jsonify(new_document.to_dict()), 201)
    except Exception as e:
        return (jsonify({"error": "Failed to upload document", "details": str(e)}), 500)


@document_bp.route("/documents/<document_id>", methods=["GET"])
@require_user_id
def get_document(document_id: Any) -> Any:
    """Get a specific document by ID."""
    document = Document.find_one(
        "id = ? AND user_id = ?", (document_id, request.user_id)
    )
    if not document:
        return (jsonify({"error": "Document not found"}), 404)
    return (jsonify(document.to_dict()), 200)


@document_bp.route("/documents/<document_id>/download", methods=["GET"])
@require_user_id
def download_document(document_id: Any) -> Any:
    """Download the latest version of a document."""
    document = Document.find_one(
        "id = ? AND user_id = ?", (document_id, request.user_id)
    )
    if not document:
        return (jsonify({"error": "Document not found"}), 404)
    try:
        return send_file(
            document.file_path,
            mimetype=document.mime_type,
            as_attachment=True,
            download_name=document.file_name,
        )
    except FileNotFoundError:
        return (jsonify({"error": "File not found on server"}), 500)


@document_bp.route("/documents/<document_id>", methods=["DELETE"])
@require_user_id
def delete_document(document_id: Any) -> Any:
    """Delete a document and all its versions."""
    try:
        document = Document.find_one(
            "id = ? AND user_id = ?", (document_id, request.user_id)
        )
        if not document:
            return (jsonify({"error": "Document not found"}), 404)
        versions = DocumentVersion.find_all("document_id = ?", (document_id,))
        for version in versions:
            if os.path.exists(version.file_path):
                os.remove(version.file_path)
            version.delete()
        document.delete()
        doc_dir = os.path.join(DOCUMENT_STORAGE_PATH, document_id)
        if os.path.exists(doc_dir):
            os.rmdir(doc_dir)
        return (jsonify({"message": "Document deleted successfully"}), 204)
    except Exception as e:
        return (jsonify({"error": "Failed to delete document", "details": str(e)}), 500)


@document_bp.route("/templates", methods=["GET"])
def get_templates() -> Any:
    """Get all document templates."""
    try:
        templates = DocumentTemplate.find_all()
        return (jsonify([t.to_dict() for t in templates]), 200)
    except Exception as e:
        return (jsonify({"error": "Failed to fetch templates", "details": str(e)}), 500)


@document_bp.route("/templates", methods=["POST"])
def create_template() -> Any:
    """Create a new document template."""
    try:
        data = request.get_json()
        new_template = DocumentTemplate(
            id=str(uuid.uuid4()),
            name=data["name"],
            description=data.get("description"),
            template_type=data["template_type"],
            fields=data.get("fields", "[]"),
            metadata=data.get("metadata", "{}"),
            is_active=data.get("is_active", True),
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )
        new_template.save()
        return (jsonify(new_template.to_dict()), 201)
    except Exception as e:
        return (jsonify({"error": "Failed to create template", "details": str(e)}), 400)


@document_bp.route("/templates/<template_id>", methods=["GET"])
def get_template(template_id: Any) -> Any:
    """Get a specific document template by ID."""
    template = DocumentTemplate.find_by_id(template_id)
    if not template:
        return (jsonify({"error": "Template not found"}), 404)
    return (jsonify(template.to_dict()), 200)


@document_bp.route("/documents/<document_id>/share", methods=["POST"])
@require_user_id
def share_document(document_id: Any) -> Any:
    """Share a document with another user or email."""
    try:
        document = Document.find_one(
            "id = ? AND user_id = ?", (document_id, request.user_id)
        )
        if not document:
            return (jsonify({"error": "Document not found"}), 404)
        data = request.get_json()
        new_share = DocumentShare(
            id=str(uuid.uuid4()),
            document_id=document_id,
            shared_with_user_id=data.get("shared_with_user_id"),
            shared_with_email=data.get("shared_with_email"),
            permission_level=data.get("permission_level", "read"),
            expires_at=data.get("expires_at"),
            shared_by=request.user_id,
            created_at=datetime.utcnow().isoformat(),
        )
        new_share.save()
        return (jsonify(new_share.to_dict()), 201)
    except Exception as e:
        return (jsonify({"error": "Failed to share document", "details": str(e)}), 400)


@document_bp.route("/documents/<document_id>/shares", methods=["GET"])
@require_user_id
def get_document_shares(document_id: Any) -> Any:
    """Get all share records for a document."""
    document = Document.find_one(
        "id = ? AND user_id = ?", (document_id, request.user_id)
    )
    if not document:
        return (jsonify({"error": "Document not found"}), 404)
    shares = DocumentShare.find_all("document_id = ?", (document_id,))
    return (jsonify([s.to_dict() for s in shares]), 200)
