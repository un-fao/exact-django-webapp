#!/usr/bin/env python
"""
Script to extract all IPCC models as CSV files.
Uses the same structure as the export_as_csv method in ipcc/admin.py
"""

import os
import sys
import csv
import django
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoexact.settings")
django.setup()

from django.db.models import ForeignKey, OneToOneField, ManyToManyField
from ipcc.models import *


def get_model_fields(model):
    """Get all field names for a model, excluding many-to-many fields"""
    return [field.name for field in model._meta.fields]


def export_model_as_csv(model_class, output_dir):
    """Export a single model as CSV using the same structure as admin.py export_as_csv"""
    meta = model_class._meta
    field_names = get_model_fields(model_class)

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Create CSV file
    filename = f"{meta}.csv"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)

        # Write header
        writer.writerow(field_names)

        # Write data
        queryset = model_class.objects.all()
        for obj in queryset:
            row = []
            for field_name in field_names:
                value = getattr(obj, field_name)
                # Handle None values and convert to string
                if value is None:
                    row.append("")
                else:
                    row.append(str(value))
            writer.writerow(row)

    print(f"Exported {queryset.count()} records to {filepath}")
    return filepath


def get_all_ipcc_models():
    """Get all IPCC model classes"""
    from ipcc import models

    # Get all classes that inherit from Model
    model_classes = []
    for attr_name in dir(models):
        attr = getattr(models, attr_name)
        if isinstance(attr, type) and issubclass(attr, django.db.models.Model) and attr != django.db.models.Model:
            model_classes.append(attr)

    return model_classes


def run():
    """Main function to export all IPCC models as CSV"""
    # Create output directory
    output_dir = "ipcc_data"

    print(f"Starting export of IPCC models to {output_dir}/")
    print("=" * 50)

    # Get all IPCC models
    model_classes = get_all_ipcc_models()

    # Sort models by name for consistent output
    model_classes.sort(key=lambda x: x._meta.model_name)

    exported_files = []

    for model_class in model_classes:
        try:
            filepath = export_model_as_csv(model_class, output_dir)
            exported_files.append(filepath)
        except Exception as e:
            print(f"Error exporting {model_class._meta.model_name}: {e}")

    print("=" * 50)
    print(f"Export completed! {len(exported_files)} files exported to {output_dir}/")
    print("\nExported files:")
    for filepath in exported_files:
        print(f"  - {os.path.basename(filepath)}")
