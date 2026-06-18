"""
Example: Residential Land-Use Change DATA-DRIVEN ABM — vODD-DD diagram generation

A classical data-driven ABM in the Parker et al. (2003) / Brown et al. (2005)
lineage: household agents bid for parcels on a raster grid, developers convert
undeveloped land when returns exceed a threshold, and the simulation is
calibrated against historical land-use maps (pattern-oriented modeling).
Used as the engine of a regional planning Digital Twin to evaluate zoning,
urban-growth boundaries, and transit-oriented development.

References:
    Parker, D.C., Manson, S.M., Janssen, M.A., Hoffmann, M.J. & Deadman, P. (2003).
        Multi-agent systems for the simulation of land-use and land-cover change:
        A review. Annals of the Association of American Geographers, 93(2),
        314-337.

    Brown, D.G., Page, S., Riolo, R., Zellner, M. & Rand, W. (2005).
        Path dependence and the validation of agent-based spatial models of land
        use. International Journal of Geographical Information Science, 19(2),
        153-174.
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
        "Simulate residential location choice and developer conversion on a "
        "parcel grid to evaluate the effect of zoning, urban-growth boundaries "
        "and transit-oriented development on urban-sprawl patterns; engine of a "
        "regional planning Digital Twin."
    ),

    # ── Data Inputs ──────────────────────────────────────────────────────────
    datasets=[
        Dataset(
            name="Parcel Cadastre",
            description="County GIS: parcel boundaries, ownership, current use",
            how_used="Initialize the spatial grid & developable mask",
            frequency="STATIC",
        ),
        Dataset(
            name="Census Demographics",
            description="Tract-level household composition, income, tenure",
            how_used="Population synthesis & preference-class assignment",
            frequency="STATIC",
        ),
        Dataset(
            name="Historical Land-Use Maps",
            description="NLCD / Landsat-derived developed-vs-undeveloped, decadal",
            how_used="Calibration target & validation reference",
            frequency="DYNAMIC",
        ),
        Dataset(
            name="Real-Estate Transactions",
            description="Recent sale prices, hedonic attributes, move histories",
            how_used="Hedonic regression for amenity weights; preference clustering",
            frequency="DYNAMIC",
        ),
        Dataset(
            name="Zoning & Policy Layers",
            description="Zoning, growth boundaries, transit corridors, road network",
            how_used="Constrain feasible parcels & accessibility scoring",
            frequency="DYNAMIC",
        ),
    ],

    pipeline=DataPipeline(
        collection=[
            "County GIS download",
            "USGS NLCD / Landsat archive",
            "Census microdata",
            "MLS / assessor transaction feed",
        ],
        preprocessing=[
            "Parcel-to-raster rasterization (100 m)",
            "Land-cover reclassification (developed / undeveloped)",
            "Spatial join of demographics to parcels",
        ],
        analysis=[
            "Hedonic regression for amenity weights",
            "k-means clustering of move patterns -> preference classes",
            "Accessibility surface (network distance to CBD & transit)",
        ],
    ),

    # ── ABM Core ─────────────────────────────────────────────────────────────
    abm_core=ABMCore(
        model_name="ResLUCC (Residential Land-Use Change ABM)",
        agents=Agents(
            n_expression="N = households + developers",
            types=["Household", "Developer"],
            state_variables=[
                "income",
                "preference_class",   # urbanite / exurban / aesthetic
                "tenure_status",
                "current_parcel",
                "dissatisfaction",
            ],
            data_source="Census Demographics + Real-Estate Transactions",
            submodels=[
                Submodel("Move Decision",
                         "Triggered by life-cycle events or dissatisfaction threshold"),
                Submodel("Location Choice",
                         "Utility-based bid over feasible parcels (multinomial logit)"),
                Submodel("Developer Conversion",
                         "Convert undeveloped -> developed if expected return > threshold"),
                Submodel("Amenity Update",
                         "Neighbor density & land cover update local aesthetic score"),
            ],
        ),
        interactions=Interactions(
            agent_agent=[
                "Households bid competitively for the same parcel; "
                "highest bid wins (auction mechanism)",
                "Neighbor effects: nearby development alters local aesthetic & price",
            ],
            agent_environment=[
                "Zoning rules constrain the feasible-parcel set",
                "Accessibility (distance to CBD / transit) enters utility",
            ],
            topology=[
                "Regular 2D raster of parcels",
                "Moore neighborhood for local effects",
            ],
            data_source="Zoning & Policy Layers; Real-Estate Transactions",
        ),
        environment=Environment(
            grid="Regular raster of parcels",
            resolution="100 m x 100 m cells",
            layers=["Zoning", "Accessibility", "Amenity", "Existing development"],
            data_source="Parcel Cadastre; Historical Land-Use Maps",
        ),
        temporal_unit="1 year",
        duration="40 years (1990-2030)",
        stop_condition="Simulation horizon reached OR developable land exhausted",
    ),

    # ── Observations ─────────────────────────────────────────────────────────
    output_patterns=[
        OutputPattern(
            name="Settlement Pattern Map",
            what_measured="Predicted developed / undeveloped raster vs observed",
            pattern_type="Spatial map",
            emergent="Leapfrog development & fragmented edges",
        ),
        OutputPattern(
            name="Density Gradient",
            what_measured="Built-up density vs distance to CBD over time",
            pattern_type="Curve",
            emergent="Monocentric -> polycentric structure under TOD scenarios",
        ),
    ],

    # ── Model Evaluation ─────────────────────────────────────────────────────
    evaluation=ModelEvaluation(
        calibration=Calibration(
            method="Pattern-oriented modeling (POM) with genetic algorithm",
            target_params=[
                "preference weights",
                "developer threshold",
                "neighbor-effect radius",
            ],
            data_source="Historical Land-Use Maps (1990 -> 2010 trajectory)",
            result="Best-fit parameter set; Kappa > 0.70 on calibration period",
        ),
        validation=Validation(
            approaches=[
                "Multi-resolution Kappa on held-out 2010-2020 maps",
                "Density-gradient & fractal-dimension comparison",
                "Null-model contrast (random allocation, persistence)",
            ],
            result="Pattern metrics within 10% of observed; null clearly rejected",
        ),
    ),

    # ── Scenarios ────────────────────────────────────────────────────────────
    scenarios=[
        Scenario("Baseline",
                 "Status-quo zoning; calibrated preferences"),
        Scenario("Growth Boundary",
                 "Strict urban-growth boundary around existing built-up area"),
        Scenario("TOD Upzoning",
                 "Higher allowed density within 800 m of transit corridors"),
        Scenario("★ Combined",
                 "Growth boundary + TOD upzoning; key DT policy scenario",
                 highlighted=True),
    ],
)

# ── 2. Generate the diagram ───────────────────────────────────────────────────
result = generate(protocol, "lucc_vodd_dd.pdf")
print(f"Diagram saved → {out}")