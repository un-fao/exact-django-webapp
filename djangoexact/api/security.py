import api.utilities as utils
import logging
from rest_framework import status as http_status


def check_permission(permission, user, project):
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
    is_project_admin = user.is_superuser or project.members.filter(user=user, group__name="Admin").exists()
    if not is_project_admin:
        logging.error("Selected user does not have project-admin permission for this project")
        return utils.ErrorResponse("Selected user does not have project-admin permission for this project", status=http_status.HTTP_403_FORBIDDEN)
    return None
