import os
import argparse
import shutil
import psycopg2


def get_conn():
    host = os.environ.get("DB_HOST", "localhost")
    port = int(os.environ.get("DB_PORT", "5432"))
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "admin")
    name = os.environ.get("DB_NAME", "Divar")
    return psycopg2.connect(host=host, port=port, user=user, password=password, dbname=name)


def clean_db(drop: bool):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if drop:
                cur.execute("DROP TABLE IF EXISTS posts")
            else:
                cur.execute("TRUNCATE TABLE posts")
        conn.commit()
    finally:
        conn.close()


def count_rows() -> int:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM posts")
            return int(cur.fetchone()[0])
    except Exception:
        return 0
    finally:
        conn.close()


def remove_logs(keep: bool):
    if keep:
        return
    p = os.path.join("logs", "scrape.jsonl")
    if os.path.exists(p):
        os.remove(p)


def remove_out(keep: bool):
    if keep:
        return
    d = os.path.join("out")
    if os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)




def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", default="false", choices=["true", "false"])
    parser.add_argument("--drop", default="false", choices=["true", "false"])
    parser.add_argument("--keep-logs", default="false", choices=["true", "false"])
    parser.add_argument("--keep-out", default="false", choices=["true", "false"])
    args = parser.parse_args()

    proceed = args.yes == "true"
    drop = args.drop == "true"
    keep_logs = args.keep_logs == "true"
    keep_out = args.keep_out == "true"

    before = count_rows()
    print("DB rows before:", before)
    if not proceed:
        print("Pass --yes true to execute cleanup.")
        return

    clean_db(drop)
    remove_logs(keep_logs)
    remove_out(keep_out)
    after = count_rows()
    print("DB rows after:", after)
    print("Cleanup complete.")


if __name__ == "__main__":
    main()
