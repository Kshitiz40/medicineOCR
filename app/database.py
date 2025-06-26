from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv
import os

load_dotenv()

class MongoDB:
    def __init__(self):
        self.client = None
        self.db = None
        self.collection = None
        
    def connect(self):
        try:
            self.client = MongoClient(os.getenv("MONGODB_ATLAS_URI"))
            self.db = self.client[os.getenv("DATABASE_NAME")]
            self.collection = self.db[os.getenv("COLLECTION_NAME")]
            # Test the connection
            self.client.admin.command('ping')
            print("Successfully connected to MongoDB Atlas!")
        except ConnectionFailure as e:
            print(f"Could not connect to MongoDB Atlas: {e}")
            raise

    def close(self):
        if self.client:
            self.client.close()

db = MongoDB()