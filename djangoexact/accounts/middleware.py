from django.http import JsonResponse
from firebase_admin import auth


class FirebaseAuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # If it's login or register or token refresh endpoint, skip authentication
        if request.path in ["/api/accounts/register/", "/api/accounts/login/"]:
            response = self.get_response(request)
            return response

        if "/admin" in request.path:
            response = self.get_response(request)
            return response

        authorization_header = request.META.get("HTTP_AUTHORIZATION")

        if not authorization_header:
            return JsonResponse({"error": "No Authorization header provided."}, status=401)

        id_token = authorization_header.split(" ")[1]

        try:
            decoded_token = auth.verify_id_token(id_token)
            request.user = decoded_token
        except ValueError:
            return JsonResponse({"error": "Invalid token."}, status=401)

        response = self.get_response(request)

        return response
