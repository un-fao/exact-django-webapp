"""Canonical manifest of reference/lookup models for the unified fixture pipeline.

The ordered list `MANIFEST` is the single source of truth for both
`dump_reference_data` and `load_reference_data`. List position encodes
dependency order: every entry must appear after all entries it FKs into.

Only reference/lookup tables belong here. Project/Activity/Module/Note/Tag/User
and other user-generated data are explicitly excluded.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ReferenceModelSpec:
    model: str
    order_by: tuple
    fixture_file: str
    category: str
    app: str


# --- api app reference models -----------------------------------------------
_API_ENTRIES = [
    # Core no-FK lookups
    ("api.Moisture", ("name",), "moisture.json", "core"),
    ("api.Climate", ("name",), "climate.json", "core"),
    ("api.Region", ("name",), "region.json", "core"),
    ("api.SoilType", ("name",), "soiltype.json", "core"),
    ("api.ExtractionSoilType", ("name",), "extractionsoiltype.json", "core"),
    ("api.ModuleType", ("name",), "moduletype.json", "core"),
    ("api.ForestType", ("name",), "foresttype.json", "core"),
    ("api.LandUseType", ("name",), "landusetype.json", "core"),
    ("api.GLEAMRegion", ("name",), "gleamregion.json", "core"),
    ("api.ForestConditionType", ("name",), "forestconditiontype.json", "core"),
    ("api.SiteLocationType", ("name",), "sitelocationtype.json", "core"),
    ("api.VegetationType", ("name",), "vegetationtype.json", "core"),
    ("api.ActivityType", ("name",), "activitytype.json", "core"),
    ("api.StatusType", ("name",), "statustype.json", "core"),
    ("api.SettlementType", ("name",), "settlementtype.json", "core"),
    ("api.ChangeRate", ("name",), "changerate.json", "core"),
    ("api.ProjectStatus", ("name",), "projectstatus.json", "core"),
    ("api.DataSource", ("name",), "datasource.json", "core"),
    ("api.ForestDegradationLevel", ("name",), "forestdegradationlevel.json", "core"),
    ("api.FireType", ("name",), "firetype.json", "core"),
    ("api.PeatType", ("name",), "peattype.json", "core"),
    ("api.WaterbodyType", ("name",), "waterbodytype.json", "core"),
    ("api.TrophicType", ("name",), "trophictype.json", "core"),
    ("api.FisheryType", ("name",), "fisherytype.json", "core"),
    ("api.FishType", ("name",), "fishtype.json", "core"),
    ("api.GasType", ("name",), "gastype.json", "core"),
    ("api.InvitationStatusType", ("name",), "invitationstatustype.json", "core"),
    ("api.DisturbanceType", ("name",), "disturbancetype.json", "core"),
    ("api.CropType", ("name",), "croptype.json", "core"),
    # Fuel-related in dependency order
    ("api.MacroFuelType", ("name",), "macrofueltype.json", "fuel"),
    ("api.FuelUseType", ("name",), "fuelusetype.json", "fuel"),
    ("api.Unit", ("name",), "unit.json", "fuel"),
    ("api.ParentFuelType", ("name",), "parentfueltype.json", "fuel"),
    ("api.FuelType", ("name",), "fueltype.json", "fuel"),
    ("api.SalinityType", ("value",), "salinitytype.json", "fuel"),
    ("api.EnergySourceType", ("name",), "energysourcetype.json", "fuel"),
    # Input-related in dependency order
    ("api.MacroInputType", ("name",), "macroinputtype.json", "input"),
    ("api.InputType", ("name",), "inputtype.json", "input"),
    ("api.EmissionFactorSource", ("name",), "emissionfactorsource.json", "input"),
    # Infrastructure / value-chain
    ("api.IrrigationSystemType", ("name",), "irrigationsystemtype.json", "infra"),
    ("api.BuildingType", ("name",), "buildingtype.json", "infra"),
    ("api.RoadType", ("name",), "roadtype.json", "infra"),
    ("api.RefrigerantType", ("name",), "refrigeranttype.json", "infra"),
    ("api.PackagingMaterialType", ("name",), "packagingmaterialtype.json", "infra"),
    # Region/country (depend on IPCCRegion + GLEAMRegion)
    ("api.IPCCRegion", ("name",), "ipccregion.json", "region"),
    ("api.Country", ("name",), "country.json", "region"),
    # Management types
    ("api.TillageType", ("name",), "tillagetype.json", "management"),
    ("api.TillageManagementType", ("name",), "tillagemanagementtype.json", "management"),
    ("api.OrganicInputType", ("name",), "organicinputtype.json", "management"),
    ("api.ResidueManagementType", ("name",), "residuemanagementtype.json", "management"),
    ("api.WaterRegimeType", ("name",), "waterregimetype.json", "management"),
    ("api.PreSeasonWaterRegimeType", ("name",), "preseasonwaterregimetype.json", "management"),
    ("api.OrganicAmendmentType", ("name",), "organicamendmenttype.json", "management"),
    ("api.WaterManagementTypeBeforeCultivation", ("name",), "watermanagementtypebeforecultivation.json", "management"),
    ("api.WaterManagementTypeAfterCultivation", ("name",), "watermanagementtypeaftercultivation.json", "management"),
    ("api.GrasslandManagementType", ("name",), "grasslandmanagementtype.json", "management"),
    ("api.LivestockCategoryType", ("name",), "livestockcategorytype.json", "management"),
    ("api.LivestockProductionType", ("name",), "livestockproductiontype.json", "management"),
    ("api.ManureManagementType", ("name",), "manuremanagementtype.json", "management"),
    ("api.LargeFisheryGearType", ("name",), "largefisherygeartype.json", "management"),
    ("api.SmallFisheryGearType", ("name",), "smallfisherygeartype.json", "management"),
    # Parameters (concrete subclasses of abstract Parameter)
    ("api.ApplicationParameter", ("name",), "applicationparameter.json", "parameter"),
    ("api.LivestockParameter", ("name",), "livestockparameter.json", "parameter"),
    ("api.IrrigationParameter", ("name",), "irrigationparameter.json", "parameter"),
    ("api.SmallFisheryParameter", ("name",), "smallfisheryparameter.json", "parameter"),
    ("api.LargeFisheryParameter", ("name",), "largefisheryparameter.json", "parameter"),
    ("api.AquacultureParameter", ("name",), "aquacultureparameter.json", "parameter"),
    ("api.GrasslandParameter", ("name",), "grasslandparameter.json", "parameter"),
    ("api.AnnualCroplandParameter", ("name",), "annualcroplandparameter.json", "parameter"),
    ("api.CoastalWetlandParameter", ("name",), "coastalwetlandparameter.json", "parameter"),
    # Definitions (FK to ModuleType, already earlier in order)
    ("api.Definition", ("module_type_id", "id"), "definition.json", "definition"),
    ("api.FieldDefinition", ("module_type_id", "field_name"), "fielddefinition.json", "definition"),
    # Organizations / agencies
    ("api.OrganizationType", ("name",), "organizationtype.json", "organization"),
    ("api.FundingAgency", ("name",), "fundingagency.json", "organization"),
    ("api.ExecutingAgency", ("name",), "executingagency.json", "organization"),
    # Hand-in-Hand
    ("api.HandInHandRegion", ("name",), "handinhandregion.json", "hih"),
    ("api.HandInHandCountry", ("region_id", "name"), "handinhandcountry.json", "hih"),
    ("api.HandInHandAssessment", ("country_id", "year", "name"), "handinhandassessment.json", "hih"),
    # Config
    ("api.ConfigParam", ("name", "id"), "configparam.json", "config"),
]


# --- ipcc app reference models ----------------------------------------------
_IPCC_ENTRIES = [
    # No-FK roots
    ("ipcc.GlobalWarmingPotential", ("id",), "globalwarmingpotential.json", "root"),
    ("ipcc.EmissionFactorCategory", ("id",), "emissionfactorcategory.json", "root"),
    ("ipcc.EmissionType", ("id",), "emissiontype.json", "root"),
    # Depend on api models only
    ("ipcc.DataOnMangrove", ("id",), "dataonmangrove.json", "ipcc"),
    ("ipcc.ForestCombustionFactor", ("id",), "forestcombustionfactor.json", "ipcc"),
    ("ipcc.AfforestationCombustionFactor", ("id",), "afforestationcombustionfactor.json", "ipcc"),
    ("ipcc.LitterDeadwoodCarbonStock", ("id",), "litterdeadwoodcarbonstock.json", "ipcc"),
    ("ipcc.LandUseCarbonStockExchangeFactor", ("id",), "landusecarbonstockexchangefactor.json", "ipcc"),
    ("ipcc.SoilOrcanicCarbonCNRatio", ("id",), "soilorcaniccarboncnratio.json", "ipcc"),
    ("ipcc.ForestManagementRootToShoot", ("id",), "forestmanagementroottoshoot.json", "ipcc"),
    ("ipcc.SoilOrganicCarbon", ("id",), "soilorganiccarbon.json", "ipcc"),
    ("ipcc.ForestTotalBiomass", ("id",), "foresttotalbiomass.json", "ipcc"),
    ("ipcc.AfforestationLandUseStockExchangeFactor", ("id",), "afforestationlandusestockexchangefactor.json", "ipcc"),
    ("ipcc.ForestManagementAGBGrowth", ("id",), "forestmanagementagbgrowth.json", "ipcc"),
    ("ipcc.BurningEmissionFactor", ("id",), "burningemissionfactor.json", "ipcc"),
    ("ipcc.FiresCombustionFactor", ("id",), "firescombustionfactor.json", "ipcc"),
    ("ipcc.CropNitrousEstimationDefaultFactor", ("id",), "cropnitrousestimationdefaultfactor.json", "ipcc"),
    ("ipcc.TillageCarbonStockExchangeFactor", ("id",), "tillagecarbonstockexchangefactor.json", "ipcc"),
    ("ipcc.OrganicInputCarbonStockExchangeFactor", ("id",), "organicinputcarbonstockexchangefactor.json", "ipcc"),
    ("ipcc.CoastalAGB", ("id",), "coastalagb.json", "ipcc"),
    ("ipcc.CoastalBGB", ("id",), "coastalbgb.json", "ipcc"),
    ("ipcc.CoastalLitter", ("id",), "coastallitter.json", "ipcc"),
    ("ipcc.CoastalDeadwood", ("id",), "coastaldeadwood.json", "ipcc"),
    ("ipcc.RewettingCarbonFactor", ("id",), "rewettingcarbonfactor.json", "ipcc"),
    ("ipcc.RewettingMethaneFactor", ("id",), "rewettingmethanefactor.json", "ipcc"),
    ("ipcc.OtherConstructedWaterbodiesEmissionFactor", ("id",), "otherconstructedwaterbodiesemissionfactor.json", "ipcc"),
    ("ipcc.Atwood", ("id",), "atwood.json", "ipcc"),
    ("ipcc.DefaultSoilCarbonStock", ("id",), "defaultsoilcarbonstock.json", "ipcc"),
    ("ipcc.DrainageEmissionFactor", ("id",), "drainageemissionfactor.json", "ipcc"),
    ("ipcc.PerennialAGB", ("id",), "perennialagb.json", "ipcc"),
    ("ipcc.PerennialBGB", ("id",), "perennialbgb.json", "ipcc"),
    ("ipcc.PerennialMaxAGB", ("id",), "perennialmaxagb.json", "ipcc"),
    ("ipcc.CroplandFLU", ("id",), "croplandflu.json", "ipcc"),
    ("ipcc.CroplandFMG", ("id",), "croplandfmg.json", "ipcc"),
    ("ipcc.CroplandFI", ("id",), "croplandfi.json", "ipcc"),
    ("ipcc.AfforestationFLU", ("id",), "afforestationflu.json", "ipcc"),
    ("ipcc.GrasslandBiomass", ("id",), "grasslandbiomass.json", "ipcc"),
    ("ipcc.GrasslandSOC", ("id",), "grasslandsoc.json", "ipcc"),
    ("ipcc.GrasslandStockExchangeFactor", ("id",), "grasslandstockexchangefactor.json", "ipcc"),
    ("ipcc.ElectricityEmission", ("id",), "electricityemission.json", "ipcc"),
    ("ipcc.LargeFisheryFUI", ("id",), "largefisheryfui.json", "ipcc"),
    ("ipcc.SmallFisheryFUI", ("id",), "smallfisheryfui.json", "ipcc"),
    ("ipcc.CropYieldStat", ("id",), "cropyieldstat.json", "ipcc"),
    ("ipcc.InputReference", ("id",), "inputreference.json", "ipcc"),
    ("ipcc.InputEmissionFactor", ("id",), "inputemissionfactor.json", "ipcc"),
    ("ipcc.BuildingEmissionFactor", ("id",), "buildingemissionfactor.json", "ipcc"),
    ("ipcc.RoadEmissionFactor", ("id",), "roademissionfactor.json", "ipcc"),
    # EmissionType already loaded above; LivestockManureEF depends on it
    ("ipcc.LivestockEntericEF", ("id",), "livestockentericef.json", "ipcc"),
    ("ipcc.LivestockManureEF", ("id",), "livestockmanureef.json", "ipcc"),
    ("ipcc.LivestockTAM", ("id",), "livestocktam.json", "ipcc"),
    ("ipcc.LivestockVSER", ("id",), "livestockvser.json", "ipcc"),
    ("ipcc.LivestockAWMS", ("id",), "livestockawms.json", "ipcc"),
    ("ipcc.LivestockNER", ("id",), "livestockner.json", "ipcc"),
    ("ipcc.MethaneEntericFermentationFactor", ("id",), "methaneentericfermentationfactor.json", "ipcc"),
    ("ipcc.ManureManagementVolatilizationMultiplier", ("id",), "manuremanagementvolatilizationmultiplier.json", "ipcc"),
    ("ipcc.EnergyDefaultEmissionFactor", ("id",), "energydefaultemissionfactor.json", "ipcc"),
    ("ipcc.IrrigationSystemData", ("id",), "irrigationsystemdata.json", "ipcc"),
    ("ipcc.IrrigationPhaseData", ("id",), "irrigationphasedata.json", "ipcc"),
    ("ipcc.IrrigationPressureRequirement", ("id",), "irrigationpressurerequirement.json", "ipcc"),
    ("ipcc.RiceDefaultEmissionFactor", ("id",), "ricedefaultemissionfactor.json", "ipcc"),
    ("ipcc.RiceSFO", ("id",), "ricesfo.json", "ipcc"),
    ("ipcc.RiceSFP", ("id",), "ricesfp.json", "ipcc"),
    ("ipcc.RiceSFW", ("id",), "ricesfw.json", "ipcc"),
    ("ipcc.RiceYield", ("id",), "riceyield.json", "ipcc"),
    ("ipcc.TrophicStateFactor", ("id",), "trophicstatefactor.json", "ipcc"),
    ("ipcc.OrganicSoilDrainageEmissionFactor", ("id",), "organicsoildrainageemissionfactor.json", "ipcc"),
    ("ipcc.PeatExtractionEmissionFactor", ("id",), "peatextractionemissionfactor.json", "ipcc"),
    ("ipcc.PeatExtractionConversionFactor", ("id",), "peatextractionconversionfactor.json", "ipcc"),
    ("ipcc.OrganicSoilFuelConsumption", ("id",), "organicsoilfuelconsumption.json", "ipcc"),
    ("ipcc.OrganicSoilGefEmissionFactor", ("id",), "organicsoilgefemissionfactor.json", "ipcc"),
    ("ipcc.OrganicSoilRewettingEmissionFactor", ("id",), "organicsoilrewettingemissionfactor.json", "ipcc"),
    ("ipcc.ForestManagementAGB", ("id",), "forestmanagementagb.json", "ipcc"),
    ("ipcc.FMGData", ("id",), "fmgdata.json", "ipcc"),
    ("ipcc.FIData", ("id",), "fidata.json", "ipcc"),
    ("ipcc.FLUData", ("id",), "fludata.json", "ipcc"),
    ("ipcc.SettlementEF", ("id",), "settlementef.json", "ipcc"),
    ("ipcc.NitrousEmissionFactor", ("id",), "nitrousemissionfactor.json", "ipcc"),
    ("ipcc.InputsNitrousEmissionFactor", ("id",), "inputsnitrousemissionfactor.json", "ipcc"),
    ("ipcc.ValueChainPackagingEmissionFactor", ("id",), "valuechainpackagingemissionfactor.json", "ipcc"),
    ("ipcc.ValueChainRefrigerantEmissionFactor", ("id",), "valuechainrefrigerantemissionfactor.json", "ipcc"),
    ("ipcc.ShadowPriceOfCarbon", ("id",), "shadowpriceofcarbon.json", "ipcc"),
    ("ipcc.FRACarbonStock", ("id",), "fracarbonstock.json", "ipcc"),
    # Custom-manager dependent — must be last
    ("ipcc.TotalBiomassAfterDefo", ("id",), "totalbiomassafterdefo.json", "ipcc-terminal"),
]


def _build(entries):
    return tuple(
        ReferenceModelSpec(
            model=model,
            order_by=order_by,
            fixture_file=fixture_file,
            category=category,
            app=model.split(".", 1)[0],
        )
        for model, order_by, fixture_file, category in entries
    )


MANIFEST = _build(_API_ENTRIES) + _build(_IPCC_ENTRIES)


def manifest_for_app(app):
    if app in (None, "", "all"):
        return MANIFEST
    return tuple(spec for spec in MANIFEST if spec.app == app)


def filter_manifest(app=None, models=None):
    specs = manifest_for_app(app)
    if models:
        wanted = set(models)
        specs = tuple(
            spec for spec in specs
            if spec.model in wanted or spec.model.split(".", 1)[1] in wanted
        )
    return specs
