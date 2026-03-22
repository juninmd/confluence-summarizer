import uuid
import asyncio
import logging
from typing import Set, Dict, Any
from fastapi import FastAPI, HTTPException
import dotenv

# Load local environment vars before importing config and other modules
dotenv.load_dotenv()

from src.confluence_summarizer.database import init_db, create_job, get_job, update_job  # noqa: E402
from src.confluence_summarizer.services.confluence import init_client, close_client, get_page_by_id, get_pages_in_space  # noqa: E402
from src.confluence_summarizer.services.rag import ingest_page, query_context  # noqa: E402
from src.confluence_summarizer.agents.analyst import analyze_page  # noqa: E402
from src.confluence_summarizer.agents.writer import rewrite_page  # noqa: E402
from src.confluence_summarizer.agents.reviewer import review_page  # noqa: E402
from src.confluence_summarizer.models.domain import JobRecord, RefinementStatus  # noqa: E402

# Set logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan for initializing and tearing down application resources."""
    init_db()
    init_client()
    logger.info("Application startup completed. DB and Client initialized.")
    yield
    await close_client()
    logger.info("Application shutdown completed. Resources released.")

app = FastAPI(title="Confluence Summarizer API", version="0.1.0", lifespan=lifespan)

# Set for strong reference to background tasks
_background_tasks: Set[asyncio.Task[Any]] = set()

REFINEMENT_CONCURRENCY = 5
INGESTION_CONCURRENCY = 10


async def _perform_refinement(job_id: str, page_id: str) -> None:
    """Core logic to run the complete Antigravity Audit on a single page."""
    try:
        await update_job(job_id, RefinementStatus.IN_PROGRESS.value)

        # 1. Recupera o conteúdo da página do Confluence
        page_data = await get_page_by_id(page_id)

        body_storage = page_data.get("body", {}).get("storage", {}).get("value", "")
        title = page_data.get("title", f"Page {page_id}")

        if not body_storage:
             raise ValueError("Página não possui conteúdo armazenado (storage value vazio).")

        # 2. Ingestão RAG (Background - Threaded na própria função)
        await ingest_page(page_id, body_storage, title)

        # 3. Agents: Analyst -> Writer -> Reviewer
        analysis = await analyze_page(body_storage)

        # Cria query para cross-check baseada nas críticas
        issues_summary = " ".join([c.issue for c in analysis.critiques])
        context = await query_context(f"Context for {title} issues: {issues_summary}")

        new_content = await rewrite_page(body_storage, analysis, context)

        review = await review_page(body_storage, new_content)

        # 4. Finalização
        if review.status == RefinementStatus.COMPLETED.value:
            await update_job(job_id, RefinementStatus.COMPLETED.value, result=new_content)
        else:
            await update_job(job_id, RefinementStatus.REJECTED.value, result=new_content, error=review.feedback)

    except Exception as e:
        logger.exception(f"Erro durante o refinamento do job {job_id}")
        await update_job(job_id, RefinementStatus.FAILED.value, error=str(e))

async def _batch_refinement(job_id: str, space_key: str) -> None:
    """Batch logic: processa todas as páginas de um space limitando concorrência."""
    try:
        await update_job(job_id, RefinementStatus.IN_PROGRESS.value)
        pages = await get_pages_in_space(space_key)

        semaphore = asyncio.Semaphore(REFINEMENT_CONCURRENCY)

        async def _bounded_refinement(p_id: str):
            async with semaphore:
                # Cada página terá um sub-job para rastreio ou ignora persistência de cada e foca no log.
                # Para simplificar na prova de conceito, rodamos a lógica sem sub-jobs
                # Mas utilizando dummy variables para logs.
                try:
                    p_data = await get_page_by_id(p_id)
                    body = p_data.get("body", {}).get("storage", {}).get("value", "")
                    title = p_data.get("title", f"Page {p_id}")
                    if body:
                        await ingest_page(p_id, body, title)
                        analysis = await analyze_page(body)
                        context = await query_context(" ".join([c.issue for c in analysis.critiques]))
                        new_content = await rewrite_page(body, analysis, context)
                        await review_page(body, new_content)
                except Exception as e:
                    logger.warning(f"Erro ao processar sub-página {p_id} no lote {job_id}: {e}")

        tasks = [_bounded_refinement(p["id"]) for p in pages if "id" in p]
        if tasks:
             await asyncio.gather(*tasks)

        await update_job(job_id, RefinementStatus.COMPLETED.value, result=f"Processadas {len(tasks)} páginas.")
    except Exception as e:
         logger.exception(f"Erro no job de lote {job_id}")
         await update_job(job_id, RefinementStatus.FAILED.value, error=str(e))

@app.post("/refine/{page_id}", summary="Refina uma única página do Confluence")
async def refine_page(page_id: str) -> Dict[str, str]:
    """Inicia um job em background para analisar, reescrever e revisar uma página específica."""
    job_id = str(uuid.uuid4())
    await create_job(job_id, page_id)

    task = asyncio.create_task(_perform_refinement(job_id, page_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {"job_id": job_id, "message": "Refinement started."}

@app.post("/refine/space/{space_key}", summary="Refina todas as páginas de um Confluence Space")
async def refine_space(space_key: str) -> Dict[str, str]:
    """Inicia um processo batch de Antigravity Audit para um space."""
    job_id = str(uuid.uuid4())
    await create_job(job_id, f"SPACE_{space_key}")

    task = asyncio.create_task(_batch_refinement(job_id, space_key))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {"job_id": job_id, "message": "Batch refinement for Space started."}

@app.get("/status/{job_id}", summary="Consulta o estado de um Refinement Job")
async def get_status(job_id: str) -> JobRecord:
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job

@app.post("/publish/{job_id}", summary="Publica o job finalizado de volta ao Confluence (Stub)")
async def publish_job(job_id: str) -> Dict[str, str]:
    """Recupera o resultado COMPLETED e salva como rascunho (stub)."""
    job = await get_job(job_id)
    if not job:
         raise HTTPException(status_code=404, detail="Job not found.")
    if job.status != RefinementStatus.COMPLETED.value:
         raise HTTPException(status_code=400, detail="Job is not completed yet.")

    # Implementação de persistência mock
    logger.info(f"Publicando alterações para a página {job.page_id}")
    return {"message": "Draft successfully published/saved."}
