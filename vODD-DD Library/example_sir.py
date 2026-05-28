"""
Example: SIR Epidemiological ABM — vODD-DD diagram generation
Run:  python example_sir.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vodd_dd import (
    generate,
    VODDProtocol, Dataset, DataPipeline,
    Agents, Submodel, Interactions, Environment, ABMCore,
    OutputPattern, Calibration, Validation, ModelEvaluation,
    Scenario,
)

# ── 1. Define your protocol ───────────────────────────────────────────────────

protocol = VODDProtocol(

    purpose=(
        "Model infectious disease spread (SIR) to evaluate NPI impact "
        "and support Digital Twin decision-making."
    ),

    # ── Data Inputs
    datasets=[
        Dataset(
            name="Census Datasets",
            description="Population size, age, gender, occupation",
            how_used="Agent initialization (N, demographics)",
            frequency="STATIC",
        ),
        Dataset(
            name="GPS Mobility Data",
            description="Location traces; work/school/home context",
            how_used="Agent mobility patterns & contact rates",
            frequency="DYNAMIC",
        ),
        Dataset(
            name="Public Health Reports",
            description="Confirmed cases, β, γ estimates",
            how_used="Infection initialization; parameter calibration",
            frequency="DYNAMIC",
        ),
    ],

    # ── Data Pipeline
    pipeline=DataPipeline(
        collection=["Local gov. census API", "GPS provider feed", "Health dept. reports"],
        preprocessing=["Multiple imputation (missing counts)", "Outlier removal", "QC checks"],
        analysis=["Statistical estimation of β & γ", "Contact-rate derivation from GPS"],
    ),

    # ── ABM Core
    abm_core=ABMCore(
        model_name="SIR Epidemic ABM",
        agents=Agents(
            n_expression="N = population",
            types=["Individual"],
            state_variables=["disease_state (S/I/R)", "age", "gender",
                             "occupation", "location", "adherence_prob"],
            data_source="Census + Public Health Reports",
            submodels=[
                Submodel("Movement",     "Agent moves across home/work/school"),
                Submodel("Transmission", "S → I on contact with infected agent"),
                Submodel("Recovery",     "I → R at rate γ; permanent immunity"),
                Submodel("Compliance",   "Stochastic NPI adherence from survey dist."),
            ],
        ),
        interactions=Interactions(
            agent_agent=[
                "Disease transmission: S→I on contact (prob = β × adherence)",
            ],
            agent_environment=[
                "Mobility: agents move between home / work / school locations",
                "NPI encoding: β multipliers applied per location context",
            ],
            topology=[
                "Spatial grid with location layers",
                "Contact within co-located agents each time step",
            ],
            data_source="GPS Mobility Data; Public Health Reports",
        ),
        environment=Environment(
            grid="Spatial grid",
            resolution="Location-level",
            layers=["Home", "Work", "School"],
            data_source="GPS Mobility Data (location layers)",
        ),
        temporal_unit="1 day",
        duration="Until epidemic ends",
        stop_condition="I = 0  OR  max time steps reached",
    ),

    # ── Observations
    output_patterns=[
        OutputPattern(
            name="Epidemic Curve",
            what_measured="S(t), I(t), R(t) counts over time",
            pattern_type="Time series",
            emergent="Peak timing & magnitude from agent interactions",
        ),
        OutputPattern(
            name="NPI Impact",
            what_measured="Δ peak infections across intervention scenarios",
            pattern_type="Comparative bar / curve",
            emergent="Emergent herd-immunity threshold",
        ),
    ],

    # ── Model Evaluation
    evaluation=ModelEvaluation(
        calibration=Calibration(
            method="Bayesian inference (MCMC)",
            target_params=["β", "γ"],
            data_source="Historical infection time-series",
            result="Calibrated β*, γ* with 95% CI",
        ),
        validation=Validation(
            approaches=[
                "Output validation: RMSE/MAE vs held-out surveillance data",
                "Scenario validation: simulated vs post-NPI surveillance trends",
                "Face validity: expert review of epidemic curve shape",
            ],
            result="RMSE < 5% of peak; expert-approved",
        ),
    ),

    # ── Scenarios
    scenarios=[
        Scenario("Baseline",
                 "No NPI; calibrated β*, γ*",
                 highlighted=False),
        Scenario("Social Distancing",
                 "β × (1 − efficacy)",
                 highlighted=False),
        Scenario("Vaccination",
                 "S → R at rollout rate",
                 highlighted=False),
        Scenario("★ Combined NPI",
                 "Distancing + masking + vaccination; key DT policy scenario",
                 highlighted=True),
    ],
)

# ── 2. Generate the diagram ───────────────────────────────────────────────────
out = generate(protocol, "sir_vodd_dd.pdf")
print(f"Diagram saved → {out}")
