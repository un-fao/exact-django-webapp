from rest_framework.permissions import AllowAny
from rest_framework import viewsets
import api.models as api_models
import api.serializers as api_serializers
import public.serializers as public_serializers
import logging as log
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from rest_framework import status as http_status
from rest_framework.response import Response
from concurrent.futures import ThreadPoolExecutor, as_completed
from api import security
import api.utilities as utils
from rest_framework.decorators import action
import api.calculators as calculators
import api.defaults as api_defaults
import types
import api.labels as labels
from django.http import HttpResponse
from api import reports
from django.utils.translation import activate
from django.conf import settings
from django.utils.translation import gettext as _
from datetime import datetime
import os
import base64
import io
import numpy as np
import ipcc.models as ipcc_models
import matplotlib.pyplot as plt
from django.shortcuts import render


def get_modules(activity: api_models.Activity, serialized=True) -> list:
    modules = activity.modules
    module_serializers_list = []

    for module in modules:
        module_dict = public_serializers.get_public_module_serializer(module.__class__)(module).data
        module_serializers_list.append(module_dict)

    return module_serializers_list if serialized else modules


class DefaultPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class PublicProjectViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows public projects to be viewed.
    """

    queryset = api_models.Project.objects.filter(is_public=True)
    serializer_class = public_serializers.PublicProjectSerializer
    permission_classes = [AllowAny]

    @action(detail=True, methods=["get"])
    def activities(self, request, pk=None):
        project: api_models.Project = get_object_or_404(self.queryset, pk=pk)
        activities = project.activities.all()
        serializer = public_serializers.PublicActivitySerializer(activities, many=True)
        return Response(data=serializer.data, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "activities",
                openapi.IN_QUERY,
                description="Comma-separated list of activity IDs to filter results",
                type=openapi.TYPE_STRING,
            ),
            openapi.Parameter(
                "cached",
                openapi.IN_QUERY,
                description="Return cached results",
                type=openapi.TYPE_BOOLEAN,
            ),
        ],
        responses={404: "Project not found", 403: "Selected user does not have permission to view project results", 200: api_serializers.ProjectResultSerializer},
    )
    def results(self, request, pk=None):
        """
        Calculates and returns total emissions for each module in the project.
        """

        try:
            project = self.queryset.prefetch_related("activities").get(pk=pk)
        except api_models.Project.DoesNotExist:
            return utils.ErrorResponse("Project not found", status=http_status.HTTP_404_NOT_FOUND)

        serialized_project = api_serializers.ProjectResultSerializer(project, context={"request": request}).data

        selected_activities = request.query_params.get("activities", "").split(",")
        if selected_activities == [""]:
            selected_activities = project.activities.values_list("id", flat=True)

        response = serialized_project
        response["activities"] = []

        # Function to process an activity
        def process_activity(activity_pk):
            return PublicActivityViewSet.results(self, request, pk=activity_pk).data

        activity_pks = project.activities.filter(pk__in=selected_activities).values_list("id", flat=True)

        # Use ThreadPoolExecutor to run tasks in parallel
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit all tasks to the executor
            future_to_pk = {executor.submit(process_activity, pk): pk for pk in activity_pks}

            for future in as_completed(future_to_pk):
                pk = future_to_pk[future]
                try:
                    data = future.result()
                except Exception as exc:
                    log.error(f"Activity {pk} generated an exception: {exc}")
                    # You can choose to handle exceptions differently if needed
                else:
                    response["activities"].append(data)

        return Response(data=response, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "activities",
                openapi.IN_QUERY,
                description="List of activity IDs to include in the report",
                type=openapi.TYPE_ARRAY,
                items={"type": openapi.TYPE_INTEGER},
            ),
            openapi.Parameter(
                "template",
                openapi.IN_QUERY,
                description="Name of the report template to render",
                type=openapi.TYPE_STRING,
                required=False,
            ),
        ],
        responses={404: "Project not found", 403: "Selected user does not have permission to view project results"},
    )
    def report(self, request, pk=None):
        project: api_models.Project = get_object_or_404(self.queryset, pk=pk)

        if not project.is_ready():
            log.error("Project is not ready")
            return utils.ErrorResponse("To get a report for a project, all activities must have been completed.", status=http_status.HTTP_400_BAD_REQUEST)

        if request.query_params.get("template", None):
            response = self.template(request, pk=pk)
            return response

        selected_activities = request.query_params.get("activities", "").split(",")
        if selected_activities == [""]:
            selected_activities = None
        else:
            selected_activities = project.activities.filter(pk__in=selected_activities)

        try:
            report = reports.BaseProjectReport(project, activities=selected_activities)
            _, file_bytes_buffer = report.build_report()
            report.close_file()
        except Exception as e:
            log.error(f"Error generating report: {e}")
            return utils.ErrorResponse(str(e), status=http_status.HTTP_422_UNPROCESSABLE_ENTITY)

        try:
            response = HttpResponse(file_bytes_buffer, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f'attachment; filename="{project.name}_report.xlsx"'

            return response
        except FileNotFoundError:
            return utils.ErrorResponse("Error generating report: file not found", status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return utils.ErrorResponse(str(e), status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(
        operation_description="Generate a PDF from an HTML template",
        manual_parameters=[
            openapi.Parameter("template", openapi.IN_QUERY, description="Name of the Django template to render", type=openapi.TYPE_STRING, required=True),
            openapi.Parameter("lang", openapi.IN_QUERY, description="Language of the template", type=openapi.TYPE_STRING, required=False),
        ],
        responses={200: "PDF file generated successfully", 400: "Template name not provided or template not found", 500: "Error generating PDF"},
        produces=["application/pdf"],
    )
    def template(self, request, pk=None):
        template_name = request.query_params.get("template")
        try:
            lang = request.query_params.get("lang", request.LANGUAGE_CODE)
        except Exception as e:
            log.error(f"Error getting language: {e}")
            lang = "en"

        if not template_name:
            return utils.ErrorResponse("Template name is required", status=http_status.HTTP_400_BAD_REQUEST)

        template_dir = os.path.join(settings.BASE_DIR, "api", "templates", "reports")
        if not os.path.exists(f"{template_dir}/{template_name}_{lang}.html"):
            return utils.ErrorResponse(f"Template '{template_name}' not found for language '{lang}'", status=http_status.HTTP_400_BAD_REQUEST)

        try:
            activate(lang)

            project: api_models.Project = get_object_or_404(self.queryset, pk=pk)
            soc: ipcc_models.SoilOrganicCarbon = ipcc_models.SoilOrganicCarbon.objects.get(climate=project.climate, moisture=project.moisture, soil_type=project.soil_type)

            # Calculate total area of all activities
            total_area = sum(activity.area for activity in project.activities.all())

            # Call project results endpoint
            total_results_response = self.results(request, pk=pk)

            total_data = total_results_response.data
            activities = total_data["activities"]
            modules = [module for activity in activities for module in activity["modules"]]
            results = [module["results"] for module in modules]
            total_w = sum(result["total_w"] for result in results)
            total_wo = sum(result["total_wo"] for result in results)
            total_balance = total_w - total_wo

            project_emissions_w = total_w
            project_emissions_wo = total_wo
            project_emissions_balance = total_balance

            new_request = request._request
            new_request.query_params = request.query_params.copy()
            new_request.query_params["aggregate"] = "gas"

            gas_results_response = self.results(new_request, pk=pk)
            gas_data = gas_results_response.data
            activities = gas_data["activities"]
            modules = [module for activity in activities for module in activity["modules"]]
            results = [module["results"] for module in modules]

            emissions_w = [result["total_w"] for result in results]
            emissions_wo = [result["total_wo"] for result in results]

            co2_w = {"name": "CO2", "value": 0}
            ch4_w = {"name": "CH4", "value": 0}
            n2o_w = {"name": "N2O", "value": 0}
            co_w = {"name": "CO", "value": 0}
            doc_w = {"name": "DOC", "value": 0}
            other_w = {"name": "OTHER", "value": 0}

            gases_w = [co2_w, ch4_w, n2o_w, co_w, doc_w, other_w]

            for w in emissions_w:
                for g in w:
                    if g["gas_type"]["name"] == "CO2":
                        co2_w["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "CH4":
                        ch4_w["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "N2O":
                        n2o_w["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "CO":
                        co_w["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "DOC":
                        doc_w["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "OTHER":
                        other_w["value"] += sum([e["value"] for e in g["emissions"]])

            co2_wo = {"name": "CO2", "value": 0}
            ch4_wo = {"name": "CH4", "value": 0}
            n2o_wo = {"name": "N2O", "value": 0}
            co_wo = {"name": "CO", "value": 0}
            doc_wo = {"name": "DOC", "value": 0}
            other_wo = {"name": "OTHER", "value": 0}

            gases_wo = [co2_wo, ch4_wo, n2o_wo, co_wo, doc_wo, other_wo]

            for wo in emissions_wo:
                for g in wo:
                    if g["gas_type"]["name"] == "CO2":
                        co2_wo["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "CH4":
                        ch4_wo["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "N2O":
                        n2o_wo["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "CO":
                        co_wo["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "DOC":
                        doc_wo["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "OTHER":
                        other_wo["value"] += sum([e["value"] for e in g["emissions"]])

            balances = [result["balance"] for result in results]

            co2 = {"name": "CO2", "value": 0}
            ch4 = {"name": "CH4", "value": 0}
            n2o = {"name": "N2O", "value": 0}
            co = {"name": "CO", "value": 0}
            doc = {"name": "DOC", "value": 0}
            other = {"name": "OTHER", "value": 0}

            for b in balances:
                for g in b:
                    if g["gas_type"]["name"] == "CO2":
                        co2["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "CH4":
                        ch4["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "N2O":
                        n2o["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "CO":
                        co["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "DOC":
                        doc["value"] += sum([e["value"] for e in g["emissions"]])
                    if g["gas_type"]["name"] == "OTHER":
                        other["value"] += sum([e["value"] for e in g["emissions"]])

            gases = [co2, ch4, n2o, co, doc, other]

            INCREASES = _("increases")
            DECREASES = _("decreases")

            sorted_gases = sorted(gases, key=lambda x: (abs(x["value"]) and x["value"] != 0), reverse=True)
            highest_gas = sorted_gases[0]
            second_highest_gas = sorted_gases[1]
            third_highest_gas = sorted_gases[2]

            project_primary_ghg = highest_gas["name"]
            project_primary_ghg_emissions = highest_gas["value"]
            project_primary_ghg_direction = INCREASES if project_primary_ghg_emissions >= 0 else DECREASES

            project_secondary_ghg = second_highest_gas["name"]
            project_secondary_ghg_emissions = second_highest_gas["value"]
            project_secondary_ghg_direction = INCREASES if project_secondary_ghg_emissions >= 0 else DECREASES

            project_tertiary_ghg = third_highest_gas["name"]
            project_tertiary_ghg_emissions = third_highest_gas["value"]
            project_tertiary_ghg_direction = INCREASES if project_tertiary_ghg_emissions >= 0 else DECREASES

            activities = project.activities.all()

            processed_activities = []

            # Hectares: if with to without, with is counted as 0 and without as area
            livestock_heads = [{"name": lct.name, "value_w": 0, "value_wo": 0} for lct in api_models.LivestockCategoryType.objects.all()]

            small_fishery_types = [{"name": ft.name, "value_w": 0, "value_wo": 0} for ft in api_models.FisheryType.objects.all()]
            large_fishery_data = {"name": "Large Fisheries", "value_w": 0, "value_wo": 0}
            aquaculture_data = {"name": "Aquaculture", "value_w": 0, "value_wo": 0}
            land_types = [{"name": lt.name, "value_w": 0, "value_wo": 0} for lt in api_models.ModuleType.objects.filter(is_luc=True).all()]

            for a in total_data["activities"]:
                db_activity: api_models.Activity = activities.get(name=a["name"])
                mlist = a["modules"]
                modules_by_highest_emissions = sorted(mlist, key=lambda x: x["results"]["balance"], reverse=total_balance > 0)

                db_activity.modules_emissions = [{"name": m["module_type"]["name"], "balance": m["results"]["balance"]} for m in modules_by_highest_emissions]

                sum_all_total_w = sum([m["results"]["total_w"] for m in mlist])
                sum_all_total_wo = sum([m["results"]["total_wo"] for m in mlist])
                sum_all_balance = sum_all_total_w - sum_all_total_wo

                db_activity.results = {"total_w": sum_all_total_w, "total_wo": sum_all_total_wo, "balance": sum_all_balance}

                main_impact = None
                secondary_impacts = []

                if db_activity.is_luc:
                    main_impact = _("hectares")
                elif db_activity.is_fishery:
                    main_impact = _("tonnes of catch")
                elif db_activity.is_livestock:
                    main_impact = _("livestock heads")

                if any([db_activity.is_energy, db_activity.is_storage, db_activity.is_transport, db_activity.is_processing]):
                    secondary_impacts.append(_("energy consumption"))
                if db_activity.is_packaging:
                    secondary_impacts.append(_("packaging material"))
                if db_activity.is_input:
                    secondary_impacts.append(_("agricultural inputs use"))

                secondary_impacts = ", ".join(secondary_impacts)

                db_activity.main_impact = main_impact
                if secondary_impacts:
                    db_activity.secondary_impacts = secondary_impacts

                for m in db_activity.modules:
                    if issubclass(m.__class__, api_models.Fishery):
                        if isinstance(m, api_models.SmallFishery):
                            m: api_models.SmallFishery
                            for ft in small_fishery_types:
                                if ft["name"] == m.fishery_type.name:
                                    ft["value_w"] += m.total_catch_yr_w
                                    ft["value_wo"] += m.total_catch_yr_wo
                        elif isinstance(m, api_models.LargeFishery):
                            m: api_models.LargeFishery
                            large_fishery_data["value_wo"] += m.total_catch_yr_wo
                            large_fishery_data["value_w"] += m.total_catch_yr_w

                    elif isinstance(m, api_models.Livestock):
                        m: api_models.Livestock
                        for lh in livestock_heads:
                            if lh["name"] == m.livestock_category_type.name:
                                lh["value_w"] += m.heads_number_w
                                lh["value_wo"] += m.heads_number_wo

                    elif isinstance(m, api_models.Aquaculture):
                        m: api_models.Aquaculture
                        aquaculture_data["value_w"] += m.annual_production_w
                        aquaculture_data["value_wo"] += m.annual_production_wo

                    elif issubclass(m.__class__, api_models.LandModule):
                        m: api_models.LandModule
                        for lt in land_types:
                            if lt["name"] == m.module_type.name:
                                if m.is_with() and not m.is_without():
                                    lt["value_w"] += m.area
                                elif m.is_without() and not m.is_with():
                                    lt["value_wo"] += m.area

                processed_activities.append(db_activity)

            processed_activities = sorted(processed_activities, key=lambda x: x.results["balance"], reverse=total_balance > 0)

            livestock_heads = list(filter(lambda x: x["value_w"] != 0 or x["value_wo"] != 0, livestock_heads))
            small_fishery_types = list(filter(lambda x: x["value_w"] != 0 or x["value_wo"] != 0, small_fishery_types))
            large_fishery_data = {} if large_fishery_data["value_w"] == 0 or large_fishery_data["value_wo"] == 0 else large_fishery_data
            aquaculture_data = {} if aquaculture_data["value_w"] == 0 or aquaculture_data["value_wo"] == 0 else aquaculture_data
            land_types = list(filter(lambda x: x["value_w"] != 0 or x["value_wo"] != 0, land_types))
            total_heads = sum([lh["value_w"] for lh in livestock_heads])
            total_tonnes_of_catch = sum([ft["value_w"] for ft in small_fishery_types]) + large_fishery_data.get("value_w", 0)

            activities_total = processed_activities

            def plot_with_without_balance_bar_chart_stacked_by_gas(data_w: list, data_wo: list):
                co2_w, ch4_w, n2o_w, co_w, doc_w, other_w = data_w
                co2_wo, ch4_wo, n2o_wo, co_wo, doc_wo, other_wo = data_wo

                # Prepare bar labels
                labels = ["With", "Without", "Balance"]

                # Build lists of values for each gas for "With", "Without", and the difference
                co2_vals = [
                    co2_w["value"],
                    co2_wo["value"],
                    co2_w["value"] - co2_wo["value"],
                ]
                ch4_vals = [
                    ch4_w["value"],
                    ch4_wo["value"],
                    ch4_w["value"] - ch4_wo["value"],
                ]
                n2o_vals = [
                    n2o_w["value"],
                    n2o_wo["value"],
                    n2o_w["value"] - n2o_wo["value"],
                ]
                co_vals = [
                    co_w["value"],
                    co_wo["value"],
                    co_w["value"] - co_wo["value"],
                ]
                doc_vals = [
                    doc_w["value"],
                    doc_wo["value"],
                    doc_w["value"] - doc_wo["value"],
                ]
                other_vals = [
                    other_w["value"],
                    other_wo["value"],
                    other_w["value"] - other_wo["value"],
                ]

                # Stack them in an array for plotting
                data_arrays = np.array([co2_vals, ch4_vals, n2o_vals, co_vals, doc_vals, other_vals])
                # Each row is a gas, each column is a bar (With, Without, Balance)

                x = np.arange(len(labels))
                width = 0.6

                fig, ax = plt.subplots(figsize=(6.5, 4))

                # We'll accumulate the bottom of each stack as we go
                bottom = np.zeros(len(labels))

                colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]
                names = ["CO2", "CH4", "N2O", "CO", "DOC", "OTHER"]

                for idx, row in enumerate(data_arrays):
                    ax.bar(x, row, width, bottom=bottom, color=colors[idx], label=names[idx])
                    bottom += row

                ax.set_xticks(x)
                ax.set_xticklabels(labels)
                ax.ticklabel_format(style="plain", axis="y", useOffset=False)
                ax.set_ylabel("Emissions (tonnes)")
                ax.set_title("")
                ax.legend()

                # Save to a BytesIO buffer
                buf = io.BytesIO()
                plt.savefig(buf, format="svg")
                buf.seek(0)

                # Encode as base64 for embedding in HTML
                chart_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                plt.close(fig)
                plt.clf()

                buf.close()
                return chart_base64

            def plot_project_balance_graph(project_emissions_w, project_emissions_wo, project_emissions_balance):
                # Create the figure and axis
                fig, ax = plt.subplots(figsize=(6.5, 4))

                # Data
                labels = ["With", "Without", "Balance"]
                emissions = [project_emissions_w, project_emissions_wo, project_emissions_balance]
                # Create horizontal bar chart
                ax.barh(labels, emissions, color=["#1f77b4", "#ff7f0e", "#2ca02c"])

                for i, v in enumerate(emissions):
                    ax.text(0 if v > 0 else v, i, f"{v:,.2f}", va="center")

                # Add legend
                ax.text(0.5, 1.1, "tCO2e", ha="center", va="bottom", transform=ax.transAxes)

                # Customize the chart
                ax.ticklabel_format(style="plain", axis="x", useOffset=False)
                ax.grid(True, axis="x", linestyle="--", alpha=0.7)

                # Save to a BytesIO buffer
                buf = io.BytesIO()
                plt.savefig(buf, format="svg")
                buf.seek(0)

                # Encode as base64 for embedding in HTML
                chart_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                plt.close(fig)
                plt.clf()

                buf.close()
                return chart_base64

            # Get faologo.eps from static files
            try:
                faologo = open(os.path.join(settings.BASE_DIR, "media", f"faologo_{lang}.svg"), "rb")
            except FileNotFoundError:
                faologo = open(os.path.join(settings.BASE_DIR, "media", "faologo.svg"), "rb")

            # Add it as base64 to the context
            faologo_base64 = base64.b64encode(faologo.read()).decode("utf-8")

            project_chart_base64 = plot_project_balance_graph(project_emissions_w, project_emissions_wo, project_emissions_balance)
            project_gases_chart_base64 = plot_with_without_balance_bar_chart_stacked_by_gas(gases_w, gases_wo)

            download_date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            context = {
                "project": project,
                "start_year_of_activities": project.start_year_of_activities,
                "implementation_years": project.implementation_years,
                "last_year_of_accounting": project.last_year_of_accounting,
                "total_project_years": (project.implementation_years + project.capitalization_years),
                "total_carbon_balance": project_emissions_balance,
                "project_emissions_w": project_emissions_w,
                "project_emissions_wo": project_emissions_wo,
                "project_emissions_balance": project_emissions_balance,
                "total_area": total_area,
                "total_heads": total_heads,
                "total_tonnes_of_catch": total_tonnes_of_catch,
                "soc": soc.value,
                "project_primary_ghg": project_primary_ghg,
                "project_primary_ghg_emissions": project_primary_ghg_emissions,
                "project_primary_ghg_direction": project_primary_ghg_direction,
                "project_secondary_ghg": project_secondary_ghg,
                "project_secondary_ghg_emissions": project_secondary_ghg_emissions,
                "project_secondary_ghg_direction": project_secondary_ghg_direction,
                "project_tertiary_ghg": project_tertiary_ghg,
                "project_tertiary_ghg_emissions": project_tertiary_ghg_emissions,
                "project_tertiary_ghg_direction": project_tertiary_ghg_direction,
                "activities": activities,
                "activities_total": activities_total,
                "project_chart_base64": project_chart_base64,
                "project_gases_chart_base64": project_gases_chart_base64,
                "faologo_base64": faologo_base64,
                "livestock_heads": livestock_heads,
                "small_fishery_types": small_fishery_types,
                "large_fishery_data": large_fishery_data,
                "aquaculture_data": aquaculture_data,
                "land_types": land_types,
                "download_date_time": download_date_time,
            }

            html = render(request, f"reports/{template_name}_{lang}.html", context).content.decode()

            # Generate PDF from HTML using WeasyPrint
            from weasyprint import HTML

            pdf = HTML(string=html).write_pdf()

            # Create the HTTP response with PDF content
            response = HttpResponse(pdf, content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{template_name}.pdf"'

            faologo.close()

            return response

        except Exception as e:
            return utils.ErrorResponse(f"Error generating PDF: {str(e)}", status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)


class PublicActivityViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows public activities to be viewed.
    """

    queryset = api_models.Activity.objects.filter(project__is_public=True)
    serializer_class = public_serializers.PublicActivitySerializerWithModules
    permission_classes = [AllowAny]
    pagination_class = DefaultPagination

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "project_id",
                openapi.IN_QUERY,
                description="Project ID to filter activities",
                type=openapi.TYPE_INTEGER,
            )
        ],
        responses={
            400: "activity_id not provided",
            403: "Selected user does not have permission to view activities in the project",
            200: public_serializers.PublicActivitySerializer(many=True),
        },
    )
    def list(self, request):
        """
        Get all activities for a given project, by filtering against a `project_id` query parameter in the URL.
        """
        log.info("ActivityViewSet.list")
        project_id = utils.get_query_param_or_validation_error(self.request, "project_id")
        is_summary = request.query_params.get("summary", False)

        get_object_or_404(self.queryset, pk=project_id, is_public=True)

        if is_summary:
            self.serializer_class = public_serializers.PublicActivitySummarySerializer

        def process_activity(activity):
            activity_dict = self.serializer_class(activity).data
            return activity_dict

        activities_list = api_models.Activity.objects.filter(project__id=project_id)

        paginator = DefaultPagination()
        page = paginator.paginate_queryset(activities_list, request)
        if page is not None:
            with ThreadPoolExecutor() as executor:
                response = list(executor.map(process_activity, page))
            return paginator.get_paginated_response(response)

        return Response(data=self.serializer_class(activities_list, many=True).data, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def modules(self, request, pk=None):
        """
        Lists the modules of a given activity.
        """

        activity = get_object_or_404(self.queryset, pk=pk)

        modules = get_modules(activity, serialized=True)

        paginator = DefaultPagination()
        page = paginator.paginate_queryset(modules, request)
        if page is not None:
            return paginator.get_paginated_response(page)

        return Response(data=modules, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "cached",
                openapi.IN_QUERY,
                description="Return cached results",
                type=openapi.TYPE_BOOLEAN,
            )
        ],
        responses={400: "Bad request", 403: "Selected user does not have permission to view activity results", 200: api_serializers.ActivityResultSerializer},
    )
    def results(self, request, pk=None):
        """
        Calculates and returns total emissions for each module in the activity.
        """

        activity = get_object_or_404(self.queryset, pk=pk)

        response = {**api_serializers.ActivityResultSerializer(activity).data}

        modules = []
        # TODO: Make a serializer for this
        for module in activity.modules:
            if not module or (module.status and module.status.name_en != "READY"):
                continue

            module_dict = public_serializers.get_public_module_serializer(module.__class__)(module).data

            try:
                viewset = generic_public_module_viewset(module.__class__).results(self, request, pk=module.pk)
                module_dict[labels.RESULTS] = viewset.data

            except Exception as e:
                log.error("Error calculating result in ActivityViewSet.results", e)
                module_dict[labels.RESULTS] = utils.error(str(e))

            modules.append(module_dict)

        response["modules"] = modules

        return Response(response)


def generic_public_module_viewset(model: api_models.Module):
    class GenericModuleViewSet(viewsets.ReadOnlyModelViewSet):
        queryset = model.objects.all()
        serializer_class = public_serializers.get_public_module_serializer(model)
        permission_classes = [AllowAny]

        def get_queryset(self):
            module_type = api_models.ModuleType.objects.get(class_name=model.__name__)

            if module_type.is_submodule:
                return model.objects.filter(parent__activity__project__is_public=True).all()
            else:
                return model.objects.filter(activity__project__is_public=True).all()

        @swagger_auto_schema(
            manual_parameters=[
                openapi.Parameter("activity", openapi.IN_QUERY, description="Activity ID to filter modules", type=openapi.TYPE_INTEGER),
                openapi.Parameter("module_type", openapi.IN_QUERY, description="Module type to filter modules", type=openapi.TYPE_STRING),
                openapi.Parameter("page_size", openapi.IN_QUERY, description="Number of items per page", type=openapi.TYPE_INTEGER),
                openapi.Parameter("page", openapi.IN_QUERY, description="Page number", type=openapi.TYPE_INTEGER),
            ],
            responses={400: "Bad request", 403: "Selected user does not have permission to view the module", 200: public_serializers.get_public_module_serializer(model)},
        )
        def list(self, request):
            """
            Lists the module(s) of a given activity
            by filtering against an `activity_id` query parameter in the URL or
            by filtering against the 'module_type' query parameter in the URL.
            """

            activity_id = utils.get_query_param_or_validation_error(self.request, "activity")
            module_type = api_models.ModuleType.objects.get(class_name=model.__name__)

            if module_type.is_submodule:
                modules = self.queryset.filter(parent__activity__id=activity_id).all()
            else:
                modules = self.queryset.filter(activity__id=activity_id).all()

            data = []

            for i, module in enumerate(modules):
                serializer = public_serializers.get_public_module_serializer(model)(instance=module, context={"request": request})
                data.append({**serializer.data})

            return Response(data)

        @action(detail=True, methods=["get"], url_path="results")
        @swagger_auto_schema(
            manual_parameters=[
                openapi.Parameter(
                    "aggregate",
                    openapi.IN_QUERY,
                    description="Aggregate results by",
                    type=openapi.TYPE_STRING,
                    enum=[api_serializers.BreakdownTypes.TOTAL.value, api_serializers.BreakdownTypes.ACTIVITY.value, api_serializers.BreakdownTypes.GAS.value, api_serializers.BreakdownTypes.ACTIVITY_GAS.value],
                ),
                openapi.Parameter("cached", openapi.IN_QUERY, description="Use cached results", type=openapi.TYPE_BOOLEAN),
            ],
            responses={400: "Bad request", 403: "Selected user does not have permission to view module results", 200: api_serializers.DynamicResultSerializer},
        )
        def results(self, request, pk=None):
            """
            Calculates and returns total emissions for a single module.
            """
            log.debug(f"START GenericModuleViewSet.results for module {model} {pk}")
            module: api_models.Module | api_models.Submodule = get_object_or_404(self.queryset, pk=pk)
            activity = module.get_activity()

            serializer = public_serializers.get_public_module_serializer(model)(data={"activity": activity.pk}, partial=True, instance=module, context={"request": request})
            serializer.is_valid(raise_exception=True)

            if module.module_type.class_name == api_models.LandUseChange.__name__:
                module: api_models.LandUseChange

                if not all(m.is_ready() for m in module.get_modules()):
                    return utils.ErrorResponse("Not all modules are ready. Land Use Change module cannot be calculated.")
            else:
                if not module.is_ready():
                    log.error(f"Module {module.module_type} is not ready. Cannot calculate result.")
                    return utils.ErrorResponse("Module is not ready. Cannot calculate result.")

            try:
                aggregate_by = api_serializers.BreakdownTypes(request.query_params.get("aggregate", api_serializers.BreakdownTypes.TOTAL))
                module_results = module.get_cached_results(by=aggregate_by)
                use_cached_results = request.query_params.get("cached", "true") == "true"

                if module_results is None or not use_cached_results:
                    log.debug(f"Cache is invalid. Calculating results for module {module.id}")
                    total, by_activity, by_gas, by_activity_gas = calculators.CalculatorFactory().calculate_result(module)

                    results_total = api_serializers.DynamicResultFactory.create(activity, total, aggregate_by=api_serializers.BreakdownTypes.TOTAL).data
                    results_by_activity = api_serializers.DynamicResultFactory.create(activity, by_activity, aggregate_by=api_serializers.BreakdownTypes.ACTIVITY).data
                    results_by_gas = api_serializers.DynamicResultFactory.create(activity, by_gas, aggregate_by=api_serializers.BreakdownTypes.GAS).data
                    results_by_activity_gas = api_serializers.DynamicResultFactory.create(activity, by_activity_gas, aggregate_by=api_serializers.BreakdownTypes.ACTIVITY_GAS).data

                    module_results = results_total if aggregate_by == api_serializers.BreakdownTypes.TOTAL else results_by_activity if aggregate_by == api_serializers.BreakdownTypes.ACTIVITY else results_by_gas if aggregate_by == api_serializers.BreakdownTypes.GAS else results_by_activity_gas
                    module.cache_results(results_total, results_by_activity, results_by_gas, results_by_activity_gas)

                serializer = api_serializers.DynamicResultSerializer(module_results, aggregate_by=aggregate_by)
                serialized_data = serializer.data

                return Response(serialized_data)

            except Exception as e:
                log.error("Error calculating result in GenericModuleViewSet.results", e)
                return utils.ErrorResponse(str(e))

        @action(detail=True, methods=["get"], url_path="defaults")
        def defaults(self, request, pk=None):
            """
            Returns the default values for a module.

            ex. GET /annual-croplands/1/defaults/
            """

            module: api_models.Module | api_models.Submodule = get_object_or_404(self.queryset, pk=pk)

            serializer = public_serializers.get_public_module_serializer(model)(data={}, instance=module, partial=True, context={"request": request})
            serializer.is_valid(raise_exception=True)
            serializer.save()

            try:
                defaults: types.SimpleNamespace = api_defaults.DefaultsFactory.get_defaults(module, calculate=True)

                if isinstance(defaults, dict):
                    defaults = types.SimpleNamespace(**defaults)

                return Response(defaults.__dict__)
            except Exception as e:
                return utils.ErrorResponse(str(e))

        @action(detail=True, methods=["get"])
        @swagger_auto_schema(responses={400: "Bad request", 403: "Selected user does not have permission to view module definitions", 200: "Definitions"})
        def definitions(self, request, pk=None):
            """
            Returns the definitions for a module.
            """

            module: api_models.Module | api_models.Submodule = get_object_or_404(self.queryset, pk=pk)

            try:
                definitions = utils.get_entity_definitions(module.module_type.class_name)
                return Response(definitions)
            except Exception as e:
                return utils.ErrorResponse(str(e))

    return GenericModuleViewSet
