import pandas as pd
import os
import logging
from dataclasses import dataclass
from typing import List, Dict, Any
import itertools

# Suppress log noise
logging.getLogger().setLevel(logging.CRITICAL)


@dataclass
class LandUseChangeData:
    """Data structure for LandUseChange module aggregation"""

    module_type_start: str = None
    module_type_w: str = None
    module_type_wo: str = None
    climate: str = None
    moisture: str = None
    soil_type: str = None
    region: str = None
    total: float = None

    def to_dict(self):
        return {
            "module": "LandUseChange",
            "module_type_start": self.module_type_start,
            "module_type_w": self.module_type_w,
            "module_type_wo": self.module_type_wo,
            "climate": self.climate,
            "moisture": self.moisture,
            "soil_type": self.soil_type,
            "region": self.region,
            "total": self.total,
        }


def load_module_data(csv_path: str) -> pd.DataFrame:
    """Load module data from CSV file"""
    if not os.path.exists(csv_path):
        print(f"Warning: {csv_path} not found, skipping...")
        return pd.DataFrame()

    print(f"Loading data from {csv_path}")
    df = pd.read_csv(csv_path)
    return df


def get_module_type_name_from_csv(filename: str) -> str:
    """Extract module type name from CSV filename"""
    # Remove .csv extension and get the module name
    module_name = filename.replace(".csv", "")

    # Map CSV names to proper module type names
    module_mapping = {"annualcropland": "Annual Cropland", "livestock": "Livestock", "grassland": "Grassland", "floodedrice": "Flooded Rice", "perennialcropland": "Perennial Cropland"}

    return module_mapping.get(module_name, module_name.title())


def create_landusechange_combinations() -> List[Dict[str, str]]:
    """Create LandUseChange combinations from available module types"""

    # Available module types from existing CSV files
    available_module_types = ["Annual Cropland", "Livestock", "Grassland", "Flooded Rice", "Perennial Cropland"]

    combinations = []

    # Create meaningful combinations (avoid redundant ones)
    # Focus on realistic land use change scenarios
    meaningful_combinations = [
        # Annual Cropland to other types
        ("Annual Cropland", "Grassland", "Annual Cropland"),
        ("Annual Cropland", "Perennial Cropland", "Annual Cropland"),
        ("Annual Cropland", "Livestock", "Annual Cropland"),
        # Grassland to other types
        ("Grassland", "Annual Cropland", "Grassland"),
        ("Grassland", "Perennial Cropland", "Grassland"),
        ("Grassland", "Livestock", "Grassland"),
        # Perennial Cropland to other types
        ("Perennial Cropland", "Annual Cropland", "Perennial Cropland"),
        ("Perennial Cropland", "Grassland", "Perennial Cropland"),
        ("Perennial Cropland", "Livestock", "Perennial Cropland"),
        # Flooded Rice to other types
        ("Flooded Rice", "Annual Cropland", "Flooded Rice"),
        ("Flooded Rice", "Grassland", "Flooded Rice"),
        ("Flooded Rice", "Perennial Cropland", "Flooded Rice"),
    ]

    for start_type, w_type, wo_type in meaningful_combinations:
        combinations.append({"module_type_start": start_type, "module_type_w": w_type, "module_type_wo": wo_type})

    print(f"Created {len(combinations)} meaningful LandUseChange combinations")
    return combinations


def aggregate_landusechange_data(max_records: int = 10000) -> List[LandUseChangeData]:
    """Aggregate LandUseChange data from existing module CSV files"""

    # Path to the minitool directory
    minitool_dir = os.path.join(os.path.dirname(__file__), "minitool")

    # Available CSV files
    csv_files = ["annualcropland.csv", "livestock.csv", "grassland.csv", "floodedrice.csv", "perennialcropland.csv"]

    # Load all module data
    module_data = {}
    for csv_file in csv_files:
        csv_path = os.path.join(minitool_dir, csv_file)
        df = load_module_data(csv_path)
        if not df.empty:
            module_name = get_module_type_name_from_csv(csv_file)
            module_data[module_name] = df
            print(f"Loaded {len(df)} records for {module_name}")

    if not module_data:
        print("No module data found!")
        return []

    # Create LandUseChange combinations
    combinations = create_landusechange_combinations()

    # Get unique environmental factors from all modules
    all_climates = set()
    all_moistures = set()
    all_soil_types = set()
    all_regions = set()

    for df in module_data.values():
        if "climate" in df.columns:
            all_climates.update(df["climate"].unique())
        if "moisture" in df.columns:
            all_moistures.update(df["moisture"].unique())
        if "soil_type" in df.columns:
            all_soil_types.update(df["soil_type"].unique())
        if "region" in df.columns:
            all_regions.update(df["region"].unique())

    print(f"Environmental factors found:")
    print(f"  Climates: {len(all_climates)}")
    print(f"  Moistures: {len(all_moistures)}")
    print(f"  Soil types: {len(all_soil_types)}")
    print(f"  Regions: {len(all_regions)}")

    # Limit the number of environmental combinations to process
    # Take a subset to make it manageable
    climates_subset = list(all_climates)[:3]  # Take first 3 climates
    moistures_subset = list(all_moistures)[:2]  # Take first 2 moistures
    soil_types_subset = list(all_soil_types)[:3]  # Take first 3 soil types
    regions_subset = list(all_regions)[:5]  # Take first 5 regions

    print(f"Using subset for processing:")
    print(f"  Climates: {len(climates_subset)}")
    print(f"  Moistures: {len(moistures_subset)}")
    print(f"  Soil types: {len(soil_types_subset)}")
    print(f"  Regions: {len(regions_subset)}")

    # Generate LandUseChange data
    landusechange_data = []
    records_processed = 0

    for combo in combinations:
        if len(landusechange_data) >= max_records:
            print(f"Reached maximum records limit ({max_records})")
            break

        start_type = combo["module_type_start"]
        w_type = combo["module_type_w"]
        wo_type = combo["module_type_wo"]

        # Check if we have data for all three module types
        if start_type not in module_data or w_type not in module_data or wo_type not in module_data:
            continue

        start_df = module_data[start_type]
        w_df = module_data[w_type]
        wo_df = module_data[wo_type]

        # For each environmental combination, calculate the LandUseChange total
        for climate in climates_subset:
            for moisture in moistures_subset:
                for soil_type in soil_types_subset:
                    for region in regions_subset:
                        if len(landusechange_data) >= max_records:
                            break

                        # Filter data for each module type and environmental factors
                        start_filtered = start_df[(start_df["climate"] == climate) & (start_df["moisture"] == moisture) & (start_df["soil_type"] == soil_type) & (start_df["region"] == region)]

                        w_filtered = w_df[(w_df["climate"] == climate) & (w_df["moisture"] == moisture) & (w_df["soil_type"] == soil_type) & (w_df["region"] == region)]

                        # Calculate LandUseChange total: w - start
                        # This represents the net change from start to with scenario
                        if not start_filtered.empty and not w_filtered.empty:
                            start_total = start_filtered["total"].mean()
                            w_total = w_filtered["total"].mean()

                            # LandUseChange total is the difference between 'with' and 'start'
                            luc_total = w_total - start_total

                            landusechange_data.append(
                                LandUseChangeData(
                                    module_type_start=start_type, module_type_w=w_type, module_type_wo=wo_type, climate=climate, moisture=moisture, soil_type=soil_type, region=region, total=luc_total
                                )
                            )

                            records_processed += 1
                            if records_processed % 100 == 0:
                                print(f"Processed {records_processed} records...")

    print(f"Generated {len(landusechange_data)} LandUseChange records")
    return landusechange_data


def save_landusechange_data(data: List[LandUseChangeData]):
    """Save LandUseChange data to CSV file"""

    if not data:
        print("No data to save!")
        return

    # Convert to DataFrame
    df_data = [item.to_dict() for item in data]
    df = pd.DataFrame(df_data)

    # Save to CSV
    output_path = os.path.join(os.path.dirname(__file__), "minitool", "landusechange.csv")
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} LandUseChange records to {output_path}")

    # Print some statistics
    print(f"\nLandUseChange Data Statistics:")
    print(f"Total records: {len(df)}")
    print(f"Unique module_type_start: {df['module_type_start'].nunique()}")
    print(f"Unique module_type_w: {df['module_type_w'].nunique()}")
    print(f"Unique module_type_wo: {df['module_type_wo'].nunique()}")
    print(f"Total range: {df['total'].min():.4f} to {df['total'].max():.4f}")
    print(f"Mean total: {df['total'].mean():.4f}")
    print(f"Median total: {df['total'].median():.4f}")


def run():
    """Main function to compute LandUseChange data"""
    print("Computing LandUseChange data from existing module CSV files...")

    # Aggregate LandUseChange data with a reasonable limit
    landusechange_data = aggregate_landusechange_data(max_records=5000)

    # Save the data
    save_landusechange_data(landusechange_data)

    print("LandUseChange data computation completed!")


if __name__ == "__main__":
    run()
