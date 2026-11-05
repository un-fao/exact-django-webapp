"""Synthetic N fertiliser forms and sewage sludge with direct and indirect N2O (IPCC 2019 Refinement).

Source: 2019 Refinement to the 2006 IPCC
Guidelines, Vol. 4, Ch. 11:
- EF1 (Table 11.1, disaggregated): synthetic N in wet climates 0.016, other N
  inputs in wet climates 0.006, all N inputs in dry climates 0.005.
- EF4 (Table 11.3, disaggregated): wet 0.014, dry 0.005. EF5: 0.011.
- FracGASF by fertiliser type (Table 11.3): urea 0.15, ammonium-based 0.08,
  nitrate-based 0.01, ammonium-nitrate-based 0.05, unspecified 0.11.
  FracGASM (organic N): 0.21.
- FracLEACH-(H) (Table 11.3): wet 0.24, dry 0.

Each row stores the combined factor in kg N2O-N per kg N, so the existing Inputs
math (N x factor x 44/28 x GWP) gives Eq. 11.1 + 11.9 + 11.10 unchanged:
    EF1 + Frac_GAS x EF4 + Frac_LEACH x EF5

Wet means a "Moist" or "Wet" moisture regime, following the Table 11.1 footnote
(temperate/boreal precipitation:PET > 1, tropical precipitation > 1000 mm).

CO2 from urea and the upstream production factor are copied from the existing
"Urea" and "Synthetic N-Fertilizers Other Than Urea" rows: no form-specific
production factor exists in EX-ACT's sources. Existing input types are not
touched, so existing projects keep their results.
"""

from django.db import migrations

EF1_SYNTHETIC = {"wet": 0.016, "dry": 0.005}
EF1_OTHER = {"wet": 0.006, "dry": 0.005}
EF4 = {"wet": 0.014, "dry": 0.005}
EF5 = 0.011
FRAC_LEACH = {"wet": 0.24, "dry": 0.0}
WET_MOISTURES = ("Moist", "Wet")

SYNTHETIC_MACRO = {
    "name_en": "Synthetic N-Fertilizers By Form (IPCC 2019)",
    "name_fr": "Engrais azotés synthétiques par forme (GIEC 2019)",
    "name_es": "Fertilizantes de N sintéticos por forma (IPCC 2019)",
    "name_ru": "Синтетические азотные удобрения по форме (МГЭИК 2019)",
}
ORGANIC_MACRO = "Organic N-Fertilizers"
UREA = "Urea"
SYNTHETIC_N = "Synthetic N-Fertilizers Other Than Urea"
SEWAGE = "Sewage"

# (names, frac_gas, ef1 table, analog type for references and CO2/production factors, macro)
NEW_TYPES = (
    (
        {
            "name_en": "Synthetic N, Unspecified Form (IPCC 2019)",
            "name_fr": "Azote synthétique, forme non précisée (GIEC 2019)",
            "name_es": "N sintético, forma no especificada (IPCC 2019)",
            "name_ru": "Синтетический азот, форма не указана (МГЭИК 2019)",
        },
        0.11,
        EF1_SYNTHETIC,
        SYNTHETIC_N,
        None,
    ),
    (
        {
            "name_en": "Urea (IPCC 2019)",
            "name_fr": "Urée (GIEC 2019)",
            "name_es": "Urea (IPCC 2019)",
            "name_ru": "Карбамид (МГЭИК 2019)",
        },
        0.15,
        EF1_SYNTHETIC,
        UREA,
        None,
    ),
    (
        {
            "name_en": "Ammonium-Based N (IPCC 2019)",
            "name_fr": "Azote ammoniacal (GIEC 2019)",
            "name_es": "N amoniacal (IPCC 2019)",
            "name_ru": "Аммонийный азот (МГЭИК 2019)",
        },
        0.08,
        EF1_SYNTHETIC,
        SYNTHETIC_N,
        None,
    ),
    (
        {
            "name_en": "Nitrate-Based N (IPCC 2019)",
            "name_fr": "Azote nitrique (GIEC 2019)",
            "name_es": "N nítrico (IPCC 2019)",
            "name_ru": "Нитратный азот (МГЭИК 2019)",
        },
        0.01,
        EF1_SYNTHETIC,
        SYNTHETIC_N,
        None,
    ),
    (
        {
            "name_en": "Ammonium Nitrate-Based N (IPCC 2019)",
            "name_fr": "Azote ammonitrique (GIEC 2019)",
            "name_es": "N amoniacal-nítrico (IPCC 2019)",
            "name_ru": "Аммиачно-нитратный азот (МГЭИК 2019)",
        },
        0.05,
        EF1_SYNTHETIC,
        SYNTHETIC_N,
        None,
    ),
    (
        {
            "name_en": "Sewage Sludge (IPCC 2019)",
            "name_fr": "Boues d'épuration (GIEC 2019)",
            "name_es": "Lodos de depuradora (IPCC 2019)",
            "name_ru": "Осадок сточных вод (МГЭИК 2019)",
        },
        0.21,
        EF1_OTHER,
        SEWAGE,
        ORGANIC_MACRO,
    ),
)

INPUT_TYPE_FLAGS = ("has_co2_emissions", "has_n2o_emissions", "has_co2_e_emissions", "unit")
REFERENCE_FIELDS = (
    "co2_multiplier",
    "co2_emissions_multiplier",
    "n2o_quantity_multiplier",
    "n2o_emissions_multiplier",
    "production_quantity_multiplier",
    "production_emissions_multiplier",
)


def n2o_n_factor(frac_gas, ef1, wetness):
    return ef1[wetness] + frac_gas * EF4[wetness] + FRAC_LEACH[wetness] * EF5


def add_n_forms(apps, schema_editor):
    InputType = apps.get_model("api", "InputType")
    MacroInputType = apps.get_model("api", "MacroInputType")
    InputReference = apps.get_model("ipcc", "InputReference")
    InputEmissionFactor = apps.get_model("ipcc", "InputEmissionFactor")

    # A fresh database (test DB, offline bootstrap) has no reference rows yet; fixtures load them later.
    if not InputType.objects.filter(name=SYNTHETIC_N).exists():
        return

    synthetic_macro, _ = MacroInputType.objects.get_or_create(name=SYNTHETIC_MACRO["name_en"], defaults=SYNTHETIC_MACRO)

    for names, frac_gas, ef1, analog_name, macro_name in NEW_TYPES:
        analog = InputType.objects.get(name=analog_name)
        macro = MacroInputType.objects.get(name=macro_name) if macro_name else synthetic_macro
        input_type, created = InputType.objects.get_or_create(
            name=names["name_en"],
            defaults={**names, "macro_input_type": macro, "description": "", **{f: getattr(analog, f) for f in INPUT_TYPE_FLAGS}},
        )
        if not created:
            continue

        analog_ref = InputReference.objects.get(input_type=analog)
        InputReference.objects.create(input_type=input_type, **{f: getattr(analog_ref, f) for f in REFERENCE_FIELDS})

        for analog_ef in InputEmissionFactor.objects.filter(input_type=analog, water_regime_type__isnull=True).select_related("moisture"):
            wetness = "wet" if analog_ef.moisture.name_en in WET_MOISTURES else "dry"
            InputEmissionFactor.objects.create(
                input_type=input_type,
                climate_id=analog_ef.climate_id,
                moisture_id=analog_ef.moisture_id,
                co2_value=analog_ef.co2_value,
                n2o_value=round(n2o_n_factor(frac_gas, ef1, wetness), 6),
                co2_eq_value=analog_ef.co2_eq_value,
            )


class Migration(migrations.Migration):

    dependencies = [
        ("ipcc", "0067_globalwarmingpotential_ch4_fossil_reference_values"),
        ("api", "0296_projectmembership_unique_user_project"),
    ]

    operations = [
        migrations.RunPython(add_n_forms, migrations.RunPython.noop),
    ]
