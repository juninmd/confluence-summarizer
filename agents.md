# Agentes de IA - Confluence Summarizer

O sistema utiliza a arquitetura de *Chain of Responsibility* para realizar uma auditoria completa (também referida no protocolo Jules como "Antigravity Audits") em espaços ou páginas individuais do Confluence, visando manutenção e conformidade da documentação.

Os Agentes operam assumindo personas ("Mission Mode", como Bolt, Palette, Sentinel, Spark conforme o contexto) para executar tarefas com a maior precisão possível.

A cadeia ocorre sequencialmente:

## 1. O Pipeline Principal
A orquestração principal recupera o texto da API do Confluence (Ingestor), indexa partes no Vector DB (RAG) e envia para os três Agentes de IA responsáveis.

### 2. Analyst Agent (Sentinel / Critic)
- **Função:** Avalia e critica criticamente o conteúdo cru recebido do Confluence.
- **Entradas:** O conteúdo HTML/texto cru da página.
- **Saídas:** Um array ou objeto JSON contendo as críticas detalhadas, com o nível de "severity" (`low`, `medium`, `high`, `critical`) normalizado em letras minúsculas e mapeado num `Pydantic Model`.
- **Regras:** Sempre levanta um erro `RuntimeError` se não for possível extrair um JSON bem formado ou as análises estiverem incompletas.

### 3. Writer Agent (Bolt / Creator)
- **Função:** Reescreve e formata o conteúdo baseando-se nas diretrizes do style guide e nas críticas fornecidas pelo Analyst Agent.
- **Entradas:** Texto original + Críticas fornecidas pelo Analyst + Contexto RAG recuperado (`List[str]`) que ajuda na verificação cruzada (evitando que a página conteste ou contradiga outros conteúdos existentes no RAG).
- **Saídas:** Texto reescrito em formato HTML (mantendo as estruturas HTML brutas como blocos de código e tabelas).
- **Regras:** O conteúdo refatorado deve preservar o formato final sem perda de dados semânticos originais importantes e estruturados. Erros devem gerar `RuntimeError`.

### 4. Reviewer Agent (Palette / Quality Assurance)
- **Função:** Garante que o texto final seja coeso e o conteúdo possua as melhorias apontadas nas críticas sem degradar outras partes. Verifica o status final do trabalho.
- **Entradas:** Texto original e o Texto Final produzido pelo Writer Agent.
- **Saídas:** Um status JSON contendo strings aliás estritas (como "approved", "accepted" ou "completed") indicando a prontidão para publicação (ou "rejected" caso falhe).
- **Regras:** Erros ou inconsistências indicam rejeição ou geram um fallback programático, e o resultado deve corresponder estritamente a um dos alias esperados.

## Considerações do Sistema e RAG:
- RAG: Particiona texto preservando palavras usando ChromaDB, indexado com overlapping de bordas seguras (1000/100).
- Fallbacks: Em caso de erro de parse, um `clean_json_response` stripa possíveis blocos Markdown de código do LLM.
- Persistência e Processamento: Os trabalhos ocorrem em background não interrompendo a ingestão em lote, reportando status via banco SQLite (com controle transacional WAL) ao cliente que chama a API.
