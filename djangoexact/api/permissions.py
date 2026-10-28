from rest_framework.permissions import BasePermission, SAFE_METHODS
from django.shortcuts import get_object_or_404
from api.models import Project, Activity, Module


class IsPublicOrAuthenticated(BasePermission):
    """
    Custom permission to allow specific methods for public projects, activities, and modules.
    """

    def has_permission(self, request, view):
        # Check if the URL starts with "api/public"
        if request.path.startswith("/api/public"):
            # Handle Project
            if view.basename == "project":
                project_id = request.query_params.get("project_id") or view.kwargs.get("pk")
                if project_id:
                    project = get_object_or_404(Project, pk=project_id)
                    if project.is_public:
                        return request.method in SAFE_METHODS

            # Handle Activity
            if view.basename == "activities":
                activity_id = view.kwargs.get("pk")
                if activity_id:
                    activity = get_object_or_404(Activity, pk=activity_id)
                    if activity.project.is_public:
                        return request.method in SAFE_METHODS
                else:
                    project_id = request.query_params.get("project_id")
                    if project_id:
                        project = get_object_or_404(Project, pk=project_id)
                        if project.is_public:
                            return request.method in SAFE_METHODS

            # Handle Modules (generic_module_viewset)
            module_basenames = [
                "annualcropland",
                "perennialcropland",
                "grassland",
                "smallfishery",
                "largefishery",
                "aquaculture",
                "input",
                "irrigation",
                "setaside",
                "otherland",
                "coastalwetland",
                "floodedrice",
                "livestock",
                "forestmanagement",
                "waterbody",
                "settlement",
                "energy",
                "storage",
                "processing",
                "packaging",
                "transport",
                "inputentry",
                "irrigationsystem",
                "irrigationphase",
                "landusechange",
                "organicsoil",
                "floodedriceminorseason",
                "forestdisturbance",
                "building",
                "road",
                "otherinfrastructure",
                "electricity",
                "fuel",
                "energyentry",
                "storageentry",
                "processingentry",
                "packagingentry",
                "transportentry",
                "annualcroplandminorseason",
                "perennialcroplandminorseason",
            ]
            if view.basename in module_basenames:
                module_id = view.kwargs.get("pk")
                if module_id:
                    module = get_object_or_404(Module, pk=module_id)
                    if module.activity.project.is_public:
                        return request.method in SAFE_METHODS

        # Default to requiring authentication for other cases
        return request.user and request.user.is_authenticated
