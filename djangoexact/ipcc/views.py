import django_filters
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Model
from rest_framework import generics, viewsets
from rest_framework.permissions import IsAuthenticated

from .serializers import get_model_serializer


class AuthenticatedViewSet:
    permission_classes = [IsAuthenticated]


def generic_viewset(_model: Model):
    class GenericFilterSet(django_filters.FilterSet):
        class Meta:
            model = _model
            fields = "__all__"

    class GenericViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
        queryset = _model.objects.all()
        serializer_class = get_model_serializer(_model)
        filter_backends = [django_filters.rest_framework.DjangoFilterBackend]
        filterset_class = GenericFilterSet

        def get_queryset(self):

            # If list operation, filter out inactive objects, unless ?filter_inactive=true
            if self.action == "list" and not self.request.query_params.get("filter_inactive"):
                try:
                    is_active_field = self.queryset.model._meta.get_field("is_active")
                    return self.queryset.filter(is_active=True)
                except FieldDoesNotExist:
                    return super().get_queryset()

            return super().get_queryset()

    return GenericViewSet
