"""
    Generic exceptions for the Greenhouse APIs
"""


class HarvestException(Exception):
    pass


class InvalidAPIVersion(HarvestException):
    pass


class InvalidAPICallError(HarvestException):
    pass


class EndpointNotFound(HarvestException):
    pass


class HarvestHTTPException(HarvestException):
    pass


class HarvestObjectNotFoundError(HarvestHTTPException):
    pass


class HarvestValidationError(HarvestHTTPException):
    pass


class HarvestUnauthorizedError(HarvestHTTPException):
    pass


class HarvestForbiddenError(HarvestHTTPException):
    pass


class HarvestRateLimitError(HarvestHTTPException):
    pass
