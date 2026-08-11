
golden_set_path = "docs/REKANVAULT_GOLDEN_SET.md"

with open(golden_set_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
inserted_discipline = False

for line in lines:
    new_lines.append(line)
    if "| 2026-08-06 | Q-101–Q-164 | Batch 2 Creation |" in line and not inserted_discipline:
        new_lines.append("| 2026-08-06 | Q-165–Q-180 | Realignment Batch 3 | Realigned golden set for 2 new DOCX SOP documents in `rekanmu/original-files/` (`SOP_Presales_RekanDigital.docx` & `SOP_Eksekusi_Proyek_Development.docx`) per RV-DEC-0015 | Sigit / Antigravity |\n")
        inserted_discipline = True

content_text = "".join(new_lines)

# Split before Findings on Baseline Q-001–Q-100 section
if "## Findings on Baseline Q-001–Q-100" in content_text:
    parts = content_text.split("## Findings on Baseline Q-001–Q-100")
    top_part = parts[0]
    bottom_part = "## Findings on Baseline Q-001–Q-100" + parts[1]
else:
    top_part = content_text
    bottom_part = ""

batch_3_text = """
---

## Golden Question Batch 3 Realignment — 2 New Rekanmu SOP Documents (Q-165 to Q-180)

| ID | Category | Question | Target Source / Path | Expected Answer / Evidence Key |
|---|---|---|---|---|
| `Q-165` | EXACT | "SOP-RD-PRESALES-001" | `rekanmu/original-files/SOP_Presales_RekanDigital.docx` | Standard Operating Procedure Presales RekanDigital document code covering lead qualification to execution handover. |
| `Q-166` | EXACT | "SOP-RMU-PROD-01" | `rekanmu/original-files/SOP_Eksekusi_Proyek_Development.docx` | Standard Operating Procedure Execution Project & Development "The Production Engine" document code. |
| `Q-167` | ID_SEMANTIC | "Bagaimana pembagian peran 4 anggota tim inti RekanDigital dalam alur presales?" | `rekanmu/original-files/SOP_Presales_RekanDigital.docx` | Tim inti terdiri dari Fahri (Direktur Utama / Sales Lead), Imi Hamengku (Komisaris Utama / Governance), Zuri (Direktur Teknologi / Technical Scoping Software), dan Sigit (Technical Scoping Hardware/IoT). |
| `Q-168` | ID_SEMANTIC | "Apa saja 4 fase utama eksekusi proyek development menurut dokumen SOP The Production Engine?" | `rekanmu/original-files/SOP_Eksekusi_Proyek_Development.docx` | Fase 1: Kick-off Meeting & Setup Project (1-2 hari); Fase 2: UI/UX & Arsitektur Hardware (Minggu 1-2); Fase 3: Sprint Development & Daily Check (siklus 2 minggu); Fase 4: Quality Assurance & Staging Deployment (3-5 hari). |
| `Q-169` | ID_SEMANTIC | "Kapan Proof of Concept (PoC) berbayar wajib ditawarkan dalam alur presales RekanDigital?" | `rekanmu/original-files/SOP_Presales_RekanDigital.docx` | PoC berbayar wajib ditawarkan pada Fase 2 jika proyek berkategori High complexity atau berisiko tinggi gagal integrasi hardware/software. |
| `Q-170` | EN_SEMANTIC | "What are the RACI responsibilities assigned to Zuri and Sigit during technical scoping in RekanDigital?" | `rekanmu/original-files/SOP_Presales_RekanDigital.docx` | Zuri and Sigit are Responsible and Accountable for Phase 2 Technical Scoping, complexity assessment (Low/Medium/High), and man-days/BOM calculation. |
| `Q-171` | EN_SEMANTIC | "How are integration points between software and hardware modules managed during project execution?" | `rekanmu/original-files/SOP_Eksekusi_Proyek_Development.docx` | Integration points between Zuri (backend/dashboard) and Sigit (device/hardware) are explicitly recorded on Jira/ClickUp project boards in Phase 1 and data contracts (MQTT topics, API structure, payloads) are aligned in Phase 2. |
| `Q-172` | EN_SEMANTIC | "What is the mandatory client requirement before software development coding begins at RMU?" | `rekanmu/original-files/SOP_Eksekusi_Proyek_Development.docx` | Wireframe/mockup created in Figma by Zuri MUST receive explicit client sign-off (screenshot/email/meeting notes) before any coding begins. |
| `Q-173` | TEMPORAL | "Kapan tanggal berlaku efektif dokumen SOP Eksekusi Proyek & Development (SOP-RMU-PROD-01)?" | `rekanmu/original-files/SOP_Eksekusi_Proyek_Development.docx` | Berlaku efektif mulai 3 Agustus 2026, disetujui oleh Fahri selaku Direktur Utama. |
| `Q-174` | TEMPORAL | "Kapan tanggal penerbitan versi 1.0 dokumen SOP Presales RekanDigital?" | `rekanmu/original-files/SOP_Presales_RekanDigital.docx` | Versi 1.0 diterbitkan pada Agustus 2026 dengan pengesahan dari Imi Hamengku (Komisaris Utama), Fahri (Direktur Utama), Zuri, dan Sigit. |
| `Q-175` | MULTIHOP | "Siapa Direktur Utama PT Rekan Makmur Utama yang menyetujui SOP Eksekusi Proyek dan bertanggung jawab atas closing sales presales?" | `rekanmu/original-files/SOP_Eksekusi_Proyek_Development.docx` & `rekanmu/original-files/SOP_Presales_RekanDigital.docx` | Fahri (Direktur Utama). |
| `Q-176` | MULTIHOP | "Siapa Komisaris Utama PT Rekan Makmur Utama yang menerima laporan governance presales dan mengesahkan SOP-RD-PRESALES-001?" | `rekanmu/original-files/SOP_Presales_RekanDigital.docx` & `member_raw_archive/ibrahim-muhammad-isa/README.txt` | Imi Hamengku (Ibrahim Muhammad Isa). |
| `Q-177` | SYNTHESIS | "Bagaimana serah terima proyek (handover) dari tim Sales ke tim Tech Lead menghubungkan SOP Presales dengan SOP Eksekusi Proyek?" | `rekanmu/original-files/SOP_Presales_RekanDigital.docx` & `rekanmu/original-files/SOP_Eksekusi_Proyek_Development.docx` | Pada Fase 4 Presales, Sales menerbitkan invoice DP dan menyerahkan berkas BRD/SOW; pada Fase 1 Eksekusi, Tech Lead menerima BRD/SOW via sesi Q&A, mengarsipkan berkas di Google Drive, dan membuat papan proyek Jira/ClickUp dengan dual swimlane. |
| `Q-178` | SYNTHESIS | "Apa saja pilar layanan teknis RekanDigital dan siapa penanggung jawab masing-masing jalur teknis pada tahap eksekusi?" | `rekanmu/original-files/SOP_Presales_RekanDigital.docx` & `rekanmu/original-files/SOP_Eksekusi_Proyek_Development.docx` | 3 pilar layanan: Software, IoT/Hardware, dan Spatial/Data. Jalur Software/Data dipimpin oleh Zuri (Direktur Teknologi) dan jalur Hardware/IoT dipimpin oleh Sigit. |
| `Q-179` | FILTER | "Find all Microsoft Word (.docx) documents in the rekanmu original-files directory." | `rekanmu/original-files/*.docx` | `SOP_Presales_RekanDigital.docx` and `SOP_Eksekusi_Proyek_Development.docx`. |
| `Q-180` | FILTER | "Retrieve documents containing document code prefix 'SOP-' in rekanmu original files." | `rekanmu/original-files/SOP_*.docx` | `SOP_Presales_RekanDigital.docx` (SOP-RD-PRESALES-001) and `SOP_Eksekusi_Proyek_Development.docx` (SOP-RMU-PROD-01). |
"""

final_content = top_part + batch_3_text + "\n" + bottom_part

with open(golden_set_path, "w", encoding="utf-8") as f:
    f.write(final_content)

print("Successfully written Batch 3 realigned questions to REKANVAULT_GOLDEN_SET.md")
