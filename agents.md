# Arquitetura de Agentes - ConfluenceRefiner

Este documento define as personas e o fluxo de trabalho dos agentes de IA no sistema ConfluenceRefiner.

## Visão Geral
O sistema utiliza um padrão de cadeia de responsabilidade onde cada agente possui uma função específica na refinação da documentação.

## Personas

### 1. Analyst Agent (O Analista)
**Responsabilidade:** Ler o texto cru extraído do Confluence e identificar problemas.
**Input:** Texto da página (raw), Metadados.
**Output:** Lista estruturada de críticas (issues).
**Critérios de Análise:**
- Clareza e concisão.
- Atualização (datas, versões de software mencionadas).
- Formatação (headers, code blocks).
- Tom de voz (deve ser técnico e formal).

### 2. Writer Agent (O Escritor)
**Responsabilidade:** Reescrever o conteúdo com base nas críticas do Analista e no Guia de Estilo.
**Input:** Texto original, Lista de críticas.
**Output:** Texto refinado (Markdown).
**Diretrizes:**
- Corrigir todas as críticas apontadas.
- Manter a estrutura lógica original, a menos que seja confusa.
- Garantir que exemplos de código estejam formatados corretamente.

### 3. Reviewer Agent (O Revisor)
**Responsabilidade:** Validar o texto refinado antes da publicação.
**Input:** Texto refinado, Texto original.
**Output:** Status (APROVADO / REJEITADO) e Comentários finais.
**Critérios:**
- O significado original foi preservado?
- O texto está alucinado (inventou informações)?
- As críticas do Analista foram resolvidas?

## Fluxo de Execução

1. **Ingestão:** `ConfluenceService` extrai a página.
2. **Retrieval:** `RAGService` busca contexto relevante (páginas relacionadas) para evitar contradições.
3. **Análise:** `Analyst Agent` processa o conteúdo + contexto.
4. **Escrita:** `Writer Agent` gera a nova versão.
5. **Revisão:** `Reviewer Agent` aprova ou solicita ajustes (loop opcional, por enquanto linear).
6. **Saída:** Resultado final é retornado via API.
