from api.models import CustomUser as User
from rest_framework import generics
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.response import Response

from .serializers import RegisterSerializer, UserSerializer


@authentication_classes([])
@permission_classes([])
class RegisterView(generics.GenericAPIView):
    serializer_class = RegisterSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user: User = serializer.save()
        user.is_active = False
        user.save()

        return Response(
            {
                "user": UserSerializer(user, context=self.get_serializer_context()).data,
                "message": "User Created Successfully.  Now perform Login to get your token",
            }
        )
