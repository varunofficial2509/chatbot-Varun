# Knowledge base

Grounding data for the AI assistant on this site. Two different jobs, two different places:

- **`profile.json`** — structured facts: skills, role history, per-technology depth
  (`technical_experience`), projects, performance metrics, even the chatbot's own
  instructions. Already comprehensive; injected into every chat request as-is. Edit
  this file for anything list- or fact-shaped.
- **This file, and any other Markdown dropped in here** — freeform narrative knowledge
  that doesn't fit a structured field: project stories, write-ups, anything better told
  in prose. Chunked, embedded into the vector store, and retrieved per question.
  Markdown files stay on disk after indexing (unlike PDFs, which get deleted once
  embedded) — they're meant to be edited and re-synced over time, not uploaded once
  and forgotten.

## Adding or updating knowledge

1. Add a new `.md` file here, or edit this one.
2. Go to `/admin` → **Sync Knowledge Base** (or just restart the app — it syncs on
   startup). Editing an existing file re-embeds only that file; unchanged files are
   skipped.
3. Name the file after its *topic*, lowercase-with-hyphens — e.g. `genai-projects.md`,
   `leadership.md` — not after a resume export. That filename is exactly what shows up
   as the cited "source" in the assistant's Sources panel, so a name like
   `Varun_Teja_SDE_Java_FullStack.pdf` reads badly there; `genai-projects.md` doesn't.
4. Don't put anything here that a random visitor shouldn't be able to ask the
   assistant about and get back verbatim — this is open retrieval, not
   access-controlled. Keep phone numbers, family/parent names, ID or registration
   numbers, mark sheets, etc. out. Public contact channels (email, LinkedIn, GitHub,
   portfolio) already live in `data/profile.json`'s `contact` block, which powers the
   sidebar's Contact dialog and portfolio link — no need to repeat them here.

## Project narrative (not already in profile.json)

`profile.json` covers Varun's skills, role history, and the Aviation Maintenance RAG
Chatbot at a high level already. A few project details are only told here, as short
points rather than prose (keeps each retrieved chunk quick to scan):

### Aero-Webb RAG Chatbot — the fuller story

- Indexes product documentation, source code, functional specs, and historical Jira
  data (around 100K tickets, with descriptions and assigned developers) into a
  pgvector store.
- Lets engineers and BAs ask natural-language questions like "who last worked on this
  module" or "how does this feature behave."
- Includes a ticket-creation agent for Business Analysts: given a plain-language
  requirement or bug description, it drafts the ticket fields, creates the ticket via
  the Jira API, and returns a direct link — replacing manual form-filling with a
  single conversational request.

### Smart Log Analyzer & Alerting System

- LLM-powered log analysis pipeline: Spring Boot, Kafka, LangChain, OpenAI API,
  pgvector, Redis.
- Ingests application logs via Kafka, detects anomalies using semantic search, and
  auto-generates root-cause summaries.
- RAG-based retrieval layer on pgvector matches incoming error patterns against
  historical incident reports, to reduce mean time to diagnose.
- Redis handles deduplication of repeated alerts, with threshold-based notification
  routing to Slack and email.

### Movie & Event Booking System

- Full-stack event booking platform: Angular, Spring Boot, Kafka, Redis, MySQL.
- Kafka-based async notifications.
- Redis caching for roughly 35% faster seat queries.
- Optimistic locking for booking concurrency.
- JWT-based security.
- Code published on Varun's GitHub (https://github.com/varunofficial2509).
