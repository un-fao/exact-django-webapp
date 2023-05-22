from functools import wraps
from django.http import HttpResponseForbidden
from api.models import Project, Activity

def can_access(resource: str):
    def decorator_func(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseForbidden("User is not authenticated")

            can_access = False

            match resource:
                case "project":
                    project = Project.objects.get(pk=kwargs["pk"], user=request.user)
                    can_access = project.user == request.user
                case "activity":
                    activity = Activity.objects.get(pk=kwargs["pk"], project__user=request.user)
                    can_access = activity.project.user == request.user
                case "module":
                    module = getattr(func, "model").objects.get(pk=kwargs["pk"], activity__project__user=request.user)
                    can_access = module.activity.project.user == request.user
                case _:
                    raise Exception(f"Invalid resource in @can_access decorator: {resource}")

            if can_access:
                return func(request, *args, **kwargs)
            
            return HttpResponseForbidden("You don't have permission to access this resource")
        return wrapper
    return decorator_func