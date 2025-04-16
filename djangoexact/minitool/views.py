from django.shortcuts import render
from rest_framework import views, generics, viewsets, mixins, decorators
from rest_framework.response import Response
from rest_framework import status
import minitool.models as models
import minitool.serializers as serializers
from django_filters.rest_framework import DjangoFilterBackend
import django_filters
from django.db.models import JSONField
from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 10000


class EntryViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    class GenericFilterSet(django_filters.FilterSet):
        class Meta:
            model = models.Entry
            fields = "__all__"
            filter_overrides = {
                JSONField: {
                    "filter_class": django_filters.CharFilter,
                },
            }

    queryset = models.Entry.objects.all()
    serializer_class = serializers.EntrySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = GenericFilterSet

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        queryset = self.filter_queryset(queryset)
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = serializers.EntrySerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        serializer = serializers.EntrySerializer(queryset, many=True)
        return Response(serializer.data)


class StatisticsModuleTotalViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    class GenericFilterSet(django_filters.FilterSet):
        class Meta:
            model = models.StatisticsModuleTotal
            fields = "__all__"
            filter_overrides = {
                JSONField: {
                    "filter_class": django_filters.CharFilter,
                },
            }

    queryset = models.StatisticsModuleTotal.objects.all()
    serializer_class = serializers.StatisticsModuleTotalSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = GenericFilterSet

    @decorators.action(detail=False, methods=["get"])
    def aggregate(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        queryset = self.filter_queryset(queryset)

        by = request.query_params.get("by", None)

        queryset = queryset.filter(field=by)

        paginator = DefaultPagination()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = serializers.StatisticsModuleTotalSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        serializer = serializers.StatisticsModuleTotalSerializer(queryset, many=True)
        return Response(serializer.data)
