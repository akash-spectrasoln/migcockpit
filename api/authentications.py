from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed


class JWTCookieAuthentication(JWTAuthentication):
    """
    Custom JWT authentication class that reads the JWT token from HttpOnly cookies only.
    """
    def authenticate(self, request):
        # Get token from cookie
        access_token = request.COOKIES.get('access_token')
        
        if not access_token:
            return None
        
        try:
            # Validate the token
            validated_token = self.get_validated_token(access_token)
            # Get the user from the validated token
            user = self.get_user(validated_token)
            return (user, validated_token)
        except Exception as e:
            raise AuthenticationFailed(f'Invalid or expired token: {str(e)}')