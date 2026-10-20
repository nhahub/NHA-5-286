
from pathlib import Path
from tempfile import TemporaryDirectory

from agents.fix_proposal import read_failed_spec_code


project_root = Path(__file__).resolve().parents[1]
runs_dir = project_root / "runs"
runs_dir.mkdir(exist_ok=True)


# Create a temporary run for testing
with TemporaryDirectory(
    dir=runs_dir,
    prefix="p4_read_",
) as temp_dir:

    run_dir = Path(temp_dir)
    tests_dir = run_dir / "tests"
    tests_dir.mkdir()

    spec_file = tests_dir / "s2-invalid-login.spec.ts"

    original_code = (
        "await page.getByRole("
        "'button', { name: 'Sign in' }).click();\n"
    )

    spec_file.write_text(
        original_code,
        encoding="utf-8",
    )

    state = {
        "run_id": run_dir.name,
        "generated_test_files": [str(spec_file)],
        "execution_evidence": [
            {
                "scenario_name": "Invalid Login",
                "error_message": "Locator timed out",
            }
        ],
    }

    # TEST 1: Valid file
    code, filename = read_failed_spec_code(state)

    assert code == original_code
    assert filename == "s2-invalid-login.spec.ts"

    print("Valid spec reading: PASSED")

    # TEST 2: File outside the allowed tests folder
    outside_file = run_dir / spec_file.name
    outside_file.write_text(
        original_code,
        encoding="utf-8",
    )

    unsafe_state = {
        **state,
        "generated_test_files": [str(outside_file)],
    }

    try:
        read_failed_spec_code(unsafe_state)
    except ValueError:
        print("Unsafe path: REJECTED")
    else:
        raise AssertionError("Unsafe path was accepted!")

    # TEST 3: Missing file
    spec_file.unlink()

    try:
        read_failed_spec_code(state)
    except ValueError:
        print("Missing file: REJECTED")
    else:
        raise AssertionError("Missing file was accepted!")


print("ALL SPEC READER TESTS PASSED")
