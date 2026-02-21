
from google.protobuf.descriptor_pb2 import FieldDescriptorProto
from google.protobuf.internal.enum_type_wrapper import EnumTypeWrapper

print(f"Type of FieldDescriptorProto.Type: {type(FieldDescriptorProto.Type)}")
print(f"Is instance of EnumTypeWrapper: {isinstance(FieldDescriptorProto.Type, EnumTypeWrapper)}")

try:
    x = FieldDescriptorProto.Type | None
    print(f"Result: {x}")
except TypeError as e:
    print(f"Error: {e}")
except Exception as e:
    print(f"Other Error: {e}")
