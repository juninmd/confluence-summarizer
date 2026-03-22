import json
from src.confluence_summarizer.agents.common import generate_response, clean_json_response
from src.confluence_summarizer.models.domain import AnalystResponse

async def analyze_page(content: str) -> AnalystResponse:
    """Sentinel / Critic Agent: analisa o conteúdo cru buscando falhas de estrutura, semântica e atualização."""
    system = """Você é um Analista Crítico de Documentação do Confluence.
Seu objetivo é extrair falhas, desatualizações e problemas de formatação.
Responda EXCLUSIVAMENTE em JSON no formato:
{
  "critiques": [
    {
      "issue": "descrição",
      "severity": "low|medium|high|critical",
      "suggestion": "como arrumar"
    }
  ]
}
"""
    user_prompt = f"Conteúdo da página:\n\n{content}"
    response_text = await generate_response(system, user_prompt)

    cleaned = clean_json_response(response_text)
    try:
        data = json.loads(cleaned)
        # Normalização do case da severity antes da validação do Pydantic
        if "critiques" in data:
            for critique in data["critiques"]:
                if "severity" in critique and isinstance(critique["severity"], str):
                    critique["severity"] = critique["severity"].lower()
        return AnalystResponse(**data)
    except Exception as e:
        raise RuntimeError(f"Falha ao realizar análise do Analyst Agent ou JSON inválido: {e}")
