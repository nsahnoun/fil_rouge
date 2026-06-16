from fastapi import HTTPException, status


class AppException(HTTPException):
    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=status_code, detail=detail)


class NotFoundException(AppException):
    def __init__(self, detail: str = "Ressource introuvable"):
        super().__init__(detail=detail, status_code=status.HTTP_404_NOT_FOUND)


class ForbiddenException(AppException):
    def __init__(self, detail: str = "Accès refusé"):
        super().__init__(detail=detail, status_code=status.HTTP_403_FORBIDDEN)


class UnauthorizedException(AppException):
    def __init__(self, detail: str = "Non authentifié"):
        super().__init__(detail=detail, status_code=status.HTTP_401_UNAUTHORIZED)


class ConflictException(AppException):
    def __init__(self, detail: str = "Conflit"):
        super().__init__(detail=detail, status_code=status.HTTP_409_CONFLICT)
