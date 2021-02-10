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
    def __init__(self, *args, errors=list):
        super().__init__(*args)
        self.errors = errors


class HarvestUnauthorizedError(HarvestHTTPException):
    pass


class HarvestForbiddenError(HarvestHTTPException):
    pass


class HarvestRateLimitError(HarvestHTTPException):
    pass


class HarvestServerError(HarvestHTTPException):
    pass
