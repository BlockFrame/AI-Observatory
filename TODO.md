# AI Observatory — Strategic TODO & Project Backlog

Questo documento contiene la roadmap operativa e il backlog delle attività prioritarie per l'**AI Observatory**.

---

## 🎯 Attività Prioritarie (In Corso / Prossimi Step)

### 1. 📡 Espansione Fonti di Raccolta (Sources & Gatherers)
- [ ] **AI News**: Identificare e integrare nuovi feed RSS/Atom di testate giornalistiche, blog aziendali di AI Lab emergenti e newsletter di settore.
- [ ] **AI Research**: Aggiungere nuovi feed arXiv (es. cs.CL, cs.CV, cs.RO), blog accademici universitarie (Stanford, Oxford, CMU, Berkeley) e repository di preprint.
- [ ] **Twitter / X Profiles**: Espandere la lista di account monitorati (`twitter_accounts.txt`) includendo key opinion leader, ricercatori di punta (AI safety, LLM evaluation, agentic frameworks) e founder di startup AI emergenti.

### 2. 📖 Restyling & Refactoring del `README.md`
- [ ] Revisione completa del `README.md` per renderlo executive-grade e orientato alla community open-source.
- [ ] Inserimento badge ufficiali (GitHub Actions status, license, tech stack, GitHub Sponsors).
- [ ] Definizione chiara di Architecture Overview, Quick Start, Environment Setup e Guida al Contributo.
- [ ] Integrazione del welcome message e della sezione GitHub Sponsorships (`BlockFrame`).

### 3. 📚 Creazione GitHub Wiki
- [ ] Creazione della struttura documentale per la **GitHub Wiki** del repository (cartella `docs/wiki/`).
- [ ] **Architettura del Sistema**: Schemi sul ciclo di vita della pipeline multi-agente (Gathering → Analysis → Cross-Category Topic Detection → Executive Briefing).
- [ ] **Guida alla Configurazione Fonti**: Documentazione per aggiungere nuovi feed RSS, account X, e subreddits.
- [ ] **Guida agli Agenti & Prompts**: Descrizione dettagliata dei vari agenti (`news`, `research`, `social`, `reddit`) e della gestione prompt tramite `prompts.yaml`.
- [ ] **Guide all'Integrazione & API**: Documentazione del server MCP locale e dell'export dati (`ai-index.json`, `llms.txt`).

### 4. 🗺️ Elaborazione Roadmap Strategica
- [ ] Definizione dettagliata della **Roadmap Q3-Q4 2026**:
  - **Fase 1 — Core & Infrastructure**: Ottimizzazione costi API (GetXAPI, DeepSeek max 2 conc), integrazione Telegram/Discord alerts.
  - **Fase 2 — Data Expansion & Quality**: Supporto per la nuova categoria "Regulatory & Ethics", deduplicazione cross-fonte avanzata.
  - **Fase 3 — Community & Ecosystem**: GitHub Wiki, sponsorship hub, SDK client, integrazione MCP completa per AI IDE.
  - **Fase 4 — Advanced Analytics**: Sentiment analysis delle notizie, trend detection su 30/90 giorni per modellation/LLM.

### 5. 🧹 Repository Cleanup & Housekeeping
- [x] Identificazione e rimozione di script temporanei/un-off nella root (`fix_models.py`, `test_scrapers.py`, `test_router.py`, `test_openai_client.py`, legacy `collectors/` e `processors/`).
- [x] Consolidation e razionalizzazione dei documenti markdown sparsi (`VERCEL_*.md`, `REDDIT_GATHERER_HANDOFF.md`, `CYBERNETIC_BLUEPRINT_APPLIED.md`) trasferendoli in `docs/archived/`.
- [x] Rimozione completa codice e configurazioni Reddit non più desiderate.
- [x] Pulizia directory temporanee e backup locali (`.data-backup/`).
- [ ] Verifica ed estensione delle regole `.gitignore` e `.dockerignore`.

---

## 📌 Backlog Infrastrutturale & Feature

- [ ] **API Ufficiali Reddit (PRAW)**: Migrare da ScrapeCreators ad API ufficiali Reddit.
- [ ] **Privacy-friendly Analytics**: Integrare Plausible / Umami sul frontend SvelteKit.
- [ ] **Notifiche Multi-Channel**: Bot Telegram (già avviato) + Webhook Discord per breaking news.
- [ ] **MCP Server Enhancements**: Estendere le capability del server MCP locale per consentire chiamate semantiche avanzate.
