import pandas as pd
import matplotlib

matplotlib.use("Agg")  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from scipy import stats
import warnings

warnings.filterwarnings("ignore")


def create_parallel_coordinates_plot(csv_file_path, output_file="parallel_coordinates_plot.png"):
    """
    Create a parallel coordinates plot for the land use change dataset.
    """

    # Read the data
    df = pd.read_csv(csv_file_path)

    # Select relevant columns for parallel coordinates
    columns_to_plot = ["climate", "moisture", "soil_type", "region", "total"]

    # Create a subset for plotting (sample if too large)
    if len(df) > 1000:
        df_sample = df[columns_to_plot].sample(n=1000, random_state=42)
        print("Sampling 1000 rows from {} total rows for better visualization".format(len(df)))
    else:
        df_sample = df[columns_to_plot].copy()

    # Encode categorical variables as numeric for parallel coordinates
    df_encoded = df_sample.copy()

    # Create mappings for categorical variables
    climate_mapping = {val: i for i, val in enumerate(df_encoded["climate"].unique())}
    moisture_mapping = {val: i for i, val in enumerate(df_encoded["moisture"].unique())}
    soil_mapping = {val: i for i, val in enumerate(df_encoded["soil_type"].unique())}
    region_mapping = {val: i for i, val in enumerate(df_encoded["region"].unique())}

    # Apply mappings
    df_encoded["climate_numeric"] = df_encoded["climate"].map(climate_mapping)
    df_encoded["moisture_numeric"] = df_encoded["moisture"].map(moisture_mapping)
    df_encoded["soil_numeric"] = df_encoded["soil_type"].map(soil_mapping)
    df_encoded["region_numeric"] = df_encoded["region"].map(region_mapping)

    # Normalize the total emissions to 0-1 scale
    df_encoded["total_normalized"] = (df_encoded["total"] - df_encoded["total"].min()) / (df_encoded["total"].max() - df_encoded["total"].min())

    # Create the parallel coordinates plot
    fig, ax = plt.subplots(figsize=(15, 10))

    # Define the parallel axes
    axes = ["climate_numeric", "moisture_numeric", "soil_numeric", "region_numeric", "total_normalized"]
    axis_labels = ["Climate", "Moisture", "Soil Type", "Region", "Total Emissions"]

    # Number of axes
    n_axes = len(axes)

    # Create color mapping based on total emissions
    colors = plt.cm.viridis(df_encoded["total_normalized"])

    # Plot each line
    for i in range(len(df_encoded)):
        values = df_encoded[axes].iloc[i].values
        ax.plot(range(n_axes), values, color=colors[i], alpha=0.3, linewidth=0.5)

    # Customize the plot
    ax.set_xticks(range(n_axes))
    ax.set_xticklabels(axis_labels, rotation=45, ha="right")
    ax.set_ylabel("Normalized Values")
    ax.set_title("Parallel Coordinates Plot: Land Use Change Emissions\n(Colored by Total Emissions)", fontsize=14, fontweight="bold")

    # Add grid
    ax.grid(True, alpha=0.3)

    # Create a colorbar
    sm = plt.cm.ScalarMappable(cmap=plt.cm.viridis, norm=plt.Normalize(vmin=df_encoded["total"].min(), vmax=df_encoded["total"].max()))
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, shrink=0.8)
    cbar.set_label("Total Emissions", rotation=270, labelpad=20)

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    plt.close()

    # Print summary statistics
    print("\nDataset Summary:")
    print(f"Total rows: {len(df)}")
    print(f"Rows plotted: {len(df_encoded)}")
    print(f"\nUnique values per category:")
    print(f"Climate zones: {len(df['climate'].unique())}")
    print(f"Moisture levels: {len(df['moisture'].unique())}")
    print(f"Soil types: {len(df['soil_type'].unique())}")
    print(f"Regions: {len(df['region'].unique())}")
    print(f"\nEmissions range: {df['total'].min():.3f} to {df['total'].max():.3f}")

    return df_encoded


def create_enhanced_parallel_plot(csv_file_path, output_file="enhanced_parallel_plot.png"):
    """
    Create an enhanced parallel coordinates plot with better styling.
    """

    # Read the data
    df = pd.read_csv(csv_file_path)

    # Sample data if too large
    if len(df) > 2000:
        df_sample = df.sample(n=2000, random_state=42)
    else:
        df_sample = df.copy()

    # Create the plot using pandas plotting
    fig, ax = plt.subplots(figsize=(16, 10))

    # Select and encode variables
    plot_data = df_sample[["climate", "moisture", "soil_type", "region", "total"]].copy()

    # Encode categorical variables
    for col in ["climate", "moisture", "soil_type", "region"]:
        plot_data[f"{col}_encoded"] = pd.Categorical(plot_data[col]).codes

    # Normalize total emissions
    plot_data["total_norm"] = (plot_data["total"] - plot_data["total"].min()) / (plot_data["total"].max() - plot_data["total"].min())

    # Create parallel coordinates
    axes = ["climate_encoded", "moisture_encoded", "soil_type_encoded", "region_encoded", "total_norm"]

    # Plot lines with color based on total emissions
    for i in range(len(plot_data)):
        values = plot_data[axes].iloc[i].values
        color_intensity = plot_data["total_norm"].iloc[i]
        ax.plot(axes, values, color=plt.cm.plasma(color_intensity), alpha=0.4, linewidth=0.8)

    # Customize plot
    ax.set_title("Enhanced Parallel Coordinates: Land Use Change Analysis\n(Color intensity = Total Emissions)", fontsize=16, fontweight="bold", pad=20)

    # Set axis labels
    ax.set_xticklabels(["Climate", "Moisture", "Soil Type", "Region", "Total Emissions"], rotation=45, ha="right")

    # Add colorbar
    sm = plt.cm.ScalarMappable(cmap=plt.cm.plasma, norm=plt.Normalize(vmin=plot_data["total"].min(), vmax=plot_data["total"].max()))
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, shrink=0.8, pad=0.02)
    cbar.set_label("Total Emissions", rotation=270, labelpad=25, fontsize=12)

    # Styling
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.set_facecolor("#f8f9fa")

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close()

    return plot_data


def create_box_plots(csv_file_path, output_dir="plots"):
    """
    Create box plots for emissions by different categorical variables.
    """
    df = pd.read_csv(csv_file_path)

    # Create subplots
    fig, axes = plt.subplots(2, 2, figsize=(20, 15))
    fig.suptitle("Box Plots: Emissions Distribution by Category", fontsize=16, fontweight="bold")

    # Climate zones
    sns.boxplot(data=df, x="climate", y="total", ax=axes[0, 0])
    axes[0, 0].set_title("Emissions by Climate Zone")
    axes[0, 0].tick_params(axis="x", rotation=45)
    axes[0, 0].grid(True, alpha=0.3)

    # Soil types
    sns.boxplot(data=df, x="soil_type", y="total", ax=axes[0, 1])
    axes[0, 1].set_title("Emissions by Soil Type")
    axes[0, 1].tick_params(axis="x", rotation=45)
    axes[0, 1].grid(True, alpha=0.3)

    # Moisture levels
    sns.boxplot(data=df, x="moisture", y="total", ax=axes[1, 0])
    axes[1, 0].set_title("Emissions by Moisture Level")
    axes[1, 0].tick_params(axis="x", rotation=45)
    axes[1, 0].grid(True, alpha=0.3)

    # Top 10 regions by count
    top_regions = df["region"].value_counts().head(10).index
    df_top_regions = df[df["region"].isin(top_regions)]
    sns.boxplot(data=df_top_regions, x="region", y="total", ax=axes[1, 1])
    axes[1, 1].set_title("Emissions by Top 10 Regions")
    axes[1, 1].tick_params(axis="x", rotation=45)
    axes[1, 1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(f"{output_dir}/box_plots.png", dpi=300, bbox_inches="tight")
    plt.close()

    return df


def create_heatmaps(csv_file_path, output_dir="plots"):
    """
    Create heatmaps for climate × soil type interactions.
    """
    df = pd.read_csv(csv_file_path)

    # Create pivot tables for heatmaps
    fig, axes = plt.subplots(2, 2, figsize=(20, 15))
    fig.suptitle("Heatmaps: Climate and Soil Type Interactions", fontsize=16, fontweight="bold")

    # Climate × Soil Type
    pivot1 = df.pivot_table(values="total", index="climate", columns="soil_type", aggfunc="mean")
    sns.heatmap(pivot1, annot=True, fmt=".2f", cmap="viridis", ax=axes[0, 0])
    axes[0, 0].set_title("Average Emissions: Climate × Soil Type")

    # Climate × Moisture
    pivot2 = df.pivot_table(values="total", index="climate", columns="moisture", aggfunc="mean")
    sns.heatmap(pivot2, annot=True, fmt=".2f", cmap="plasma", ax=axes[0, 1])
    axes[0, 1].set_title("Average Emissions: Climate × Moisture")

    # Soil Type × Moisture
    pivot3 = df.pivot_table(values="total", index="soil_type", columns="moisture", aggfunc="mean")
    sns.heatmap(pivot3, annot=True, fmt=".2f", cmap="coolwarm", ax=axes[1, 0])
    axes[1, 0].set_title("Average Emissions: Soil Type × Moisture")

    # Top regions × Climate
    top_regions = df["region"].value_counts().head(8).index
    df_top = df[df["region"].isin(top_regions)]
    pivot4 = df_top.pivot_table(values="total", index="region", columns="climate", aggfunc="mean")
    sns.heatmap(pivot4, annot=True, fmt=".2f", cmap="RdYlBu_r", ax=axes[1, 1])
    axes[1, 1].set_title("Average Emissions: Top Regions × Climate")

    plt.tight_layout()
    plt.savefig(f"{output_dir}/heatmaps.png", dpi=300, bbox_inches="tight")
    plt.close()

    return df


def create_bar_charts(csv_file_path, output_dir="plots"):
    """
    Create bar charts for top regions and climate zones.
    """
    df = pd.read_csv(csv_file_path)

    fig, axes = plt.subplots(2, 2, figsize=(20, 15))
    fig.suptitle("Bar Charts: Emissions by Category", fontsize=16, fontweight="bold")

    # Average emissions by climate
    climate_avg = df.groupby("climate")["total"].mean().sort_values(ascending=True)
    climate_avg.plot(kind="barh", ax=axes[0, 0], color="skyblue")
    axes[0, 0].set_title("Average Emissions by Climate Zone")
    axes[0, 0].grid(True, alpha=0.3)

    # Average emissions by soil type
    soil_avg = df.groupby("soil_type")["total"].mean().sort_values(ascending=True)
    soil_avg.plot(kind="barh", ax=axes[0, 1], color="lightcoral")
    axes[0, 1].set_title("Average Emissions by Soil Type")
    axes[0, 1].grid(True, alpha=0.3)

    # Top 15 regions by average emissions
    region_avg = df.groupby("region")["total"].mean().sort_values(ascending=True).tail(15)
    region_avg.plot(kind="barh", ax=axes[1, 0], color="lightgreen")
    axes[1, 0].set_title("Top 15 Regions by Average Emissions")
    axes[1, 0].grid(True, alpha=0.3)

    # Emissions by moisture level
    moisture_avg = df.groupby("moisture")["total"].mean().sort_values(ascending=True)
    moisture_avg.plot(kind="barh", ax=axes[1, 1], color="gold")
    axes[1, 1].set_title("Average Emissions by Moisture Level")
    axes[1, 1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(f"{output_dir}/bar_charts.png", dpi=300, bbox_inches="tight")
    plt.close()

    return df


def create_faceted_scatter_plots(csv_file_path, output_dir="plots"):
    """
    Create faceted scatter plots for detailed analysis.
    """
    df = pd.read_csv(csv_file_path)

    # Sample data if too large
    if len(df) > 2000:
        df_sample = df.sample(n=2000, random_state=42)
    else:
        df_sample = df.copy()

    # Create faceted scatter plot
    g = sns.FacetGrid(df_sample, col="climate", col_wrap=3, height=4, aspect=1.2)
    g.map_dataframe(sns.scatterplot, x="moisture", y="total", hue="soil_type", alpha=0.7, s=50)
    g.add_legend(title="Soil Type")
    g.set_axis_labels("Moisture Level", "Total Emissions")
    g.fig.suptitle("Faceted Scatter Plot: Emissions by Climate Zone\n(Colored by Soil Type)", y=1.02, fontsize=14)

    plt.tight_layout()
    plt.savefig(f"{output_dir}/faceted_scatter.png", dpi=300, bbox_inches="tight")
    plt.close()

    return df_sample


def create_histogram_density_plots(csv_file_path, output_dir="plots"):
    """
    Create histogram and density plots for emissions distribution.
    """
    df = pd.read_csv(csv_file_path)

    fig, axes = plt.subplots(2, 2, figsize=(20, 15))
    fig.suptitle("Distribution Analysis: Emissions Data", fontsize=16, fontweight="bold")

    # Overall distribution
    axes[0, 0].hist(df["total"], bins=50, alpha=0.7, color="skyblue", edgecolor="black")
    axes[0, 0].set_title("Overall Emissions Distribution")
    axes[0, 0].set_xlabel("Total Emissions")
    axes[0, 0].set_ylabel("Frequency")
    axes[0, 0].grid(True, alpha=0.3)

    # Density plot by climate
    for climate in df["climate"].unique():
        climate_data = df[df["climate"] == climate]["total"]
        axes[0, 1].hist(climate_data, bins=30, alpha=0.6, label=climate, density=True)
    axes[0, 1].set_title("Emissions Density by Climate Zone")
    axes[0, 1].set_xlabel("Total Emissions")
    axes[0, 1].set_ylabel("Density")
    axes[0, 1].legend(bbox_to_anchor=(1.05, 1), loc="upper left")
    axes[0, 1].grid(True, alpha=0.3)

    # Box plot with violin
    sns.violinplot(data=df, x="soil_type", y="total", ax=axes[1, 0])
    axes[1, 0].set_title("Emissions Distribution by Soil Type (Violin Plot)")
    axes[1, 0].tick_params(axis="x", rotation=45)
    axes[1, 0].grid(True, alpha=0.3)

    # Q-Q plot for normality
    stats.probplot(df["total"], dist="norm", plot=axes[1, 1])
    axes[1, 1].set_title("Q-Q Plot: Normality Check")
    axes[1, 1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(f"{output_dir}/histogram_density.png", dpi=300, bbox_inches="tight")
    plt.close()

    return df


def create_bubble_charts(csv_file_path, output_dir="plots"):
    """
    Create bubble charts for multi-dimensional analysis.
    """
    df = pd.read_csv(csv_file_path)

    # Aggregate data for bubble chart
    bubble_data = df.groupby(["climate", "soil_type"]).agg({"total": ["mean", "count"]}).reset_index()
    bubble_data.columns = ["climate", "soil_type", "avg_emissions", "count"]

    fig, axes = plt.subplots(1, 2, figsize=(20, 8))
    fig.suptitle("Bubble Charts: Multi-dimensional Analysis", fontsize=16, fontweight="bold")

    # Bubble chart 1: Climate vs Soil Type
    scatter1 = axes[0].scatter(bubble_data["climate"], bubble_data["soil_type"], s=bubble_data["count"] * 10, c=bubble_data["avg_emissions"], cmap="viridis", alpha=0.7, edgecolors="black")
    axes[0].set_title("Climate vs Soil Type\n(Bubble size = Count, Color = Avg Emissions)")
    axes[0].tick_params(axis="x", rotation=45)
    axes[0].tick_params(axis="y", rotation=0)
    axes[0].grid(True, alpha=0.3)

    # Add colorbar
    cbar1 = plt.colorbar(scatter1, ax=axes[0])
    cbar1.set_label("Average Emissions")

    # Bubble chart 2: Region analysis
    region_data = df.groupby("region").agg({"total": ["mean", "count"], "climate": lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[0]}).reset_index()
    region_data.columns = ["region", "avg_emissions", "count", "dominant_climate"]

    # Top 20 regions
    region_data = region_data.nlargest(20, "count")

    axes[1].scatter(
        region_data["count"], region_data["avg_emissions"], s=region_data["count"] * 2, c=region_data["dominant_climate"].astype("category").cat.codes, cmap="tab10", alpha=0.7, edgecolors="black"
    )
    axes[1].set_title("Region Analysis\n(Bubble size = Count, Color = Dominant Climate)")
    axes[1].set_xlabel("Number of Records")
    axes[1].set_ylabel("Average Emissions")
    axes[1].grid(True, alpha=0.3)

    # Add region labels for largest bubbles
    for i, row in region_data.nlargest(5, "count").iterrows():
        axes[1].annotate(row["region"], (row["count"], row["avg_emissions"]), xytext=(5, 5), textcoords="offset points", fontsize=8)

    plt.tight_layout()
    plt.savefig(f"{output_dir}/bubble_charts.png", dpi=300, bbox_inches="tight")
    plt.close()

    return bubble_data


def create_ridge_plots(csv_file_path, output_dir="plots"):
    """
    Create ridge plots for distribution comparison.
    """
    df = pd.read_csv(csv_file_path)

    # Create ridge plot for climate zones
    fig, axes = plt.subplots(len(df["climate"].unique()), 1, figsize=(12, 2 * len(df["climate"].unique())))
    if len(df["climate"].unique()) == 1:
        axes = [axes]

    fig.suptitle("Ridge Plot: Emissions Distribution by Climate Zone", fontsize=16, fontweight="bold")

    for i, climate in enumerate(sorted(df["climate"].unique())):
        climate_data = df[df["climate"] == climate]["total"]
        axes[i].hist(climate_data, bins=30, alpha=0.7, color=plt.cm.viridis(i / len(df["climate"].unique())))
        axes[i].set_title(f"{climate} (n={len(climate_data)})")
        axes[i].set_xlabel("Total Emissions")
        axes[i].grid(True, alpha=0.3)
        axes[i].set_ylabel("Frequency")

    plt.tight_layout()
    plt.savefig(f"{output_dir}/ridge_plots.png", dpi=300, bbox_inches="tight")
    plt.close()

    return df


def create_treemap(csv_file_path, output_dir="plots"):
    """
    Create treemap for hierarchical data visualization.
    """
    try:
        import squarify  # type: ignore
    except ImportError:
        print("Installing squarify for treemap...")
        import subprocess

        subprocess.check_call(["pip", "install", "squarify"])
        import squarify  # type: ignore

    df = pd.read_csv(csv_file_path)

    # Create hierarchical data
    hierarchy_data = df.groupby(["climate", "soil_type"]).agg({"total": ["mean", "count"]}).reset_index()
    hierarchy_data.columns = ["climate", "soil_type", "avg_emissions", "count"]

    fig, axes = plt.subplots(1, 2, figsize=(20, 10))
    fig.suptitle("Treemap: Hierarchical Data Visualization", fontsize=16, fontweight="bold")

    # Treemap 1: By climate zones
    climate_sizes = df.groupby("climate")["total"].count()
    colors = plt.cm.Set3(np.linspace(0, 1, len(climate_sizes)))
    squarify.plot(sizes=climate_sizes.values, label=climate_sizes.index, color=colors, alpha=0.7, ax=axes[0])
    axes[0].set_title("Data Distribution by Climate Zone")
    axes[0].axis("off")

    # Treemap 2: By soil types
    soil_sizes = df.groupby("soil_type")["total"].count()
    colors2 = plt.cm.Pastel1(np.linspace(0, 1, len(soil_sizes)))
    squarify.plot(sizes=soil_sizes.values, label=soil_sizes.index, color=colors2, alpha=0.7, ax=axes[1])
    axes[1].set_title("Data Distribution by Soil Type")
    axes[1].axis("off")

    plt.tight_layout()
    plt.savefig(f"{output_dir}/treemap.png", dpi=300, bbox_inches="tight")
    plt.close()

    return hierarchy_data


# Main execution
def run():
    # Path to your CSV file
    import os

    # Create plots directory
    plots_dir = "plots"
    os.makedirs(plots_dir, exist_ok=True)

    csv_path = os.path.join(os.path.dirname(__file__), "minitool", "landusechange.csv")

    print("🌍 LAND USE CHANGE DATA VISUALIZATION SUITE")
    print("=" * 60)

    # 1. Parallel Coordinates Plots
    print("\n1️⃣ Creating Parallel Coordinates Plots...")
    print("-" * 40)
    create_parallel_coordinates_plot(csv_path, f"{plots_dir}/parallel_coords.png")
    create_enhanced_parallel_plot(csv_path, f"{plots_dir}/enhanced_parallel.png")

    # 2. Box Plots
    print("\n2️⃣ Creating Box Plots...")
    print("-" * 40)
    create_box_plots(csv_path, plots_dir)

    # 3. Heatmaps
    print("\n3️⃣ Creating Heatmaps...")
    print("-" * 40)
    create_heatmaps(csv_path, plots_dir)

    # 4. Bar Charts
    print("\n4️⃣ Creating Bar Charts...")
    print("-" * 40)
    create_bar_charts(csv_path, plots_dir)

    # 5. Faceted Scatter Plots
    print("\n5️⃣ Creating Faceted Scatter Plots...")
    print("-" * 40)
    create_faceted_scatter_plots(csv_path, plots_dir)

    # 6. Histogram/Density Plots
    print("\n6️⃣ Creating Histogram/Density Plots...")
    print("-" * 40)
    create_histogram_density_plots(csv_path, plots_dir)

    # 7. Bubble Charts
    print("\n7️⃣ Creating Bubble Charts...")
    print("-" * 40)
    create_bubble_charts(csv_path, plots_dir)

    # 8. Ridge Plots
    print("\n8️⃣ Creating Ridge Plots...")
    print("-" * 40)
    create_ridge_plots(csv_path, plots_dir)

    # 9. Treemap
    print("\n9️⃣ Creating Treemap...")
    print("-" * 40)
    create_treemap(csv_path, plots_dir)

    print("\n✅ ALL VISUALIZATIONS COMPLETE!")
    print("=" * 60)
    print(f"📁 All plots saved in: {plots_dir}/")
    print("\nGenerated visualizations:")
    print("• Parallel Coordinates (2 versions)")
    print("• Box Plots (4 subplots)")
    print("• Heatmaps (4 interaction matrices)")
    print("• Bar Charts (4 category comparisons)")
    print("• Faceted Scatter Plots (climate-based facets)")
    print("• Histogram/Density Plots (distribution analysis)")
    print("• Bubble Charts (multi-dimensional analysis)")
    print("• Ridge Plots (distribution comparison)")
    print("• Treemap (hierarchical data)")


def create_all_plots(csv_file_path):
    """
    Create all visualization types for the land use change dataset.
    """
    import os

    # Create plots directory
    plots_dir = "plots"
    os.makedirs(plots_dir, exist_ok=True)

    print("🌍 COMPREHENSIVE LAND USE CHANGE VISUALIZATION")
    print("=" * 60)

    # Execute all visualization functions
    functions = [
        ("Parallel Coordinates", lambda: create_parallel_coordinates_plot(csv_file_path, f"{plots_dir}/parallel_coords.png")),
        ("Enhanced Parallel Coordinates", lambda: create_enhanced_parallel_plot(csv_file_path, f"{plots_dir}/enhanced_parallel.png")),
        ("Box Plots", lambda: create_box_plots(csv_file_path, plots_dir)),
        ("Heatmaps", lambda: create_heatmaps(csv_file_path, plots_dir)),
        ("Bar Charts", lambda: create_bar_charts(csv_file_path, plots_dir)),
        ("Faceted Scatter Plots", lambda: create_faceted_scatter_plots(csv_file_path, plots_dir)),
        ("Histogram/Density Plots", lambda: create_histogram_density_plots(csv_file_path, plots_dir)),
        ("Bubble Charts", lambda: create_bubble_charts(csv_file_path, plots_dir)),
        ("Ridge Plots", lambda: create_ridge_plots(csv_file_path, plots_dir)),
        ("Treemap", lambda: create_treemap(csv_file_path, plots_dir)),
    ]

    for i, (name, func) in enumerate(functions, 1):
        print(f"\n{i}️⃣ Creating {name}...")
        print("-" * 40)
        try:
            func()
            print(f"✅ {name} completed successfully")
        except Exception as e:
            print(f"❌ Error creating {name}: {str(e)}")

    print(f"\n🎉 Visualization suite complete! Check the '{plots_dir}/' directory for all plots.")


if __name__ == "__main__":
    # Run the complete visualization suite
    run()
