# Roadmap de Evolução — SivansAI (RAG do Acervo)

Este documento estabelece o plano de evolução técnica e funcional do **SivansAI**, organizado em marcos de desenvolvimento (*milestones*), prioridades e impacto esperado.

---

## Visão Geral das Fases

```mermaid
flowchart LR
    Fase1["Fase 1 (v1.1)<br/>UX & Latência"] --> Fase2["Fase 2 (v1.2)<br/>Qualidade RAG & Ingestão"]
    Fase2 --> Fase3["Fase 3 (v1.3)<br/>Pipeline & Dados"]
    Fase3 --> Fase4["Fase 2.0<br/>Produção & Governança"]
```

---

## 🎯 Fase 1 (v1.1) — Experiência do Usuário e Percepção de Velocidade

**Objetivo:** Reduzir o tempo de espera perceptível do usuário e enriquecer a visualização das evidências.

- [ ] **Streaming de Respostas Token por Token**
  - **Prioridade:** Alta | **Impacto:** Alto (UX)
  - Implementar rota com `StreamingResponse` na FastAPI utilizando Server-Sent Events (SSE).
  - Consumir via `st.write_stream` no Streamlit, reduzindo o *Time to First Token* (TTFT) de ~20s para < 1s.
- [ ] **Player de Vídeo no Ponto Citado (Timestamp Direct Link)**
  - **Prioridade:** Média | **Impacto:** Médio
  - Em fontes vindas de vídeo (`Minuto MM:SS`), renderizar player `st.video` com parâmetro `start_time` automático.
- [ ] **Destaque Visual de Termos do Glossário**
  - **Prioridade:** Baixa | **Impacto:** Médio
  - Exibir no frontend quais termos da pergunta foram identificados e expandidos pelo glossário temático.

---

## 🔬 Fase 2 (v1.2) — Calibração do RAG e Ingestão Especializada

**Objetivo:** Elevar a métrica de *Answer Relevancy* (atualmente em 0.54) e aperfeiçoar a captura de áudio.

- [ ] **Otimização do System Prompt (Answer Relevancy)**
  - **Prioridade:** Alta | **Impacto:** Alto (Qualidade)
  - Ajustar o prompt de sistema para instruir o LLM a responder diretamente à pergunta na primeira sentença antes de aprofundar nas evidências contextuais.
- [ ] **Transcrição Whisper com `initial_prompt` do Glossário**
  - **Prioridade:** Alta | **Impacto:** Alto (Dados)
  - Injetar os termos doutrinários do `glossario.json` no parâmetro `initial_prompt` do `faster-whisper`, forçando o modelo acústico a transcrever nomes próprios e palavras específicas corretamente.
- [ ] **OCR Automático para PDFs Escaneados**
  - **Prioridade:** Média | **Impacto:** Alto (Cobertura de Acervo)
  - Implementar fallback com `ocrmypdf` ou `pytesseract` caso uma página de PDF extraia menos de 50 caracteres via PyMuPDF.
- [ ] **Avaliação com Modelos de 3B Parâmetros**
  - **Prioridade:** Média | **Impacto:** Médio
  - Benchmark comparativo entre `qwen2.5:1.5b`, `qwen2.5:3b` e `llama3.2:3b` avaliando o custo de memória versus ganho de coerência textual.

---

## 🗄️ Fase 3 (v1.3) — Engenharia de Dados e Escalabilidade

**Objetivo:** Fortalecer a robustez do armazenamento e permitir acervos de grande escala.

- [ ] **Sincronização Bidirecional da Pasta do Acervo**
  - **Prioridade:** Média | **Impacto:** Médio
  - Ajustar o `watcher.py` para detectar remoção de arquivos e disparar a limpeza de chunks obsoletos no Qdrant e no MinIO.
- [ ] **Índice BM25 Persistente em Disco**
  - **Prioridade:** Média | **Impacto:** Médio (Escalabilidade)
  - Substituir a lista BM25 em memória por uma base SQLite com `FTS5` (Full-Text Search) ou `Tantivy`, suportando centenas de milhares de chunks sem sobrecarregar a memória RAM.
- [ ] **Rotinas Automatizadas de Backup e Restore**
  - **Prioridade:** Alta | **Impacto:** Alto (Resiliência)
  - Scripts para snapshot automático dos volumes MinIO (`backup_minio_data`) e coleções do Qdrant (`qdrant_storage`).

---

## 🛡️ Fase 4 (v2.0) — Governança, Segurança e Produção

**Objetivo:** Habilitar compartilhamento seguro em rede e pipeline de integração contínua profissional.

- [ ] **Integração Contínua com GitHub Actions**
  - **Prioridade:** Alta | **Impacto:** Alto (DevOps)
  - Criação de workflow `.github/workflows/ci.yml` para validação de sintaxe, formatação e execução de testes automatizados a cada commit.
- [ ] **Controle de Acesso por Nível de Conteúdo (RBAC)**
  - **Prioridade:** Média | **Impacto:** Alto (Governança)
  - Adicionar metadado de confidencialidade aos documentos (`publico` vs. `interno`) e filtrar na busca com base nas permissões do usuário.
- [ ] **Autenticação na API e no Frontend**
  - **Prioridade:** Média | **Impacto:** Alto (Segurança)
  - Proteção por token Bearer / JWT na FastAPI e tela de login simples no Streamlit.
- [ ] **Observabilidade com OpenTelemetry / Tracing**
  - **Prioridade:** Baixa | **Impacto:** Médio
  - Rastreamento completo de latência por etapa: Embeddings ➔ Qdrant ➔ BM25 ➔ Reranker ➔ Ollama.

---

Para detalhes técnicos de implementação e snippets de código de cada funcionalidade planejada, consulte [docs/SUGESTOES_DE_MELHORIAS.md](docs/SUGESTOES_DE_MELHORIAS.md).
