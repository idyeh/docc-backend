from uuid import uuid4
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename

from app import db
from app.models import MediaFile

uploads_bp = Blueprint("uploads", __name__)

# allowed extensions
ALLOWED = {"pdf", "docx", "txt", "jpg", "jpeg", "png", "mp3", "wav", "mp4"}

@uploads_bp.route("/", methods=["POST"])
@jwt_required()
def upload_file():
    file = request.files.get("file")
    if not file:
        return jsonify(msg="No file provided"), 400

    # simple extension check
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED:
        return jsonify(msg="Type not allowed"), 400

    filename = secure_filename(file.filename)
    obj_name = f"{uuid4().hex}_{filename}"

    minio_client = current_app.minio_client
    bucket = current_app.config["MINIO_BUCKET"]

    # stream upload
    try:
        minio_client.put_object(
            bucket, obj_name, file.stream, file.content_length,
            content_type=file.mimetype
        )
    except Exception as e:
        current_app.logger.error(f"MinIO upload failed: {e}")
        return jsonify(msg="Upload failed"), 500

    # construct a public URL (assumes MinIO is fronted by HTTP)
    endpoint = current_app.config["MINIO_ENDPOINT"]
    secure = current_app.config["MINIO_SECURE"]
    scheme = "https" if secure else "http"
    url = f"{scheme}://{endpoint}/{bucket}/{obj_name}"

    # TODO: extract metadata (EXIF, PDF info) here
    metadata = {}

    # save a record in the DB
    mf = MediaFile(
        filename=filename,
        content_type=file.mimetype,
        url=url,
        size=file.content_length,
        metadata=metadata,
        uploaded_by=get_jwt_identity()
    )
    db.session.add(mf)
    db.session.commit()

    return jsonify(id=mf.id, url=mf.url), 201
