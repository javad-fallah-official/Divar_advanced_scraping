from dotenv import load_dotenv
import os

load_dotenv()

DB = {
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "database": os.getenv("DB_NAME"),
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", 5432)),
}

TARGET_URL = os.getenv("TARGET_URL", "https://divar.ir/s/tehran/motorcycles")
USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
MAX_SCROLLS = int(os.getenv("MAX_SCROLLS", 200))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 100))