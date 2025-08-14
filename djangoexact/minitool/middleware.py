from django.db import connections


class DatabaseConnectionMiddleware:
    """
    Middleware to ensure database connections are properly closed after each request.
    This helps prevent connection pool exhaustion.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Process request
        response = self.get_response(request)

        # Close database connections after response
        connections.close_all()

        return response
