from rest_framework import generics
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from django.db.models import Model
from .serializers import get_model_serializer
import django_filters


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

    return GenericViewSet
