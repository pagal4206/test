from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError


class MongoStore:
    def __init__(self, mongo_uri: str, db_name: str) -> None:
        self._mongo_uri = mongo_uri
        self._db_name = db_name
        self.client = MongoClient(self._mongo_uri, serverSelectionTimeoutMS=5000)
        self.db = None
        self.users_collection: Collection
        self.groups_collection: Collection

    def connect(self) -> None:
        try:
            self.client.admin.command("ping")
        except PyMongoError as exc:
            raise RuntimeError(f"MongoDB connection failed: {exc}") from exc

        self.db = self.client[self._db_name]
        self.users_collection = self.db["users"]
        self.groups_collection = self.db["groups"]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self.users_collection.create_index("user_id", unique=True)
        self.users_collection.create_index("active")

        self.groups_collection.create_index("group_id", unique=True)
        self.groups_collection.create_index("active")
        self.groups_collection.create_index("force_sub.enabled")

