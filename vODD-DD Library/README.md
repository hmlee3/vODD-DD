# vODD-DD Protocol Generator

Generate a one-page **vODD-DD** visual protocol diagram (Visual Overview, Design
concepts & Details, for **D**ata-**D**riven agent-based models) from a Python
description of your model. One call produces **PDF + SVG + PNG**.

## Install

The library needs `reportlab` (PDF/SVG) and, for PNG output, `pymupdf`:

```bash
pip install reportlab pymupdf
```

PNG is optional — if `pymupdf` isn't available the generator still writes the PDF
and SVG and just skips the PNG (it also falls back to the `pdftoppm` system tool
if present).

## Quick start

Two complete, runnable examples live in `exampleABM/`:

- `example_sir.py` — the canonical SIR epidemic case study.
- `example_landuseABM.py` — a residential land-use change ABM after
  Parker et al. (2003) / Brown et al. (2005).

Run them from the project root:

```bash
python exampleABM/example_sir.py
python exampleABM/example_landuseABM.py
```

> **Path note.** Because the examples now live in a sub-folder, the top of each
> script must add the project root to `sys.path` so `from vodd_dd import ...`
> resolves:
>
> ```python
> import sys, os
> # Step up one level from exampleABM/ to reach the project root where vodd_dd/ lives.
> sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
> ```

## The diagram layout

The generated page mirrors the official vODD-DD template, left to right:

| Section            | Built from                                              |
|--------------------|---------------------------------------------------------|
| **Purpose**        | `VODDProtocol.purpose`                                  |
| **Data Inputs**    | `datasets` (each a card with a STATIC/DYNAMIC badge) + `pipeline` |
| **ABM Core**       | `abm_core` → agents, submodels, interactions, environment, temporal/stop strip |
| **Observations**   | `output_patterns`                                       |
| **Model Evaluation** | `evaluation` → calibration + validation               |
| **Scenarios**      | `scenarios` (set `highlighted=True` to emphasize one)   |

## API at a glance

`generate(protocol, output_path="vodd_protocol.pdf", dpi=150) -> dict`
renders all three formats. Use a higher `dpi` for a sharper PNG.

For more control, use the renderer directly:

```python
from vodd_dd.renderer import VODDRenderer
r = VODDRenderer(protocol)
r.render_pdf("out.pdf")
r.render_svg("out.svg")
r.render_png("out.png", dpi=300)   # needs pymupdf
```

### Data models (all `dataclass`es from `vodd_dd`)

- **`VODDProtocol`** — top-level container holding every section below.
- **`Dataset`** — `name`, `description`, `how_used`, `frequency` (`"STATIC"` |
  `"DYNAMIC"`).
- **`DataPipeline`** — `collection`, `preprocessing`, `analysis` (lists of strings).
- **`ABMCore`** — `model_name`, `agents`, `interactions`, `environment`,
  `temporal_unit`, `duration`, `stop_condition`.
- **`Agents`** — `n_expression`, `types`, `state_variables`, `data_source`,
  `submodels`.
- **`Submodel`** — `name`, `description`.
- **`Interactions`** — `agent_agent`, `agent_environment`, `topology`,
  `data_source`.
- **`Environment`** — `grid`, `resolution`, `layers`, `data_source`.
- **`OutputPattern`** — `name`, `what_measured`, `pattern_type`, `emergent`, `has_chart` (optional flag, default `False`).
- **`Calibration`** — `method`, `target_params`, `data_source`, `result`.
- **`Validation`** — `approaches`, `result`.
- **`ModelEvaluation`** — `calibration`, `validation`.
- **`Scenario`** — `name`, `description`, `highlighted`.

List fields are optional and default to empty, so you can fill in as much or as
little as your model needs. Boxes grow automatically to fit the text, and long
labels shrink to stay inside their banners — no manual layout required.
