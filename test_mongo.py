import certifi
from pymongo import MongoClient

MONGODB_URI = "mongodb+srv://agiuser:agi123@cluster0.1wg00ra.mongodb.net/agi_career?retryWrites=true&w=majority&appName=Cluster0"

try:
    print("Testing MongoDB connection...")
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=8000, tls=True, tlsCAFile=certifi.where(), tlsAllowInvalidCertificates=False)
    client.admin.command('ping')
    print("Connected successfully!")
except Exception as e:
    print(f"Connection failed: {e}")
