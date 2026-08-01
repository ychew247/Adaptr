import os
import psycopg2


def main():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    try:
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT now();")
                result = cur.fetchone()
                print("Connected successfully.")
                print("Database time:", result[0])

    except psycopg2.Error as error:
        print("Connection failed:")
        print(error)


if __name__ == "__main__":
    main()
