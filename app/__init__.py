import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from minio import Minio

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()

def create_app():
    app = Flask(__name__)
    app.logger.setLevel(logging.INFO)
    logging.getLogger('werkzeug').setLevel(logging.INFO)
    app.config.from_object("app.config.Config")

    app.logger.info(f"MINIO_ENDPOINT={app.config['MINIO_ENDPOINT']}")
    app.logger.info(f"MINIO_ROOT_USER={app.config['MINIO_ROOT_USER']}")
    app.logger.info(f"MINIO_ROOT_PASSWORD={'******' if app.config['MINIO_ROOT_PASSWORD'] else 'MISSING'}")
    app.logger.info(f"MINIO_BUCKET={app.config['MINIO_BUCKET']}")
    app.logger.info(f"MINIO_SECURE={app.config['MINIO_SECURE']}")

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": ["http://localhost:8888"]}})

    # --- MinIO setup ---
    try:
        minio_client = Minio(
            endpoint=app.config["MINIO_ENDPOINT"],
            access_key=app.config["MINIO_ROOT_USER"],
            secret_key=app.config["MINIO_ROOT_PASSWORD"],
            secure=app.config["MINIO_SECURE"]
        )
        # only try bucket ops if credentials worked
        bucket = app.config["MINIO_BUCKET"]
        if not minio_client.bucket_exists(bucket):
            minio_client.make_bucket(bucket)
        app.logger.info(f"MinIO bucket '{bucket}' is ready.")
        app.minio_client = minio_client
    except Exception as e:
        app.logger.error(f"MinIO setup failed: {e}")

    # register blueprints
    from app.auth.routes      import auth_bp
    from app.users.routes     import users_bp
    from app.forms.routes     import forms_bp
    from app.uploads.routes   import uploads_bp
    from app.workflows.routes import workflows_bp

    app.register_blueprint(auth_bp,      url_prefix="/api/auth")
    app.register_blueprint(users_bp,     url_prefix="/api/users")
    app.register_blueprint(forms_bp,     url_prefix="/api/forms")
    app.register_blueprint(uploads_bp,   url_prefix="/api/uploads")
    app.register_blueprint(workflows_bp, url_prefix="/api/workflows")

    return app