# AI Observatory — Strategic TODO

Questo documento contiene l'elenco aggiornato delle sole attività aperte e da completare per l'**AI Observatory**.

---

## 🎯 Attività Aperte

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

- [ ] **Privacy-friendly Analytics**: Integrare Plausible / Umami sul frontend SvelteKit.
- [ ] **Webhook Discord**: Aggiungere supporto per notifiche Discord oltre al bot Telegram.
- [ ] **MCP Server Enhancements**: Estendere le capability di ricerca semantica del server MCP locale (`mcp_server.py`).
