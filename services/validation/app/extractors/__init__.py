"""Document-specific field extractors."""

from app.extractors.base_extractor import BaseExtractor
from app.extractors.passport_extractor import PassportExtractor
from app.extractors.driving_license_extractor import DrivingLicenseExtractor
from app.extractors.visa_extractor import VisaExtractor
from app.extractors.national_id_extractor import NationalIdExtractor
from app.extractors.permit_extractor import PermitExtractor

_EXTRACTORS = {
    "passport": PassportExtractor,
    "driving_license": DrivingLicenseExtractor,
    "visa": VisaExtractor,
    "national_id": NationalIdExtractor,
    "permit": PermitExtractor,
}


def get_extractor(document_type: str) -> BaseExtractor:
    """Return an extractor instance for the given document type."""
    cls = _EXTRACTORS.get(document_type)
    if cls is None:
        raise ValueError(f"No extractor registered for document_type={document_type}")
    return cls()
