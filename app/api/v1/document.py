from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_owned_workspace
from app.db.session import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.document import DocumentOut
from app.services.document_service import DocumentService

router = APIRouter(prefix="/workspaces/{workspace_id}/documents", tags=["documents"])


def get_document_service(db: AsyncSession = Depends(get_db)) -> DocumentService:
    return DocumentService(db)


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    workspace: Workspace = Depends(get_owned_workspace),
    file: UploadFile = File(...),
    service: DocumentService = Depends(get_document_service),
):
    return await service.upload(workspace.id, file)


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    workspace: Workspace = Depends(get_owned_workspace),
    service: DocumentService = Depends(get_document_service),
):
    return await service.list_for_workspace(workspace.id)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    workspace: Workspace = Depends(get_owned_workspace),
    service: DocumentService = Depends(get_document_service),
):
    document = await service.get_owned(document_id, workspace.id)
    await service.delete(document)
