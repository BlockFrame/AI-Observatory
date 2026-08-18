# Wiredframe Radar — Strategic TODO

Questo documento contiene lo stato aggiornato delle attività strategiche per **Wiredframe Radar**.

---

## 🎯 Attività Aperte

### 0. 🛡️ Affidabilità, Qualità Editoriale & Osservabilità
- [x] **Quality score per report e categoria**: calcolare e pubblicare segnali deterministici su lunghezza, copertura dei top item, fallback LLM, validità Markdown/link e qualità delle fonti; bloccare la pubblicazione sotto soglia.
- [x] **Separazione ranking / scrittura**: modelli specialistici per ranking/estrazione e route quality dedicate con fallback espliciti per le summary editoriali.
- [x] **Telemetria LLM per categoria**: `summary.json` espone modello, provider, durata, token, retry/fallback e stato per News, Social, Research e GitHub Trending.
- [x] **Osservabilità dei gatherer**: dashboard/stato per fonte con ultimo successo, articoli raccolti, latenza, errore, tasso di duplicati e freshness del feed.
- [x] **Alert funnel per fonte**: esporre raccolti → analizzati → top-ranked → citati e segnalare fonti attive ma silenziate, senza alterare il ranking editoriale.
- [x] **Test end-to-end della resilienza**: fixture realistiche per timeout NVIDIA, 429 Gemini, JSON troncato, feed vuoti e fallback; verificare che il publish gate rifiuti report di bassa qualità.
- [x] **Link enrichment efficiente**: eseguire prima entity matching deterministico e inviare al modello solo riferimenti ambigui, riducendo latenza, token e chiamate LLM.
- [x] **Cache semantica degli articoli**: usare checksum del contenuto e cache di analisi per evitare rielaborazioni di articoli ripubblicati da più feed.
- [ ] **Usage accounting OpenRouter autorevole**: acquisire dalle risposte `usage.cost`, reasoning token e cache token reali, mantenendo il tracker locale come vista cross-provider e riconciliando gli scostamenti dal listino statico.
- [ ] **Correlazione delle trace LLM**: assegnare un `run_id` alla pipeline e propagare fase, caller, coverage date, release e fallback come metadata, così da ricostruire `run → fase → chiamata` anche nei sistemi esterni.
- [ ] **Valutazione Langfuse end-to-end**: dopo 3-5 run OpenRouter reali, valutare Langfuse per tracing multi-provider, prompt versioning, dataset ed eval; usare sampling/privacy mode per prompt e output e considerare LangSmith solo in caso di adozione LangChain/LangGraph.
- [ ] **Replay selettivo degli errori LLM**: conservare prompt/output completi solo per chiamate fallite o campionate, con redazione dei dati sensibili e retention esplicita, senza pubblicarli negli artifact del frontend.

### 1. 📡 Espansione Fonti di Raccolta (Sources & Gatherers)
- [ ] **AI News**: Identificare e integrare nuovi feed RSS/Atom di testate giornalistiche tech, blog di AI Lab emergenti e newsletter di settore (`config/rss_feeds.txt`).
- [ ] **AI Research**: Aggiungere nuovi feed arXiv (es. cs.CL, cs.CV, cs.AI) e blog accademici universitari (Stanford, MIT, Oxford, CMU, Berkeley) (`config/research_feeds.txt`).
- [ ] **Twitter / X Profiles**: Espandere la lista degli account monitorati (`config/twitter_accounts.txt`) includendo key opinion leader (AI safety, LLM eval, agentic frameworks) e founder di startup AI emergenti.

### 2. 📖 Restyling & Refactoring del `README.md`
- [ ] Revisione completa del `README.md` per renderlo executive-grade e orientato alla community open-source.
- [ ] Inserimento dei badge ufficiali aggiornati (GitHub Actions status, Licenza Apache 2.0, Tech Stack, GitHub Sponsors).
- [ ] Aggiornamento dell'Architecture Overview, Quick Start e sezione Contributi rimuovendo riferimenti obsoleti.
- [ ] Integrazione del welcome message e della sezione GitHub Sponsorships ufficiale per `BlockFrame`.

### 3. 📚 Creazione GitHub Wiki (`docs/wiki/`)
- [ ] Creazione della struttura documentale per la **GitHub Wiki** del repository (nella directory `docs/wiki/`).
- [ ] **Architettura del Sistema**: Schemi sul ciclo di vita della pipeline multi-agente (Gathering → Analysis → Topic Detection → Briefing).
- [ ] **Guida alla Configurazione Fonti**: Documentazione per aggiungere e gestire feed RSS ed account X.
- [ ] **Guida agli Agenti & Prompts**: Descrizione dettagliata dei vari agenti (`news`, `research`, `social`, `github_trending`) e personalizzazione tramite `prompts.yaml`.
- [ ] **Guide all'Integrazione & API**: Documentazione del server MCP locale e degli export dati (`ai-index.json`, `llms.txt`).

### 4. 🗺️ Elaborazione Roadmap Strategica
- [ ] Stesura del documento **Roadmap Q3-Q4 2026** (`docs/ROADMAP.md`):
  - **Fase 1 — Core & Infrastructure**: Notifiche Discord per breaking news.
  - **Fase 2 — Data Expansion & Quality**: Supporto per la nuova categoria "Regulatory & Ethics", deduplicazione cross-fonte avanzata.
  - **Fase 3 — Community & Ecosystem**: GitHub Wiki, sponsorship hub, SDK client, integrazione MCP completa per AI IDE.
  - **Fase 4 — Advanced Analytics**: Sentiment analysis delle notizie e trend detection su 30/90 giorni per modellatione/LLM.

---

## 📌 Backlog Feature

- [ ] **Technical Updates**: creare una sezione separata per release note, breaking change, SDK/framework update e integrazioni tecniche (LangChain, CopilotKit, LangGraph, n8n, ecc.), distinta dall'Executive Briefing e non soggetta al ranking editoriale strategico.
- [ ] **“Why it matters”**: aggiungere per ogni notizia una sintesi strutturata di impatto, urgenza e destinatario decisionale.
- [ ] **Storyline & follow-up**: raggruppare aggiornamenti della stessa storia in una timeline a 7/30 giorni.
- [ ] **Digest personalizzato**: filtri persistenti per aziende, modelli, temi e ruolo dell'utente; generazione di una daily digest mirata.
- [ ] **Alert selettivi**: notifiche ad alta confidenza per release frontier, benchmark, funding, policy e segnali di rischio.
- [ ] **Evidence view**: rendere visibili fonti, confidenza, motivazione del ranking e percorso di generazione per ogni insight.
- [ ] **Ecosystem comparison dashboard**: confronto tra provider/modelli per capacità, costo, API, benchmark, release e segnali social.
- [ ] **Privacy-friendly Analytics**: Integrare Plausible / Umami sul frontend SvelteKit.
- [ ] **Webhook Discord**: Aggiungere supporto per notifiche Discord oltre al bot Telegram.
- [ ] **MCP Server Enhancements**: Estendere le capability di ricerca semantica del server MCP locale (`mcp_server.py`).
