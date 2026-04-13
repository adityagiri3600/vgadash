# VGADASH Paper Workspace

This workspace keeps the semester paper organized around the provided Word
template while still giving us text-first sources that are easy to revise.

Files:
- `template/Revised 983.docx`: professor-provided template, kept as the base.
- `content.md`: main paper draft with section text and figure/table markers.
- `references.md`: numeric references used by the draft.
- `assets/`: diagram and VGA screenshots used in the draft.
- `scripts/generate_assets.py`: creates the paper figures as PNG files.
- `scripts/generate_docx.py`: renders `content.md` into a draft `.docx` using the template styles.
- `output/vgadash_semester_paper_draft.docx`: generated draft document.

Regeneration:
```bash
python3 paper/scripts/generate_docx.py
```

Notes:
- The draft uses placeholders for authors, institute, and emails.
- Layout fidelity is based on the Word template styles preserved in the input `.docx`.
- The generator overwrites the stable draft filenames in `output/` instead of creating versioned copies.
