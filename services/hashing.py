from argon2 import PasswordHasher


class HashService:
    _hasher: PasswordHasher

    @classmethod
    def setup(cls, time_cost: int, memory_cost: int, parallelism: int):
        cls._hasher = PasswordHasher(
            time_cost=time_cost, memory_cost=memory_cost,
            parallelism=parallelism
        )

    @classmethod
    def hash(cls, password: str) -> str:
        return cls._hasher.hash(password)

    @classmethod
    def verify(cls, password_hash: str, password: str) -> bool:
        return cls._hasher.verify(password_hash, password)
