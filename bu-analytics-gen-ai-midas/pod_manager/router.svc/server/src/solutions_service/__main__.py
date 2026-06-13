"""Allow ``python -m solutions_service`` when the package is on ``PYTHONPATH``."""

from solutions_service.main import run

if __name__ == "__main__":
    run()
