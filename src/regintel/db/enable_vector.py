
from sqlalchemy import text

from regintel.db.session import engine


def main():
    with engine.begin() as connection:
        connection.execute(
            text("CREATE EXTENSION IF NOT EXISTS vector")
        )

    print("pgvector extension enabled.")


if __name__ == "__main__":
    main()
