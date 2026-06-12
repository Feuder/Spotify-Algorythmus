import json

from app.db import SessionLocal
from app.services.sync import source_probe


def main() -> None:
    with SessionLocal() as db:
        print(json.dumps(source_probe(db, 100), indent=2))


if __name__ == "__main__":
    main()
