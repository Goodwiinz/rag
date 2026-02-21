
import sys
try:
    from google.protobuf.internal.enum_type_wrapper import EnumTypeWrapper
    print("EnumTypeWrapper found")

    # Create a dummy protobuf-like enum
    class MyProtoEnum(metaclass=EnumTypeWrapper):
        DESCRIPTOR = None

    try:
        x = MyProtoEnum | None
        print("MyProtoEnum | None works")
    except TypeError as e:
        print(f"MyProtoEnum | None failed: {e}")

except ImportError:
    print("EnumTypeWrapper not found")

import enum
class MyEnum(enum.Enum):
    A = 1

try:
    x = MyEnum | None
    print("MyEnum | None works")
except TypeError as e:
    print(f"MyEnum | None failed: {e}")
