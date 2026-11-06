from app.db.database import SessionLocal
from app.services.fter_template_service import (
    create_default_fter_template,
)


def main():

    db = SessionLocal()

    try:

        template = create_default_fter_template(db)

        print("FTER template ready.")
        print(f"Template ID: {template.id}")
        print(f"Template: {template.template_name}")
        print(f"Version: {template.version}")

    finally:

        db.close()


if __name__ == "__main__":
    main()