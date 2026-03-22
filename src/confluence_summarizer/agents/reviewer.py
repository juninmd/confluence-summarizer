import json
from src.confluence_summarizer.agents.common import generate_response, clean_json_response
from src.confluence_summarizer.models.domain import ReviewerResponse, RefinementStatus

async def review_page(original_content: str, rewritten_content: str) -> ReviewerResponse:
    """Palette / Quality Assurance: Verifica a aderência final entre as versões original e reescrita."""
    system = """Você é um Revisor de Documentações Técnicas do Confluence.
Avalie se a reescrita preserva as intenções originais, melhora o conteúdo seguindo os feedbacks e se o HTML está bem formado.
Responda EXCLUSIVAMENTE em JSON no formato:
{
  "status": "approved|rejected",
  "feedback": "motivo para aprovar ou rejeitar."
}"""

    user_prompt = f"Original:\n{original_content}\n\nReescrito:\n{rewritten_content}"
    response_text = await generate_response(system, user_prompt)

    try:
        data = json.loads(clean_json_response(response_text))
        status_raw = data.get("status", "").lower()
        if status_raw in ["approved", "accepted", "completed"]:
            data["status"] = RefinementStatus.COMPLETED.value
        else:
            data["status"] = RefinementStatus.REJECTED.value

        return ReviewerResponse(**data)
    except Exception as e:
        raise RuntimeError(f"Falha ao realizar a revisão final ou JSON inválido: {e}")
