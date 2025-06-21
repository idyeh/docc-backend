import logging
from typing import Annotated
from uuid import uuid4
import io

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from werkzeug.utils import secure_filename
from doccapi.security import get_current_user
from doccapi.models.user import User
from doccapi.database import database, mediafile_table
from doccapi.config import config
from minio import Minio

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED = {"pdf", "docx", "txt", "jpg", "jpeg", "png", "mp3", "wav", "mp4"}

@router.post("", status_code=201)
async def upload_file(
    current_user: Annotated[User, Depends(get_current_user)], 
    file: UploadFile = File(...)
):
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided"
        )
    
    ext = file.filename.split(".")[-1].lower()
    if ext not in ALLOWED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="File type not allowed"
        )
    
    filename = secure_filename(file.filename)
    obj_name = f"{uuid4().hex}_{filename}"

    try:
        file_content = await file.read()
        file_size = len(file_content)
        
        # 创建文件流用于上传
        file_stream = io.BytesIO(file_content)


        minio_client = Minio(
            endpoint=config.MINIO_ENDPOINT,
            access_key=config.MINIO_ROOT_USER,
            secret_key=config.MINIO_ROOT_PASSWORD,
            secure=config.MINIO_SECURE
        )

        bucket = config.MINIO_BUCKET

        # 上传到 MinIO
        minio_client.put_object(
            bucket_name=bucket,
            object_name=obj_name,
            data=file_stream,
            length=file_size,
            content_type=file.content_type
        )

        endpoint = config.MINIO_ENDPOINT
        secure = config.MINIO_SECURE
        scheme = "https" if secure else "http"
        url = f"{scheme}://{endpoint}/{bucket}/{obj_name}"

        metadata = {}

        query = mediafile_table.insert().values(
            filename=filename,
            content_type=file.content_type,
            url=url,
            size=file_size,
            meta=metadata,
            uploaded_by=current_user.id
        )
        result = await database.execute(query)

        return {
            "id": result, 
            "url": url, 
            "filename": filename,
            "content_type": file.content_type,
            "size": file_size
        }

    except Exception as e:
        logger.error(f"MinIO upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file to storage"
        )

@router.delete("", status_code=204)
async def delete_file(
    current_user: Annotated[User, Depends(get_current_user)], 
    file: UploadFile = File(...)
):
    return None