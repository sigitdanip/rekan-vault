# RekanVault — Notion Golden Question Set

- **Owner**: Sigit (`RV-DEC-0015`)
- **Status**: Active / Benchmark Ready
- **Created**: 2026-08-11
- **Corpus Source**: Pilot Notion root page "Sulaiman OS" (`3b2aeb25-2cf1-80b5-acc1-c3225200ce27`) — 126 pages, 1,033 blocks across 4 databases
- **Source type**: `notion`
- **Note**: Target source uses page titles since Notion chunks carry `doc_title` in metadata (not file paths).
- **Total**: 42 questions (EXACT, ID_SEMANTIC, EN_SEMANTIC, FILTER, TEMPORAL, NEGATIVE, SYNTHESIS, MULTIHOP, CONFLICT)

---

## Change Review Discipline (`RV-DEC-0015`)

Per `RV-DEC-0015`, any modification to an existing question's expected answer or evidence target MUST record a stated reason in the log below.

| Date | Q-ID | Action | Reason | Stated By |
|---|---|---|---|---|
| 2026-08-11 | NQ-001–NQ-030 | Initial Batch Creation | Grounded on Notion Sulaiman OS corpus scan (126 pages, 1033 blocks) | Sisyphus |
| 2026-08-12 | NQ-061–NQ-072 | SYNTHESIS + MULTIHOP + CONFLICT | Cross-document analysis of 126-page Notion corpus — covers SLEMAN architecture, RMU pivot, AI stack, Islamic finance, and naming variants | Sisyphus |

---

## Benchmark Question Categories

1. **EXACT**: Exact page title or key phrase matches.
2. **ID_SEMANTIC**: Indonesian language semantic retrieval queries.
3. **EN_SEMANTIC**: English language semantic retrieval queries.
4. **NEGATIVE**: Unanswerable / out-of-corpus queries (must return `INSUFFICIENT_EVIDENCE`).
5. **FILTER**: Source-type, block-type, or Notion-specific metadata filtering.
6. **TEMPORAL**: Date-anchored content from Notion conversation logs.
7. **SYNTHESIS**: Multi-page synthesis requiring 2+ source citations.
8. **MULTIHOP**: Relationship and entity-traversal queries across Notion pages.
9. **CONFLICT**: Naming/terminology variant queries where both forms are valid.

---

## Golden Question Set (NQ-001 to NQ-030)

| ID | Category | Question | Target Source / Path | Expected Answer / Evidence Key |
|---|---|---|---|---|
| `NQ-001` | EXACT | "Sulaiman OS" | `Sulaiman OS` | Root operating system page for SULAIMAN — single source of truth for all knowledge, decisions, experiments, ideas, and execution logs. |
| `NQ-002` | EXACT | "IDENTITY LOG (1)" | `🧬 IDENTITY LOG (1)` | Core identity record for Ibrahim Muhammad Isa — full name, role, mindset, and life context. |
| `NQ-003` | EXACT | "Framework Operational Intelligence vs ERP" | `Framework Operational Intelligence vs ERP` | Perbedaan fundamental: ERP menyimpan data dan mencatat transaksi, sementara Operational Intelligence mencari insight. |
| `NQ-004` | EXACT | "Dompet Kita" | `Dompet Kita — Family Finance & Spending Discipline Redesign` | Family finance web app berbasis iPhone via Add to Home Screen untuk Imi dan Heni. |
| `NQ-005` | EXACT | "Quantization vs Sampling" | `Quantization vs Sampling — Perbedaan Fundamental` | Sampling: pilih sebagian data representatif. Quantization: simpan semua data dengan presisi lebih rendah. |
| `NQ-006` | EXACT | "TurboVec & TurboQuant" | `TurboVec & TurboQuant — Revolusi Kompresi Vector AI` | Library vector index Rust berdasarkan algoritma TurboQuant dari Google Research (ICLR 2026). |
| `NQ-011` | ID_SEMANTIC | "Bagaimana arsitektur knowledge acquisition SLEMAN menggunakan multi-agent AI?" | `Arsitektur Knowledge Acquisition SLEMAN Menggunakan Multi-Agent AI` | Claude sebagai gatekeeper dan reviewer via Notion MCP, GPT sebagai knowledge collector, membangun infrastructure melalui pembagian peran. |
| `NQ-012` | ID_SEMANTIC | "Apa perbedaan antara SLEMAN sebagai internal operating system dan Rekan sebagai commercial layer?" | `SLEMAN sebagai Internal Operating System dan Rekan sebagai Commercial Layer` | SLEMAN adalah operating system internal, sementara Rekan adalah commercial layer yang terpisah secara strategis. |
| `NQ-013` | ID_SEMANTIC | "Mengapa Rekan Makmur Utama pivot dari ERP ke Operational Intelligence?" | `Pivot Rekan Makmur Utama dari ERP ke Operational Intelligence` | Tidak akan membangun ERP baru — arah produk diubah menjadi Intelligence Layer. |
| `NQ-014` | ID_SEMANTIC | "Apa empat lini produk Rekan Makmur Utama?" | `Pembentukan 4 Lini Produk Rekan Makmur Utama` | RekanOps (Operational Intelligence), RekanReport, dan dua domain intelligence lainnya. |
| `NQ-015` | ID_SEMANTIC | "Bagaimana konsep AI Loop Autonomous dijelaskan?" | `AI Loop Autonomous — Manusia Bukan Satu-satunya Driver Percepatan` | AI sekarang ikut mengembangkan AI — loop percepatan bukan lagi linear tapi otonom dan eksponensial. |
| `NQ-016` | ID_SEMANTIC | "Bagaimana RMU diposisikan sebagai Business Health Platform?" | `RMU Sebagai Business Health Platform` | Sebagian besar masalah klien adalah gejala kesehatan bisnis — bukan masalah teknologi. |
| `NQ-017` | ID_SEMANTIC | "Bagaimana framework 30 hari discovery RMU bekerja?" | `30 Hari Discovery Framework RMU` | Prioritas 30 hari pertama: membangun Discovery Framework untuk menjawab pertanyaan tentang kebocoran uang. |
| `NQ-018` | ID_SEMANTIC | "Apa pendekatan anomaly-centric thinking vs KPI-centric thinking?" | `Anomaly-Centric Thinking vs KPI-Centric Thinking` | Pergeseran dari pencarian KPI universal menuju pencarian pola anomali universal. |
| `NQ-021` | EN_SEMANTIC | "How is data imperfection used as a strategic moat?" | `Data Imperfection as Strategic Moat` | RMU's advantage should not depend on clean, complete data — the intelligence framework absorbs imperfection. |
| `NQ-022` | EN_SEMANTIC | "What is the 13-era data technology journey framework?" | `Peta Perjalanan Teknologi Data — Era 1 sampai 13 (Terkalibrasi)` | Framework 13 era dari Dataisme (Harari) hingga Singularity (Kurzweil). |
| `NQ-023` | EN_SEMANTIC | "How does operational intelligence differ from software-based discovery?" | `Operational Intelligence Berbasis Discovery, Bukan Software` | Nilai utama RMU bukan pada software atau dashboard — melainkan pada discovery framework. |
| `NQ-024` | EN_SEMANTIC | "What is the SULAIMAN OS architecture?" | `Sulaiman OS` | capture → store → retrieve → log → decision trail — single source of truth queried by any AI. |
| `NQ-025` | EN_SEMANTIC | "How does the domain convergence in Era 10-12 create cross-domain opportunities?" | `Konvergensi Domain Era 10–12 — Peluang Cross-Domain Orchestrator` | Neurologi, bioscience, IoT, nanotech, agrotech converge — orchestrator opportunity for cross-domain data management. |
| `NQ-031` | FILTER | "Tampilkan semua halaman Notion tentang SLEMAN" | `SLEMAN` | Multiple SLEMAN-related pages including Skill Tree, Guardrail, Knowledge Acquisition, and OS architecture. |
| `NQ-032` | FILTER | "Cari semua dokumen dari source type notion tentang trading atau quant" | `Quant` | Quant Scanner V3 pages, Islamic Finance Framework, Arryeah Trading System. |
| `NQ-033` | FILTER | "Tampilkan halaman Notion yang membahas AI infrastructure atau stack" | `AI` | AI Loop Autonomous, Arsitektur Hybrid AI Stack, AI sebagai Infrastruktur Geopolitik, Peluang AI Asia. |
| `NQ-034` | FILTER | "Daftar semua halaman Notion yang sudah di-archive" | `ARCHIVED` | [ARCHIVED] RMU Product Family Architecture, [ARCHIVED] Business Vital Signs Analogy, [ARCHIVED] Design RMU Operational Intelligence Framework, [ARCHIVED] RMU Discovery-First Strategy. |
| `NQ-041` | NEGATIVE | "What is the stock price of Tesla as of August 2026?" | None | `INSUFFICIENT_EVIDENCE` — Real-time stock data not in Sulaiman OS corpus. |
| `NQ-042` | NEGATIVE | "Siapa presiden Indonesia pada tahun 1945?" | None | `INSUFFICIENT_EVIDENCE` — Historical trivia not present in Sulaiman OS knowledge base. |
| `NQ-043` | NEGATIVE | "What is the chemical formula for graphene?" | None | `INSUFFICIENT_EVIDENCE` — General science facts not covered in this corpus. |
| `NQ-044` | NEGATIVE | "Bagaimana cara memasak rendang Padang yang autentik?" | None | `INSUFFICIENT_EVIDENCE` — Culinary recipes not present in Sulaiman OS. |
| `NQ-051` | TEMPORAL | "Apa yang terjadi pada update 2026-06-27 tentang siklus kehancuran finansial futures?" | `🔄 UPDATE 2026-06-27 — Siklus Kehancuran Finansial Futures 5 Tahun: Analisis Neurobiologis` | Pola kritis 5 tahun (2021-2026): setiap kali Imi punya uang, masuk futures, dan habis — analisis neurobiologis tentang addiction loop. |
| `NQ-052` | TEMPORAL | "Kapan pivot Rekan Makmur Utama dari ERP ke Operational Intelligence diputuskan?" | `Pivot Rekan Makmur Utama dari ERP ke Operational Intelligence` | 2026-06-10 — percakapan dan migrasi terjadi pada tanggal tersebut. |
| `NQ-053` | TEMPORAL | "Apa IDENTITY LOG terakhir dan kapan terakhir diupdate?" | `🧬 IDENTITY LOG (1)` | Last updated 2026-05-30 — update when there is significant shift in role, mindset, or life context. |
| `NQ-061` | SYNTHESIS | "Bagaimana hubungan antara konsep SLEMAN sebagai internal operating system dengan pivot Rekan Makmur Utama dari ERP ke Operational Intelligence?" | `SLEMAN sebagai Internal Operating System dan Rekan sebagai Commercial Layer` & `Pivot Rekan Makmur Utama dari ERP ke Operational Intelligence` | SLEMAN adalah OS internal (knowledge, decision trail) sementara pivot RMU mengalihkan arah dari membangun ERP baru menjadi Intelligence Layer — keduanya terpisah secara strategis namun SLEMAN menjadi fondasi knowledge yang dimonetisasi melalui Rekan. |
| `NQ-062` | SYNTHESIS | "Apa keterkaitan antara AI Loop Autonomous, MCP sebagai Universal Execution Layer, dan Arsitektur Hybrid AI Stack?" | `AI Loop Autonomous — Manusia Bukan Satu-satunya Driver Percepatan` & `MCP sebagai Universal Execution Layer — Paradigm Shift dari Chatbot ke AI Agent` & `Arsitektur Hybrid AI Stack — Google + Claude + OpenAI + Open Source` | AI Loop Autonomous menjelaskan percepatan eksponensial (AI mengembangkan AI), MCP menyediakan execution layer universal, dan Hybrid AI Stack menyediakan infrastruktur multi-provider — ketiganya membentuk ekosistem AI otonom Rekan. |
| `NQ-063` | SYNTHESIS | "Bagaimana framework Islamic Finance dipadukan dengan Arryeah Trading System untuk trading instruments?" | `Islamic Finance Framework untuk Trading Instruments` & `Arryeah Trading System Framework — Multi-Layer Screening untuk AI Robot Trading` | Islamic Finance memberikan batasan syariah (instrumen, akad) sedangkan Arryeah menyediakan technical screening multi-layer — kombinasi screening syariah + technical untuk AI robot trading. |
| `NQ-064` | SYNTHESIS | "Bagaimana konsep Data Imperfection sebagai Strategic Moat berhubungan dengan Anomaly-Centric Thinking?" | `Data Imperfection as Strategic Moat` & `Anomaly-Centric Thinking vs KPI-Centric Thinking` | Data imperfection menjadi moat strategis karena RMU tidak bergantung pada data bersih — framework anomaly-centric mencari pola anomali universal, bukan KPI universal. |
| `NQ-065` | MULTIHOP | "Sistem AI apa yang dirancang sebagai navigator eksplorasi ilmu dan bagaimana arsitektur knowledge acquisition-nya menggunakan multi-agent AI?" | `Konsep AI Sulaiman sebagai Navigator Eksplorasi Ilmu dan Masa Depan` & `Arsitektur Knowledge Acquisition SLEMAN Menggunakan Multi-Agent AI` | AI Sulaiman adalah sistem reflektif (bukan chatbot) yang menavigasi eksplorasi ilmu — knowledge acquisition menggunakan Claude sebagai gatekeeper/reviewer via Notion MCP dan GPT sebagai collector. |
| `NQ-066` | MULTIHOP | "Apa empat lini produk Rekan Makmur Utama dan bagaimana hubungannya dengan konsep Operational Intelligence berbasis Discovery?" | `Pembentukan 4 Lini Produk Rekan Makmur Utama` & `Operational Intelligence Berbasis Discovery` | 4 lini: RekanOps (Operational Intelligence), RekanReport, dan dua domain intelligence lainnya — nilai utama bukan pada software melainkan pada discovery framework. |
| `NQ-067` | MULTIHOP | "Bagaimana framework 30 hari discovery RMU berhubungan dengan MVP AI Reporting Layer sebagai langkah pertama?" | `30 Hari Discovery Framework RMU` & `MVP tidak dimulai dari ERP full` | 30 hari pertama fokus pada Discovery Framework untuk menjawab kebocoran uang — MVP dimulai dari AI Reporting Layer, bukan ERP full. |
| `NQ-068` | MULTIHOP | "Bagaimana GP Foundation 12 Pillar Structure berhubungan dengan visi AI Sulaiman sebagai navigator?" | `GP Foundation — 12 Pillar Structure Refinement` & `Konsep AI Sulaiman sebagai Navigator Eksplorasi Ilmu dan Masa Depan` | GP Foundation menyediakan 12 pilar struktural yayasan, sementara AI Sulaiman berfungsi sebagai sistem navigasi reflektif untuk eksplorasi ilmu dalam kerangka pilar tersebut. |
| `NQ-069` | CONFLICT | "Bagaimana variasi penulisan 'Sulaiman' vs 'SULAIMAN' vs 'SLEMAN' muncul di berbagai halaman Notion?" | `Sulaiman OS` & `Memisahkan Internal Knowledge dan External Knowledge dalam SLEMAN` | Halaman root menggunakan "Sulaiman OS" (proper case), halaman knowledge acquisition menggunakan "SLEMAN" (uppercase), dan beberapa halaman menggunakan "SULAIMAN" — ketiganya merujuk pada sistem yang sama. |
| `NQ-070` | CONFLICT | "Apakah penamaan sistem disebut 'AI Sulaiman' atau 'Sulaiman' dalam berbagai halaman?" | `Nama dan Peran AI: Sulaiman sebagai Sistem Reflektif` & `Konsep AI Sulaiman sebagai Navigator Eksplorasi Ilmu dan Masa Depan` | Halaman pertama menyebut "Sulaiman" sedangkan halaman kedua menyebut "AI Sulaiman" — keduanya valid merujuk pada sistem reflektif yang sama. |
| `NQ-071` | CONFLICT | "Bagaimana istilah 'Operational Intelligence' vs 'Intelligence Layer' digunakan dalam halaman yang berbeda?" | `Framework Operational Intelligence vs ERP` & `Pivot Rekan Makmur Utama dari ERP ke Operational Intelligence` | Framework menggunakan "Operational Intelligence" sebagai konsep, sedangkan halaman pivot menyebutnya "Intelligence Layer" sebagai arah produk — keduanya valid. |
| `NQ-072` | CONFLICT | "Apakah RMU disebut 'Rekan Makmur Utama', 'RMU', atau 'Rekanmu' dalam berbagai halaman?" | `Pivot Rekan Makmur Utama dari ERP ke Operational Intelligence` & `RMU Sebagai Business Health Platform` | Halaman pivot menggunakan "Rekan Makmur Utama" dan "Rekanmu", halaman health platform menggunakan "RMU" — ketiga sebutan merujuk entitas yang sama. |
