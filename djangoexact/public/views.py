from rest_framework import generics
import api.models as models
import api.views as views
import public.serializers as serializers

# Create your views here.


class PublicProjectRetrieveView(generics.RetrieveAPIView):
    """
    View to retrieve a public project.
    """

    queryset = models.Project.objects.all()
    serializer_class = serializers.PublicProjectSerializer
    lookup_field = "id"

    def get_queryset(self):
        """
        Override the get_queryset method to filter projects by public status.
        """
        return self.queryset.filter(is_public=True)

    def get(self, request, id):
        """
        Override the get method to retrieve a public project.
        """
        project = self.get_object()
        serializer = self.get_serializer(project)
        return views.Response(serializer.data)
