
from enum import Enum
from typing import Optional

class UserRole(Enum):
    ADMIN = "admin"
    USER = "user"

try:
    x = UserRole | None
    print("UserRole | None works")
except TypeError as e:
    print(f"UserRole | None failed: {e}")

try:
    from typing import Union
    x = Union[UserRole, None]
    print("Union[UserRole, None] works")
except TypeError as e:
    print(f"Union[UserRole, None] failed: {e}")
