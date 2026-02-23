"""
platform_sdk.tier1_runtime.validate
──────────────────────────────────────
Input/schema validation via Pydantic v2. Raises platform ValidationError
(not raw Pydantic errors) so API responses are always consistent.
"""
from __future__ import annotations

from typing import Any, Type, TypeVar

from pydantic import BaseModel, ValidationError as PydanticValidationError

T = TypeVar("T", bound=BaseModel)


def validate_input(model: Type[T], data: Any) -> T:
    """
    Validate raw data against a Pydantic model.
    Raises platform_sdk ValidationError (not Pydantic's) on failure.

    Usage:
        class CreateUser(BaseModel):
            email: str
            name: str

        user = validate_input(CreateUser, request.json())
    """
    try:
        if isinstance(data, dict):
            return model.model_validate(data)
        return model.model_validate(data)
    except PydanticValidationError as exc:
        from platform_sdk.tier0_core.errors import ValidationError

        fields = {
            ".".join(str(loc) for loc in err["loc"]): err["msg"]
            for err in exc.errors()
        }
        raise ValidationError(
            code="validation_error",
            user_message="Request validation failed.",
            fields=fields,
        ) from exc


def validate_response(model: Type[T], data: Any) -> T:
    """
    Validate outgoing response data. Useful for enforcing response contracts.
    Raises ValidationError if the response shape is wrong.
    """
    return validate_input(model, data)


__sdk_export__ = {
    "surface": "service",
    "exports": ["validate_input"],
    "description": "Pydantic v2 input validation with contract enforcement",
    "tier": "tier1_runtime",
    "module": "validate",
}
