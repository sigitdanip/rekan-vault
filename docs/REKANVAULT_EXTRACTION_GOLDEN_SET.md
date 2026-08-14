# RekanVault — Labeled Extraction Golden Set (`P5-T1` / `RV-DEC-P5-0001`)

- **Owner**: Sigit (`RV-DEC-0015`)
- **Status**: Active / Benchmark Ready
- **Last Updated**: 2026-08-12
- **Corpus Source**: Pilot Google Drive (`SOP_Presales_RekanDigital.docx`, `SOP_Eksekusi_Proyek_Development.docx`, `rekanmu` technical specs) & Notion (`Sulaiman OS`)
- **Memory Types Covered**: All 18 enabled memory types (`Fact`, `Claim`, `Decision`, `Policy`, `Procedure`, `Event`, `Project`, `Task`, `Idea`, `Risk`, `Assumption`, `Lesson`, `Metric`, `Person`, `Organization`, `Topic`, `Asset`, `Skill`).

---

## Change Review Discipline (`RV-DEC-0015`)

Per `RV-DEC-0015`, any modification to an existing extraction test case's expected memory JSON or target chunk locator MUST record a stated reason in the log below.

| Date | EXT-ID | Action | Reason | Stated By |
|---|---|---|---|---|
| 2026-08-12 | EXT-001–EXT-018 | Initial Golden Set Creation | Grounded on live pilot corpus across all 18 typed memory schemas | Sigit / Antigravity |

---

## Extraction Test Cases

### EXT-001 — Fact
- **Memory Type**: `Fact`
- **Target Locator**: `SOP_Presales_RekanDigital.docx#v1#chunk_001`
- **Input Text**:
  ```text
  Standard Operating Procedure Presales PT Rekan Digital Indonesia memiliki kode dokumen SOP-RD-PRESALES-001 dan berlaku efektif sejak 15 Januari 2026.
  ```
- **Expected Memory**:
  ```json
  {
    "memory_type": "Fact",
    "title": "Kode Dokumen dan Tanggal Efektif SOP Presales",
    "summary": "SOP Presales PT Rekan Digital Indonesia berkode SOP-RD-PRESALES-001 dan berlaku sejak 15 Januari 2026.",
    "statement": "SOP Presales PT Rekan Digital Indonesia memiliki kode SOP-RD-PRESALES-001 dan efektif per 15 Januari 2026.",
    "verification_method": "Document Header Inspection",
    "impact": "MEDIUM"
  }
  ```

---

### EXT-002 — Claim
- **Memory Type**: `Claim`
- **Target Locator**: `SOP_Presales_RekanDigital.docx#v1#chunk_002`
- **Input Text**:
  ```text
  Tim presales mengklaim bahwa tingkat konversi proposal teknis meningkat sebesar 35% setelah penerapan template proposal terstandar v2.0.
  ```
- **Expected Memory**:
  ```json
  {
    "memory_type": "Claim",
    "title": "Peningkatan Konversi Proposal Teknis 35%",
    "summary": "Penerapan template proposal terstandar v2.0 diklaim meningkatkan konversi proposal teknis sebesar 35%.",
    "assertion": "Template proposal v2.0 meningkatkan konversi presales sebesar 35%.",
    "supports_count": 1,
    "contradicts_count": 0,
    "impact": "MEDIUM"
  }
  ```

---

### EXT-003 — Decision
- **Memory Type**: `Decision`
- **Target Locator**: `SOP_Eksekusi_Proyek_Development.docx#v1#chunk_005`
- **Input Text**:
  ```text
  Manajemen memutuskan bahwa seluruh repositori proyek baru harus menggunakan monorepo modular monolith dengan Python 3.12 dan PostgreSQL hosted di Supabase, menolak usulan microservices dan Redis.
  ```
- **Expected Memory**:
  ```json
  {
    "memory_type": "Decision",
    "title": "Keputusan Arsitektur Modular Monolith dan Supabase PostgreSQL",
    "summary": "Seluruh repositori proyek baru wajib menggunakan modular monolith Python 3.12 dan PostgreSQL Supabase.",
    "rationale": "Menjaga kesederhanaan operasional VPS single-node dan performa transactional.",
    "alternatives_considered": ["Microservices Architecture", "Mandatory Redis dependency"],
    "decision_maker": "Manajemen Rekan Digital",
    "status": "active",
    "impact": "HIGH"
  }
  ```

---

### EXT-004 — Policy
- **Memory Type**: `Policy`
- **Target Locator**: `SOP_Presales_RekanDigital.docx#v1#chunk_004`
- **Input Text**:
  ```text
  Setiap penawaran harga presales dengan nilai di atas Rp 100.000.000 wajib mendapatkan persetujuan tertulis dari VP of Engineering dan Managing Director sebelum dikirimkan ke klien.
  ```
- **Expected Memory**:
  ```json
  {
    "memory_type": "Policy",
    "title": "Persetujuan Penawaran Presales > Rp 100 Juta",
    "summary": "Penawaran presales melebihi Rp 100 juta wajib mendapat persetujuan tertulis VP of Engineering dan Managing Director.",
    "directive": "Persetujuan ganda (VP Eng + MD) wajib untuk penawaran > Rp 100.000.000.",
    "enforcement_scope": "Presales Division",
    "mandatory": true,
    "impact": "HIGH"
  }
  ```

---

### EXT-005 — Procedure
- **Memory Type**: `Procedure`
- **Target Locator**: `SOP_Eksekusi_Proyek_Development.docx#v1#chunk_008`
- **Input Text**:
  ```text
  Tahapan rilis staging proyek: 1. Jalankan ruff check dan mypy strict. 2. Jalankan pytest test suite lengkap. 3. Ekspor Pydantic schema kontrak. 4. Deploy build ke VPS staging.
  ```
- **Expected Memory**:
  ```json
  {
    "memory_type": "Procedure",
    "title": "Tahapan Rilis Staging Proyek",
    "summary": "Prosedur 4 langkah rilis staging meliputi linter, typecheck, pytest, ekspor skema, dan deployment.",
    "steps": [
      "Jalankan ruff check dan mypy strict",
      "Jalankan pytest test suite lengkap",
      "Ekspor Pydantic schema kontrak",
      "Deploy build ke VPS staging"
    ],
    "prerequisites": ["CI check pass", "Pre-merge code review"],
    "impact": "MEDIUM"
  }
  ```

---

### EXT-006 — Event
- **Memory Type**: `Event`
- **Target Locator**: `SOP_Presales_RekanDigital.docx#v1#chunk_010`
- **Input Text**:
  ```text
  Sesi Kick-off Proyek RekanVault v0.1.0 dilaksanakan pada tanggal 2 Februari 2026 bertempat di Ruang Rapat Utama RekanDigital Jakarta dan dihadiri tim pengembang serta VP Engineering.
  ```
- **Expected Memory**:
  ```json
  {
    "memory_type": "Event",
    "title": "Kick-off Proyek RekanVault v0.1.0",
    "summary": "Pelaksanaan sesi kick-off proyek RekanVault v0.1.0 pada 2 Februari 2026 di Jakarta.",
    "occurred_at": "2026-02-02T09:00:00Z",
    "location": "Ruang Rapat Utama RekanDigital Jakarta",
    "participants": ["Tim Pengembang", "VP Engineering"],
    "impact": "MEDIUM"
  }
  ```

---

### EXT-007 — Project
- **Memory Type**: `Project`
- **Target Locator**: `SOP_Eksekusi_Proyek_Development.docx#v1#chunk_012`
- **Input Text**:
  ```text
  Proyek RekanVault (kode proyek RV-01) bertujuan membangun source-connected knowledge system dengan konektor Google Drive dan Notion di bawah kepemimpinan Sigit.
  ```
- **Expected Memory**:
  ```json
  {
    "memory_type": "Project",
    "title": "Proyek RekanVault Source-Connected Knowledge System",
    "summary": "Pengembangan sistem pengetahuan terhubung Google Drive dan Notion berkode RV-01.",
    "project_code": "RV-01",
    "status": "active",
    "owner": "Sigit",
    "impact": "MEDIUM"
  }
  ```

---

### EXT-008 — Task
- **Memory Type**: `Task`
- **Target Locator**: `SOP_Eksekusi_Proyek_Development.docx#v1#chunk_015`
- **Input Text**:
  ```text
  Tugas pembuatan konektor Notion 2026-03-11 dengan penanganan rate limiting telah ditugaskan kepada Sisyphus dengan batas waktu 5 Agustus 2026.
  ```
- **Expected Memory**:
  ```json
  {
    "memory_type": "Task",
    "title": "Pembuatan Konektor Notion API 2026-03-11",
    "summary": "Implementasi konektor Notion dengan rate limiting oleh Sisyphus sebelum 5 Agustus 2026.",
    "assignee": "Sisyphus",
    "due_date": "2026-08-05T23:59:59Z",
    "task_status": "completed",
    "impact": "MEDIUM"
  }
  ```

---

### EXT-009 — Idea
- **Memory Type**: `Idea`
- **Target Locator**: `SOP_Presales_RekanDigital.docx#v1#chunk_018`
- **Input Text**:
  ```text
  Diusulkan ide penggunaan visual SkillTree terhubung bukti dokumen untuk membantu evaluasi kompetensi teknis tim rekayasa perangkat lunak.
  ```
- **Expected Memory**:
  ```json
  {
    "memory_type": "Idea",
    "title": "Visual SkillTree Terhubung Bukti Dokumen",
    "summary": "Gagasan peta kemampuan teknis (SkillTree) yang diverifikasi oleh bukti dokumen.",
    "proposal": "Membangun visualisasi SkillTree evidence-backed untuk pemetaan kompetensi tim.",
    "potential_impact": "Meningkatkan transparansi dan validasi keahlian tim teknis.",
    "impact": "MEDIUM"
  }
  ```

---

### EXT-010 — Risk
- **Memory Type**: `Risk`
- **Target Locator**: `SOP_Eksekusi_Proyek_Development.docx#v1#chunk_020`
- **Input Text**:
  ```text
  Risiko R-003: Kebocoran Supabase secret key dapat melewati Row Level Security (RLS) PostgreSQL. Mitigasi: Isolasi penggunaan secret key hanya pada skrip migrasi dan admin worker.
  ```
- **Expected Memory**:
  ```json
  {
    "memory_type": "Risk",
    "title": "Kebocoran Supabase Secret Key (R-003)",
    "summary": "Secret key Supabase melewati RLS PostgreSQL jika terekspos di API/browser.",
    "threat": "Kebocoran Supabase Secret Key melewati keamanan Row Level Security.",
    "mitigation": "Isolasi secret key hanya pada migration Alembic dan admin background worker.",
    "severity": "HIGH",
    "impact": "HIGH"
  }
  ```

---

### EXT-011 — Assumption
- **Memory Type**: `Assumption`
- **Target Locator**: `SOP_Presales_RekanDigital.docx#v1#chunk_022`
- **Input Text**:
  ```text
  Diasumsikan bahwa kapasitas RAM VPS sebesar 16 GB mencukupi untuk menjalankan model embedding bge-m3 dan reranker bge-reranker-v2-m3 secara simultan.
  ```
- **Expected Memory**:
  ```json
  {
    "memory_type": "Assumption",
    "title": "Kapasitas RAM VPS 16 GB untuk Model BGE",
    "summary": "Asumsi bahwa RAM VPS 16 GB cukup untuk embedding bge-m3 dan cross-encoder reranker.",
    "premise": "VPS 16 GB mampu menampung ~1.6 GB peak RSS model BGE tanpa swap thrashing.",
    "validation_status": "validated",
    "impact": "MEDIUM"
  }
  ```

---

### EXT-012 — Lesson
- **Memory Type**: `Lesson`
- **Target Locator**: `SOP_Eksekusi_Proyek_Development.docx#v1#chunk_025`
- **Input Text**:
  ```text
  Pelajaran P4-GATE: Mengabaikan penyimpanan teks dokumen di PostgreSQL menyebabkan lexical search tsvector kosong dan menggagalkan evaluasi recall. Pembelajaran: Seluruh dokumen wajib melalui upsert_document sebelum diindeks ke Qdrant.
  ```
- **Expected Memory**:
  ```json
  {
    "memory_type": "Lesson",
    "title": "Pelajaran Alur Ingesti PostgreSQL Sebelum Qdrant",
    "summary": "Dokumen wajib melalui DocumentRepository.upsert_document untuk mengisi tsvector sebelum Qdrant.",
    "takeaway": "Seluruh ingesti wajib menulis ContentBlock PostgreSQL terlebih dahulu agar lexical search berfungsi.",
    "context_description": "P4-GATE verification spent 45 minutes debugging zero recall due to Qdrant direct indexing bypass.",
    "impact": "MEDIUM"
  }
  ```

---

### EXT-013 — Metric
- **Memory Type**: `Metric`
- **Target Locator**: `SOP_Presales_RekanDigital.docx#v1#chunk_028`
- **Input Text**:
  ```text
  Target pencapaian Recall@10 untuk pipeline hybrid retrieval pada golden set pertanyaan adalah minimal 0.85 (85%). Hasil pengujian aktual mencapai 0.8938 (89.4%).
  ```
- **Expected Memory**:
  ```json
  {
    "memory_type": "Metric",
    "title": "Target dan Hasil Recall@10 Hybrid Retrieval",
    "summary": "Target Recall@10 minimal 0.85; pencapaian aktual mencapai 0.8938 (89.4%).",
    "metric_name": "Recall@10",
    "metric_value": 0.8938,
    "unit": "ratio",
    "target_value": 0.85,
    "impact": "MEDIUM"
  }
  ```

---

### EXT-014 — Person
- **Memory Type**: `Person`
- **Target Locator**: `SOP_Presales_RekanDigital.docx#v1#chunk_030`
- **Input Text**:
  ```text
  Sigit bertindak sebagai Sole Reviewer dan Lead Architect yang memegang hak persetujuan akhir atas seluruh Pull Request dan Architecture Decision Record di RekanVault.
  ```
- **Expected Memory**:
  ```json
  {
    "memory_type": "Person",
    "title": "Profil Sigit — Sole Reviewer & Lead Architect",
    "summary": "Sigit adalah sole pre-merge reviewer dan pemilik keputusan arsitektur proyek.",
    "name": "Sigit",
    "role": "Lead Architect & Sole Reviewer",
    "organization": "Rekan Digital Indonesia",
    "impact": "LOW"
  }
  ```

---

### EXT-015 — Organization
- **Memory Type**: `Organization`
- **Target Locator**: `SOP_Presales_RekanDigital.docx#v1#chunk_032`
- **Input Text**:
  ```text
  PT Rekan Digital Indonesia adalah perusahaan penyedia jasa solusi rekayasa perangkat lunak dan transformasi digital yang berbasis di Jakarta, Indonesia.
  ```
- **Expected Memory**:
  ```json
  {
    "memory_type": "Organization",
    "title": "PT Rekan Digital Indonesia",
    "summary": "Profil PT Rekan Digital Indonesia sebagai penyedia solusi rekayasa perangkat lunak.",
    "organization_name": "PT Rekan Digital Indonesia",
    "industry": "Software Engineering & Digital Transformation",
    "impact": "LOW"
  }
  ```

---

### EXT-016 — Topic
- **Memory Type**: `Topic`
- **Target Locator**: `SOP_Eksekusi_Proyek_Development.docx#v1#chunk_035`
- **Input Text**:
  ```text
  Topik Arsitektur Modular Monolith mencakup pembagian modul internal, pola domain-driven design, dan penghindaran ketergantungan microservices.
  ```
- **Expected Memory**:
  ```json
  {
    "memory_type": "Topic",
    "title": "Topik Arsitektur Modular Monolith",
    "summary": "Pembahasan mengenai arsitektur modular monolith, batas modul, dan penyederhanaan deployment.",
    "topic_name": "Modular Monolith Architecture",
    "description": "Prinsip desain monolit modular untuk sistem single-node VPS.",
    "impact": "LOW"
  }
  ```

---

### EXT-017 — Asset
- **Memory Type**: `Asset`
- **Target Locator**: `SOP_Eksekusi_Proyek_Development.docx#v1#chunk_038`
- **Input Text**:
  ```text
  Aset database PostgreSQL `rekanvault` dihosting pada platform Supabase dengan ekstensi `pg_trgm` dan `unaccent` aktif untuk pencarian teks.
  ```
- **Expected Memory**:
  ```json
  {
    "memory_type": "Asset",
    "title": "Aset Database PostgreSQL Supabase",
    "summary": "Database PostgreSQL authoritative store hosted di Supabase dengan pg_trgm dan unaccent.",
    "asset_name": "rekanvault-supabase-db",
    "asset_type": "PostgreSQL Database",
    "impact": "MEDIUM"
  }
  ```

---

### EXT-018 — Skill
- **Memory Type**: `Skill`
- **Target Locator**: `SOP_Eksekusi_Proyek_Development.docx#v1#chunk_040`
- **Input Text**:
  ```text
  Kompetensi FastAPI Pro dan Modern Async Python 3.12 dibutuhkan oleh tim pengembang untuk membangun HTTP API non-blocking berkinerja tinggi.
  ```
- **Expected Memory**:
  ```json
  {
    "memory_type": "Skill",
    "title": "Kompetensi FastAPI Pro & Async Python 3.12",
    "summary": "Keahlian membangun API async non-blocking menggunakan FastAPI dan Python 3.12.",
    "skill_name": "FastAPI & Async Python 3.12",
    "proficiency_level": "Expert",
    "impact": "LOW"
  }
  ```
