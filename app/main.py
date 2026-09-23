from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings, get_settings
from app.models import ChatRequest, ChatResponse, HealthResponse
from app.services.agent import AgentService
from app.services.company_api import CorporateApiClient
from app.services.complaints import ComplaintRepository
from app.services.documents import DocumentValidationError, validate_application_document
from app.services.qwen import QwenClient
from app.services.rag import KnowledgeBase


settings = get_settings()
# база знаний RAG
knowledge_base = KnowledgeBase(settings)
# репозиторий жалоб
complaint_repository = ComplaintRepository(settings.database_path)
# Сам ии агент
agent = AgentService(
    settings,
    knowledge_base,
    QwenClient(settings),
    CorporateApiClient(settings),
    complaint_repository,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    complaint_repository.initialize()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse("app/static/index.html")


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    try:
        knowledge_base.ensure_ready()
        rag_ready = True
    except Exception:
        rag_ready = False
    return HealthResponse(
        status="ok" if rag_ready else "degraded",
        llm_configured=agent.qwen.configured,
        llm_provider=settings.llm_provider,
        llm_model=settings.resolved_llm_model,
        corporate_api_configured=agent.corporate_api.configured,
        rag_ready=rag_ready,
    )

# Передача сообщений между пользователем и агентом
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return await agent.chat(request.message, request.conversation_id)

# Загрузка документов для заявки на технические условия
@app.post("/api/conversations/{conversation_id}/documents")
async def upload_application_document(
    conversation_id: str, file: Annotated[UploadFile, File(...)]
) -> dict[str, str]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".jpg", ".jpeg", ".png"}:
        raise HTTPException(status_code=400, detail="Supported formats: PDF, JPG, JPEG, PNG")
    safe_name = Path(file.filename or "document").name
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="The document must not exceed 20 MB")
    folder = settings.uploads_dir / conversation_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / safe_name
    path.write_bytes(content)
    try:
        status, message = validate_application_document(path)
    except DocumentValidationError as error:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(error)) from error
    document = agent.add_application_document(conversation_id, safe_name, status, message)
    return {"document": document.name, "status": document.status, "message": document.message}


def require_admin_token(
    x_admin_token: Annotated[str | None, Header()] = None,
) -> None:
    if not settings.admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Invalid administrative token")

# Загрузка документов в базу знаний (только для администратора)
@app.post("/api/admin/documents")
async def upload_knowledge_document(
    file: Annotated[UploadFile, File(...)],
    _: Annotated[None, Depends(require_admin_token)],
) -> dict[str, int | str]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".txt", ".md", ".pdf"}:
        raise HTTPException(status_code=400, detail="Only .txt, .md, and .pdf knowledge documents are supported")
    safe_name = Path(file.filename or "document").name
    stored_path = settings.uploads_dir / "knowledge" / safe_name
    stored_path.parent.mkdir(parents=True, exist_ok=True)
    stored_path.write_bytes(await file.read())
    try:
        chunk_count = knowledge_base.ingest_file(stored_path, safe_name)
    except Exception as error:
        raise HTTPException(status_code=503, detail="Knowledge base is unavailable") from error
    return {"document": safe_name, "chunks": chunk_count}
