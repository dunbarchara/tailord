# Backward-compat shim — all logic moved to letter_generator.py.
# Callers should migrate to: from app.services.letter_generator import generate_letter
from app.services.letter_generator import generate_letter as generate_tailoring

__all__ = ["generate_tailoring"]
