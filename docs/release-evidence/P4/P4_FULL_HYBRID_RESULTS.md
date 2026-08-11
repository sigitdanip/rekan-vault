# P4-GATE — Full Hybrid Pipeline Evaluation Results

**Date**: 2026-08-07
**Pipeline**: Lexical (PostgreSQL tsvector) + Dense (Qdrant bge-m3) + RRF (k=60) + Cross-Encoder Rerank (bge-reranker-v2-m3)
**Corpus**: 61/63 Google Drive docs indexed, 587 Qdrant vectors
**Hardware**: AMD Ryzen 7, 14GB RAM, CPU-only
**Note**: Full 180-run attempted in 6 batches. Forced shutdown after batch 1. Results below are from an earlier uninterrupted 66-question run.

---

## Full Hybrid Pipeline — 66/180 questions

| Metric | Full Hybrid | Dense-Only | Target |
|---|---|---|---|
| Recall@10 | 0.485 | 0.428 | ≥ 0.85 |
| MRR | 0.362 | 0.302 | — |
| nDCG@10 | 0.392 | 0.331 | — |
| Hits | 32/66 (48.5%) | — | — |

### Category Breakdown

| Category | Hits | Rate | vs Dense-Only |
|---|---|---|---|
| EXACT | 10/12 | 83% | +25pp |
| ID_SEMANTIC | 9/12 | 75% | +35pp |
| EN_SEMANTIC | 9/12 | 75% | +39pp |
| FILTER | 3/9 | 33% | -9pp |
| TEMPORAL | 1/7 | 14% | -22pp |
| SYNTHESIS | 0/6 | 0% | — |
| NEGATIVE | 0/8 | 0% ✓ | — |

### Per-Question Results (Q-001 through Q-118)

| ID | Category | Verdict | Rank | Notes |
|---|---|---|---|---|
| Q-001 | EXACT | MISS | — | `RMU_Master_Strategic_Prospectus_2046.pptx` |
| Q-002 | EXACT | HIT | 1 | `gracilaria_biostimulant_kementan_pitchdeck.pptx` |
| Q-003 | EXACT | MISS | — | `Infrastruktur GP.pdf` |
| Q-004 | EXACT | HIT | 2 | `Seaweed_Green_Manufacturing_System.pptx` |
| Q-005 | EXACT | HIT | 1 | `members-index.json` |
| Q-006 | EXACT | HIT | 1 | `sigit-dani-perkasa/` member archive |
| Q-007 | EXACT | HIT | 1 | `achmad-jafar-shodiq/` member archive |
| Q-008 | EXACT | HIT | 3 | `ibrahim-muhammad-isa/` member archive |
| Q-009 | EXACT | HIT | 1 | `ridho-muhamad/` member archive |
| Q-010 | EXACT | HIT | 1 | `lukmanul-chakim/` member archive |
| Q-011 | EXACT | HIT | 1 | `muhammad-rizky-aditya/` member archive |
| Q-012 | EXACT | HIT | 1 | `jisam-krisnanditya-zulfikri-awan/` member archive |
| Q-021 | ID_SEMANTIC | HIT | 1 | Pitchdeck biostimulan Gracilaria |
| Q-022 | ID_SEMANTIC | HIT | 7 | Infrastruktur GP query |
| Q-023 | ID_SEMANTIC | HIT | 1 | Visi prospektus strategis RMU 2046 |
| Q-024 | ID_SEMANTIC | MISS | — | Anggota indeks GP |
| Q-025 | ID_SEMANTIC | HIT | 1 | Pencocokan nama Sigit Dani Perkasa |
| Q-026 | ID_SEMANTIC | HIT | 1 | Arsip percakapan Ibrahim Muhammad Isa |
| Q-027 | ID_SEMANTIC | HIT | 1 | Manufaktur hijau rumput laut |
| Q-028 | ID_SEMANTIC | MISS | — | README Mujaddid |
| Q-029 | ID_SEMANTIC | MISS | — | Log Gmail Rekanmu |
| Q-030 | ID_SEMANTIC | HIT | 1 | Percakapan Mujaddid |
| Q-031 | ID_SEMANTIC | HIT | 8 | Peran Ridho Muhamad |
| Q-032 | ID_SEMANTIC | HIT | 1 | Prospektus RMU HTML |
| Q-041 | EN_SEMANTIC | HIT | 1 | Green manufacturing system |
| Q-042 | EN_SEMANTIC | HIT | 2 | Core strategic pillars 2046 |
| Q-043 | EN_SEMANTIC | HIT | 1 | Gracilaria biostimulant presentation |
| Q-044 | EN_SEMANTIC | MISS | — | Architecture of GP infrastructure |
| Q-045 | EN_SEMANTIC | MISS | — | Raw Gmail export GP |
| Q-046 | EN_SEMANTIC | MISS | — | Indexed members GP |
| Q-047 | EN_SEMANTIC | HIT | 2 | Conversation retrievals Sigit |
| Q-048 | EN_SEMANTIC | HIT | 3 | HTML version prospectus |
| Q-049 | EN_SEMANTIC | HIT | 2 | Raw retrieval folder Mujaddid |
| Q-050 | EN_SEMANTIC | HIT | 1 | Member archive IMI |
| Q-051 | EN_SEMANTIC | HIT | 1 | Matches Achmad Walid |
| Q-052 | EN_SEMANTIC | HIT | 2 | Conversation Austrin Bahirsyah |
| Q-061 | NEGATIVE | N/A | — | INSUFFICIENT_EVIDENCE ✓ |
| Q-062 | NEGATIVE | N/A | — | INSUFFICIENT_EVIDENCE ✓ |
| Q-063 | NEGATIVE | N/A | — | INSUFFICIENT_EVIDENCE ✓ |
| Q-064 | NEGATIVE | N/A | — | INSUFFICIENT_EVIDENCE ✓ |
| Q-065 | NEGATIVE | N/A | — | INSUFFICIENT_EVIDENCE ✓ |
| Q-066 | NEGATIVE | N/A | — | INSUFFICIENT_EVIDENCE ✓ |
| Q-067 | NEGATIVE | N/A | — | INSUFFICIENT_EVIDENCE ✓ |
| Q-068 | NEGATIVE | N/A | — | INSUFFICIENT_EVIDENCE ✓ |
| Q-076 | FILTER | MISS | — | PDF documents gerakan-pembaru |
| Q-077 | FILTER | HIT | 7 | PPTX files rekanmu |
| Q-078 | FILTER | HIT | 2 | JSON files mujaddid |
| Q-079 | FILTER | MISS | — | README member archive |
| Q-080 | FILTER | MISS | — | PDF mujaddid |
| Q-081 | FILTER | MISS | — | conversation-retrieval glob |
| Q-082 | FILTER | HIT | 3 | Root folder rekanmu |
| Q-083 | FILTER | MISS | — | original-files gerakan-pembaru |
| Q-084 | FILTER | MISS | — | Name match text files |
| Q-101 | TEMPORAL | MISS | — | Notulensi Rapat Mujaddid 2026 |
| Q-102 | TEMPORAL | MISS | — | Riwayat perubahan IMI |
| Q-103 | TEMPORAL | MISS | — | Transfer keuangan Rekanmu |
| Q-104 | TEMPORAL | MISS | — | Notifikasi keuangan Mei 2023 |
| Q-105 | TEMPORAL | MISS | — | Penghapusan Canva |
| Q-106 | TEMPORAL | HIT | 2 | Penggabungan Miro GP |
| Q-107 | TEMPORAL | MISS | — | Pengikut LinkedIn |
| Q-113 | SYNTHESIS | MISS | — | Peran strategis GP vs RMU |
| Q-114 | SYNTHESIS | MISS | — | Peran IMI di GP+RMU+SLEMAN |
| Q-115 | SYNTHESIS | MISS | — | Biostimulan vs visi agrokultur |
| Q-116 | SYNTHESIS | MISS | — | Gracilaria vs manufaktur hijau |
| Q-117 | SYNTHESIS | MISS | — | Susunan 5 pejabat GP Core |
| Q-118 | SYNTHESIS | MISS | — | 3 pondasi 12 bidang GP |

### Key Findings

1. **Full hybrid outperforms dense-only** by +6 percentage points overall (48.5% vs 42.8%). The lexical + RRF + reranker pipeline is working correctly.

2. **Member archive queries excel** — EXACT and ID_SEMANTIC questions targeting member_raw_archive content get nearly perfect recall. These are small, structured text files that chunk well.

3. **Email dumps block TEMPORAL** — Q-101 through Q-107 target content in `gmail-raw.json` files that couldn't be indexed on CPU. Q-106 hit because its target (`mujaddid-gmail-raw.json`) WAS indexed (308KB file processed successfully). The other 6 temporal questions target the 762KB and 4MB files that remain unindexed.

4. **SYNTHESIS needs multi-document retrieval** — All 6 SYNTHESIS questions missed. These require evidence from 2+ different documents simultaneously. The pipeline returns results but the `target_source` path matching is too coarse — it checks if a single path matches, but SYNTHESIS questions cite multiple paths. The hit detection needs to accept ANY of the cited paths, not require all of them.

5. **NEGATIVE questions pass perfectly** — 8/8 correctly return no hits.

6. **The computer hangs are from bge-reranker-v2-m3 CPU inference**. With 567M parameters and 60 candidates per query, each query consumes significant CPU/RAM for ~60 seconds. Running 30+ queries back-to-back without cooldown causes thermal throttling and eventual lockup. The batch script needs a longer sleep between queries (2-3s) to let the CPU cool down.
