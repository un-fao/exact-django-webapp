import api.utilities as utils
import logging
from rest_framework import status as http_status


def not_authenticated():
    # Imported here: accounts.firebase imports api.models, which is still loading when
    # this module is first imported.
    from accounts.firebase import WWW_AUTHENTICATE

    response = utils.ErrorResponse("Authentication credentials were not provided.", status=http_status.HTTP_401_UNAUTHORIZED)
    response["WWW-Authenticate"] = WWW_AUTHENTICATE
    return response


def check_permission(permission, user, project):
    # 403 tells the client "signed in but not allowed"; an anonymous caller is not signed in.
    if not user.is_authenticated:
        return not_authenticated()
    if not utils.has_project_permission(permission, user, project):
        permission = permission.replace("_", " ")
        logging.error(f"Selected user does not have permission to {permission}")
        return utils.ErrorResponse(f"Selected user does not have permission to {permission}", status=http_status.HTTP_403_FORBIDDEN)
    return None


def check_project_admin(user, project):
    """Guard for project-admin-only actions.

    Superusers bypass every other project permission check. Everyone else must
    be a member of the project in the Admin group.
    """
    if not user.is_authenticated:
        return not_authenticated()
    is_project_admin = user.is_superuser or project.members.filter(user=user, group__name="Admin").exists()
    if not is_project_admin:
        logging.error("Selected user does not have project-admin permission for this project")
        return utils.ErrorResponse("Selected user does not have project-admin permission for this project", status=http_status.HTTP_403_FORBIDDEN)
    return None
