import csv

from ipcc.models import ForestManagementAGB


def export_to_csv(model):
    # Fetch all objects from the model
    queryset = model.objects.all()

    # Define field names for the CSV header
    field_names = [field.name for field in model._meta.fields]

    # Prepare the data
    data = [field_names]  # Start with header row
    for obj in queryset:

        # If a field in the object has itself an attribute "name", use it. Otherwise, use the field
        row = [getattr(getattr(obj, field), "name") if hasattr(getattr(obj, field), "name") else getattr(obj, field) for field in field_names]
        data.append(row)

    # Write data to a CSV file
    with open("forest_agb.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerows(data)


# Call the function with your model
export_to_csv(ForestManagementAGB)
