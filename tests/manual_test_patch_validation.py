
from agents.fix_proposal import validate_patch_on_copy


original = (
    "await page.locator('#login-btn').click();\n"
)

valid_patch = (
    "--- a/login.spec.ts\n"
    "+++ b/login.spec.ts\n"
    "@@ -1 +1 @@\n"
    "-await page.locator('#login-btn').click();\n"
    "+await page.getByRole('button', "
    "{ name: 'Login' }).click();\n"
)

invalid_patch = valid_patch.replace(
    "@@ -1 +1 @@",
    "@@ -1,2 +1,2 @@",
)

print("Original:", repr(original))
print("Patch:", repr(valid_patch))

removed_line = valid_patch.splitlines()[3][1:]
original_line = original.splitlines()[0]

print("Lines Match:", original_line == removed_line)

validate_patch_on_copy(
    valid_patch,
    original,
    "login.spec.ts",
)

print("Valid patch: PASSED")

try:
    validate_patch_on_copy(
        invalid_patch,
        original,
        "login.spec.ts",
    )
except ValueError:
    print("Invalid patch: REJECTED")
else:
    raise AssertionError(
        "Invalid patch was accepted!"
    )

print("ALL PATCH VALIDATION TESTS PASSED")
