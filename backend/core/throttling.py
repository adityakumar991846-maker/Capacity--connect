"""
Custom rate throttles for sensitive authentication and public verification endpoints.
"""

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class AuthRateThrottle(AnonRateThrottle):
    """
    Throttles sensitive public auth requests (registration, login) by IP.
    """
    scope = 'auth'


class VerifyRateThrottle(AnonRateThrottle):
    """
    Throttles public credential verification requests by IP.
    """
    scope = 'verify'
