import django_filters as filters


def get_model_filter(model_arg):
    class GenericModelFilter(filters.FilterSet):
        class Meta:
            model = model_arg
            fields = "__all__"

    try:
        return globals()[f"{model_arg.__name__}Filter"]
    except KeyError:
        return GenericModelFilter
