
from typing import List
from src.confluence_summarizer.agents.common import generate_response, clean_json_response
from src.confluence_summarizer.models.domain import AnalystResponse

async def rewrite_page(original_content: str, critiques: AnalystResponse, context: List[str]) -> str:
    """Bolt / Creator Agent: Usa os dados originais e o feedback para reescrever a página."""
    system = """Você é um Escritor de Documentações Técnicas do Confluence.
Seu objetivo é reescrever a página de forma concisa e padronizada.
Respeite o conteúdo do sistema armazenado no contexto (RAG) para não gerar informações conflituantes.
Mantenha a estrutura HTML crua para tabelas e blocos de código se eles existirem!
Retorne APENAS o HTML da reescrita. Não insira blocos Markdown como ```html ao redor da resposta."""

    user_prompt = f"Conteúdo Original:\n{original_content}\n\nCríticas:\n"
    for c in critiques.critiques:
        user_prompt += f"- {c.severity}: {c.issue} -> {c.suggestion}\n"

    user_prompt += f"\n\nContexto Base (Outras páginas):\n{context}\n\nPor favor, retorne o novo HTML da página."

    response_text = await generate_response(system, user_prompt)
    if not response_text:
        raise RuntimeError("Falha ao gerar o conteúdo reescrito (Writer Agent retornou vazio).")

    return clean_json_response(response_text) # Reutilizado o clean para remover ```html caso o LLM insira
