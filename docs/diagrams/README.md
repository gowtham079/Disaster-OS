# Project Diagrams

## View / Export Diagrams

1. Open `PROJECT_DIAGRAMS.html` in Chrome/Edge.
2. Wait for diagrams to render (2–3 seconds).
3. **For PPT/PDF:** Print → Save as PDF, or screenshot each slide section.

## Diagram List (matches synopsis presentation style)

| # | File (after generation) | Content |
|---|-------------------------|---------|
| 6 | `images/01_er_diagram.png` | Database ER Diagram |
| 7 | `images/02_system_architecture.png` | Overall System Architecture (regenerated) |
| 8 | `images/03_use_case_operator.png` | Operator Use Cases |
| 9 | `images/04_use_case_admin.png` | Admin Use Cases |
| 10 | `images/05_sequence_diagram.png` | Sequence Diagram |
| 11 | `images/07_ml_pipeline.png` | Machine Learning Pipeline |
| 12 | `images/08_message_bus_communication.png` | Message Bus Communication |
| 13 | `images/10_overall_workflow.png` | Overall Workflow |
| 14 | `images/11_activity_diagram.png` | Activity Diagram |
| 15 | `images/12_dfd_level1.png` | Data Flow Diagram Level 1 |
| 16 | `images/13_database_interaction.png` | Database Interaction Diagram |

## Mermaid source files

Individual diagram sources live in `mermaid/` (e.g. `mermaid/10_overall_workflow.mmd` … `mermaid/13_database_interaction.mmd`). Add new `.mmd` files there and embed the same block in `PROJECT_DIAGRAMS.html`, then re-run the generator.

## Auto-generate PNG (optional)

```bash
cd docs/diagrams
pip install playwright
playwright install chromium
python generate_diagram_images.py
```

## Mermaid source

Edit diagrams inside `PROJECT_DIAGRAMS.html` (Mermaid blocks).
