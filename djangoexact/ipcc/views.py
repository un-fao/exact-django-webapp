from .serializers import GeneralSerializer
from rest_framework import generics

# Create your views here.
class GenericAPIView(generics.ListAPIView):
    def dispatch(self, request, *args, **kwargs):
        self.model = kwargs.pop('model')
        self.queryset = self.model.objects.all()
        serializer = GeneralSerializer
        serializer.Meta.model = self.model
        self.serializer_class = serializer
        return super().dispatch(request, *args, **kwargs)