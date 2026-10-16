"""Accepting project invitations.

Both accept paths (the in-app status change and the emailed token link) go through
accept_invitation so that accepting is idempotent and a (user, project) pair never
gets a second membership.
"""
from django.db import transaction
from django.utils import timezone

from api.models import InvitationStatusType, ProjectInvitation, ProjectMembership
from api.utilities import InvitationStatus


class InvitationNotAcceptableError(Exception):
    """The invitation is not pending or its token has expired."""


@transaction.atomic
def accept_invitation(invitation: ProjectInvitation) -> ProjectMembership:
    """Mark a pending invitation accepted and grant its role on the project.

    An existing member gets the invited role instead of a second membership, except the
    project owner, whose role is left alone so the project never loses its owning Admin.

    Raises:
        InvitationNotAcceptableError: if the invitation is not pending or has expired.
    """
    # Row lock: two concurrent accepts of the same link must not both see "pending".
    invitation = ProjectInvitation.objects.select_for_update(of=("self",)).select_related("project", "status").get(pk=invitation.pk)

    if invitation.status.name_en != InvitationStatus.PENDING.value:
        raise InvitationNotAcceptableError(f"This invitation has already been {invitation.status.name_en}.")
    if invitation.token_expiry and invitation.token_expiry < timezone.now():
        raise InvitationNotAcceptableError("This invitation has expired.")

    invitation.status = InvitationStatusType.objects.get(name_en=InvitationStatus.ACCEPTED.value)
    invitation.save()

    membership, created = ProjectMembership.objects.get_or_create(
        user_id=invitation.user_id, project_id=invitation.project_id, defaults={"group_id": invitation.group_id}
    )
    if not created and membership.group_id != invitation.group_id and invitation.user_id != invitation.project.owner_id:
        membership.group_id = invitation.group_id
        membership.save(update_fields=["group"])

    return membership
