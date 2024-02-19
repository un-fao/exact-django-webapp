import json
import os
from collections import defaultdict

import matplotlib.pyplot as plt
from PIL import Image


# Modified function to save graphs for emissions data with total emissions in the title
def save_emission_graphs_with_totals(module_name, emissions_data, data_type, save_path):
    activity_data = defaultdict(lambda: defaultdict(list))
    total_emissions_by_activity = defaultdict(float)

    for entry in emissions_data:
        activity = entry["activity"]
        emissions_list = entry["emissions"]

        for index, emission in enumerate(emissions_list):
            year = index  # Year starts from 0 and increases by 1 each year
            gas_type = emission["gas_type"]["name"]
            value = emission["value"]
            activity_data[activity][gas_type].append((year, value))
            total_emissions_by_activity[activity] += value

    for activity, gases in activity_data.items():
        total_emissions = total_emissions_by_activity[activity]
        plt.figure(figsize=(12, 6))
        plt.title(f"{module_name} - {data_type} - Emissions for Activity: {activity} (Total: {total_emissions:.2f})")
        plt.xlabel("Year (starting from 0)")
        plt.ylabel("Emission Value")

        max_years = max(len(data) for data in gases.values())

        for gas_type, data in gases.items():
            years = [year for year, _ in data]
            values = [value for _, value in data]

            plt.plot(years, values, label=gas_type, marker="o")

        plt.xticks(range(0, max_years))
        plt.legend()

        filename = f"{module_name.replace(' ', '_')}_{data_type.replace(' ', '_')}_{activity.replace(' ', '_')}.png"
        plt.savefig(os.path.join(save_path, filename))
        plt.close()


# Path to the JSON file - Update this path as needed
file_path = "/Users/claudiolavacca/Desktop/forest190220241302.json"

# Load the JSON data from the uploaded file
with open(file_path, "r") as file:
    data = json.load(file)

# Adjusting the script to directly process the data for the current JSON structure
modules_data = {"Forest Results": {"total_w": data.get("total_w", []), "total_wo": data.get("total_wo", [])}}

# Directory to save the plots - Update this path as needed
save_directory = "your_directory_for_saving_plots/"
os.makedirs(save_directory, exist_ok=True)

# Saving plots for 'total_w' and 'total_wo' with total emissions in the title
for module_name, emissions_info in modules_data.items():
    save_emission_graphs_with_totals(module_name, emissions_info["total_w"], "With", save_directory)
    save_emission_graphs_with_totals(module_name, emissions_info["total_wo"], "Without", save_directory)

# Combining all images into a single large image
plot_files = [os.path.join(save_directory, file) for file in os.listdir(save_directory) if file.endswith(".png")]
images = [Image.open(file) for file in plot_files]
widths, heights = zip(*(i.size for i in images))

total_width = max(widths)
total_height = sum(heights)
combined_image = Image.new("RGB", (total_width, total_height))

y_offset = 0
for img in images:
    combined_image.paste(img, (0, y_offset))
    y_offset += img.size[1]

# Path to the combined image - Update this path as needed
combined_image_path = "path_to_combined_image.png"
combined_image.save(combined_image_path)
