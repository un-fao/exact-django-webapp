"""Named constants for Excel report generation."""

# Shadow Price of Carbon annual increase rate (post-2050 extrapolation)
SPC_INCREASE_RATE = 0.0225

# Worksheet names
WS_RESULTS = "Results"
WS_METADATA = "Metadata"
WS_ADDITIONAL_INDICATORS = "Additional Indicators"
WS_SHADOW_PRICE = "Shadow Price of Carbon"
WS_INVENTORY = "Inventory"

# Results worksheet header rows
ROW_HEADER_YEARS = 1
ROW_CUMULATIVE_BALANCE = 2
ROW_YEARLY_BALANCE = 3
# Per-category rows from row 4 down: (label, EmissionsAggregator attribute).
ROW_FIRST_CATEGORY = 4
SUMMARY_CATEGORY_ROWS = (
    ("CO2 in above-ground biomass (AGB)", "agb_co2"),
    ("CO2 in below-ground biomass (BGB)", "bgb_co2"),
    ("CO2 in biomass (AGB+BGB)", "biomass_co2"),
    ("CO2 in dead organic matter (litter and deadwood)", "dom_co2"),
    ("CO2 in soils", "soil_co2"),
    ("Other CO2", "other_co2"),
    ("CH4", "ch4"),
    ("N2O", "n2o"),
    ("Other GHGs", "other_ghgs"),
)
ROW_CUMULATIVE_HECTARES = ROW_FIRST_CATEGORY + len(SUMMARY_CATEGORY_ROWS)
ROW_CUMULATIVE_HEADS = ROW_CUMULATIVE_HECTARES + 1
ROW_CUMULATIVE_CATCH = ROW_CUMULATIVE_HECTARES + 2
ROW_YEARLY_FLUX_WO = ROW_CUMULATIVE_HECTARES + 3
ROW_YEARLY_FLUX_W = ROW_CUMULATIVE_HECTARES + 4

# Metadata worksheet column indices
META_COL_LABEL = 1
META_COL_START = 2
META_COL_WITH = 3
META_COL_WITHOUT = 4
META_COL_TIER2 = 5
META_COL_COMMENT = 6

# Project-level metadata rows
META_ROW_DOWNLOAD_DATE = 1
META_ROW_PROJECT_NAME = 2
META_ROW_STATUS = 3
META_ROW_COUNTRY = 4
META_ROW_CLIMATE = 5
META_ROW_MOISTURE = 6
META_ROW_SOIL_TYPE = 7
META_ROW_IMPLEMENTATION_YEARS = 8
META_ROW_CAPITALIZATION_YEARS = 9
META_ROW_TOTAL_DURATION = 10
META_ROW_GWP = 11
META_ROW_GWP_CO2 = 12
META_ROW_GWP_CH4 = 13
META_ROW_GWP_N2O = 14
META_ROW_GWP_CH4_FOSSIL = 15
META_ROW_START_WITH_HEADER = 18

# Shadow price worksheet row constants
SPC_ROW_HEADER = 1
SPC_ROW_YEAR = 2
SPC_ROW_WO = 3
SPC_ROW_WO_LOW = 4
SPC_ROW_WO_HIGH = 5
SPC_ROW_WITH = 8
SPC_ROW_WITH_LOW = 9
SPC_ROW_WITH_HIGH = 10
SPC_NPV_START_ROW = 12
SPC_NOMINAL_ROW = 28

# Inventory worksheet column indices
INV_COL_ACTIVITY = 1
INV_COL_MODULE = 2
INV_COL_IPCC_CATEGORY = 3
INV_COL_GAS_TYPE = 4
INV_COL_VALUE = 5

# Results column data starts at
DATA_COL_START = 2  # Column 2 = first data year
