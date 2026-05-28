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

```python
from vodd_dd import (
    generate, VODDProtocol, Dataset, DataPipeline,
    Agents, Submodel, Interactions, Environment, ABMCore,
    OutputPattern, Calibration, Validation, ModelEvaluation, Scenario,
)

protocol = VODDProtocol(
    purpose="Model infectious disease spread (SIR) to evaluate NPI impact.",

    # ── DATA INPUTS ──────────────────────────────────────────────
    datasets=[
        Dataset("Census Datasets", "Population size, age, gender",
                "Agent initialization", frequency="STATIC"),
        Dataset("GPS Mobility Data", "Location traces; home/work/school",
                "Agent mobility & contact rates", frequency="DYNAMIC"),
    ],
    pipeline=DataPipeline(
        collection=["Census API", "GPS provider feed"],
        preprocessing=["Multiple imputation", "QC checks"],
        analysis=["Estimate β & γ", "Contact-rate derivation"],
    ),

    # ── ABM CORE ─────────────────────────────────────────────────
    abm_core=ABMCore(
        model_name="SIR Epidemic ABM",
        agents=Agents(
            n_expression="N = population",
            types=["Individual"],
            state_variables=["disease_state (S/I/R)", "age", "location"],
            data_source="Census + Public Health Reports",
            submodels=[
                Submodel("Movement", "Agent moves across home/work/school"),
                Submodel("Transmission", "S → I on contact with infected agent"),
                Submodel("Recovery", "I → R at rate γ; permanent immunity"),
            ],
        ),
        interactions=Interactions(
            agent_agent=["Disease transmission: S→I on contact"],
            agent_environment=["Mobility between home / work / school"],
            topology=["Spatial grid with location layers"],
            data_source="GPS Mobility Data; Public Health Reports",
        ),
        environment=Environment(
            grid="Spatial grid", resolution="Location-level",
            layers=["Home", "Work", "School"],
            data_source="GPS Mobility Data",
        ),
        temporal_unit="1 day",
        duration="Until epidemic ends",
        stop_condition="I = 0 OR max time steps reached",
    ),

    # ── OBSERVATIONS ─────────────────────────────────────────────
    output_patterns=[
        OutputPattern("Epidemic Curve", "S(t), I(t), R(t) over time",
                      pattern_type="Time series",
                      emergent="Peak timing & magnitude from interactions"),
        OutputPattern("NPI Impact", "Δ peak infections across scenarios",
                      pattern_type="Comparative bar / curve",
                      emergent="Emergent herd-immunity threshold"),
    ],

    # ── MODEL EVALUATION ─────────────────────────────────────────
    evaluation=ModelEvaluation(
        calibration=Calibration(
            method="Bayesian inference (MCMC)",
            target_params=["β", "γ"],
            data_source="Historical infection time-series",
            result="Calibrated β*, γ* with 95% CI",
        ),
        validation=Validation(
            approaches=["RMSE/MAE vs held-out data", "Face validity: expert review"],
            result="RMSE < 5% of peak; expert-approved",
        ),
    ),

    # ── SCENARIOS ────────────────────────────────────────────────
    scenarios=[
        Scenario("Baseline", "No NPI; calibrated β*, γ*"),
        Scenario("Social Distancing", "β × (1 − efficacy)"),
        Scenario("Combined NPI", "Distancing + masking + vaccination",
                 highlighted=True),   # draws a bold border
    ],
)

generate(protocol, "my_model.pdf")
```

`generate()` writes `my_model.pdf`, `my_model.svg`, and `my_model.png` (PNG if
available) and returns a dict of the paths:

```python
{"pdf": "my_model.pdf", "svg": "my_model.svg", "png": "my_model.png"}
```

A complete, runnable example is in `example_sir.py`:

```bash
python example_sir.py
```

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
- **`OutputPattern`** — `name`, `what_measured`, `pattern_type`, `emergent`.
- **`Calibration`** — `method`, `target_params`, `data_source`, `result`.
- **`Validation`** — `approaches`, `result`.
- **`ModelEvaluation`** — `calibration`, `validation`.
- **`Scenario`** — `name`, `description`, `highlighted`.

List fields are optional and default to empty, so you can fill in as much or as
little as your model needs. Boxes grow automatically to fit the text, and long
labels shrink to stay inside their banners — no manual layout required.

## Notes

- Output is sized to A4. Content that exceeds one page extends the canvas.
- The PDF/PNG use Helvetica metrics and are pixel-accurate; the SVG declares a
  `Helvetica, Arial, sans-serif` stack so it matches across viewers.
- See `CHANGES.md` for the layout/contrast fixes applied to the renderer.
