from functools import wraps

from django.http import HttpResponseForbidden

from api.models import Activity, Project, UserProjectGroup


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
                    can_access = project.owner == request.user
                case "activity":
                    activity = Activity.objects.get(pk=kwargs["pk"], project__user=request.user)
                    can_access = activity.project.owner == request.user
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


"""membership: UserProjectGroup = project.members.filter(user=self.request.user).first()
can_view = membership and membership.group.permissions.filter(codename="view_project").exists()
"""


def can_access_project(func):
    @wraps(func)
    def wrapper(viewset, *args, **kwargs):
        request = viewset.request
        if not request.user.is_authenticated:
            return HttpResponseForbidden("User is not authenticated")

        project = Project.objects.get(pk=kwargs["pk"])
        membership: UserProjectGroup = project.members.filter(user=request.user).first()
        can_access = membership and membership.group.permissions.filter(codename="view_project").exists()

        if can_access:
            return func(viewset, *args, **kwargs)

        return HttpResponseForbidden("You don't have permission to access this resource")

    return wrapper
