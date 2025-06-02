import os
from dotenv import load_dotenv, find_dotenv

dotenv_path = find_dotenv()
print("Using .env file at:", dotenv_path)
load_dotenv(dotenv_path)

print("DB_NAME:", os.getenv("DB_NAME"))
print("MONGO_URI:", os.getenv("MONGO_URI"))
