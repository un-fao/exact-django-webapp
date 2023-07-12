from rest_framework import generics
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from django.db.models import Model
from .serializers import get_model_serializer


class AuthenticatedViewSet:
    permission_classes = [IsAuthenticated]


def generic_viewset(model: Model):
    class GenericViewSet(viewsets.ModelViewSet, AuthenticatedViewSet):
        queryset = model.objects.all()
        serializer_class = get_model_serializer(model)

    return GenericViewSet
