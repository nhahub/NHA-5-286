"""
Purpose: Deterministic pre-classification step that validates the Analyzer agent's failure_type candidate and prevents guessing.
Owner: @Shema
Reads: failure_analysis (raw agent output dict)
Writes: failure_type state field (validated string)
Must not: guess a classification; unknown or malformed values must become ERROR, never a fallback class
"""

# VALID_FAILURE_CLASSES: frozenset[str] = frozenset({"Test", "Application", "Environment", "Infrastructure"})
# VALID_SUBTYPES: frozenset[str] = frozenset({"SELECTOR", "TIMING", "ASSERTION"})

# def validate_failure_class(candidate: str) -> str:
#     -> Returns candidate unchanged if it is in VALID_FAILURE_CLASSES
#     -> Returns "ERROR" for anything else; never guesses

# def validate_subtype(failure_type: str, subtype: str | None) -> str | None:
#     -> Returns subtype unchanged if failure_type == "Test" and subtype in VALID_SUBTYPES
#     -> Returns None if failure_type != "Test" (non-Test classes have no subtypes)
#     -> Returns None if subtype is not in VALID_SUBTYPES (malformed, not an error)

# def classify(analysis: dict) -> dict:
#     -> Runs validate_failure_class and validate_subtype; returns updated dict
#     -> Does not raise — sets failure_type to "ERROR" on bad input so the run still ends cleanly
