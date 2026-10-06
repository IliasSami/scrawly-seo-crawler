"""Tech-stack detection (fingerprinting) for auto-configuration."""
from sentinelseo.detect.fingerprint import (
    DetectionResult,
    detect_from_response,
    detect_stack,
)

__all__ = ["DetectionResult", "detect_from_response", "detect_stack"]
