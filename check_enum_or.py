
from google.protobuf.internal.enum_type_wrapper import EnumTypeWrapper

# We can't easily instantiate EnumTypeWrapper without a valid C++ enum descriptor,
# but we can check if the class has __or__ method.

print(f"Has __or__: {hasattr(EnumTypeWrapper, '__or__')}")
