"""
Complete AMF3 encoder and decoder for Yu-Gi-Oh! BAM Pocket protocol.
Follows AMF3 specification (string/object/trait reference tables, sealed and dynamic traits,
arrays, bytearrays, doubles, integers, null/bool).

Protocol response classes and fields cited from decompiled AS3:
- GetVersionResponse [GetVersionResponse.as:6-20]
- PingResponse [PingResponse.as:6-19]
- GetTokenResponse [GetTokenResponse.as:6-17]
- LoginResponse [LoginResponse.as:6-15]
- GetPlayerSaveResponse [GetPlayerSaveResponse.as:7-16]
- AbstractException [AbstractException.as:3-16]
"""

import struct
import zlib
from typing import Any, Dict, List, Optional, Tuple

# AMF3 Type Markers
MARKER_UNDEFINED = 0x00
MARKER_NULL      = 0x01
MARKER_FALSE     = 0x02
MARKER_TRUE      = 0x03
MARKER_INTEGER   = 0x04
MARKER_DOUBLE    = 0x05
MARKER_STRING    = 0x06
MARKER_XML_DOC   = 0x07
MARKER_DATE      = 0x08
MARKER_ARRAY     = 0x09
MARKER_OBJECT    = 0x0A
MARKER_XML       = 0x0B
MARKER_BYTEARRAY = 0x0C


class AMF3Date(float):
    """Milliseconds since the Unix epoch, encoded as an AMF3 Date (AS3 Date fields such as
    GetServerTimeResponse.serverTime, GetLastSavedDateResponse.lastSavedDate)."""


class AMF3Object(dict):
    """Represents a typed or dynamic AMF3 Object."""
    def __init__(self, class_alias: str = "", **kwargs):
        super().__init__(**kwargs)
        self.class_alias = class_alias

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'AMF3Object' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "class_alias":
            super().__setattr__(name, value)
        else:
            self[name] = value

    def __repr__(self) -> str:
        return f"AMF3Object({self.class_alias!r}, {dict(self)!r})"


class TraitInfo:
    """AMF3 Object Traits Metadata."""
    def __init__(self, class_alias: str, is_externalizable: bool, is_dynamic: bool, sealed_prop_names: List[str]):
        self.class_alias = class_alias
        self.is_externalizable = is_externalizable
        self.is_dynamic = is_dynamic
        self.sealed_prop_names = sealed_prop_names


def encode_u29(n: int) -> bytes:
    """Encode an integer into AMF3 variable-length 29-bit integer (U29)."""
    n &= 0x1FFFFFFF
    if n < 0x80:
        return bytes([n])
    elif n < 0x4000:
        return bytes([(n >> 7) | 0x80, n & 0x7F])
    elif n < 0x200000:
        return bytes([(n >> 14) | 0x80, ((n >> 7) & 0x7F) | 0x80, n & 0x7F])
    else:
        return bytes([(n >> 22) | 0x80, ((n >> 15) & 0x7F) | 0x80, ((n >> 8) & 0x7F) | 0x80, n & 0xFF])


def decode_u29(data: bytes, offset: int) -> Tuple[int, int]:
    """Decode an unsigned U29 from data at offset. Returns (value, new_offset)."""
    b = data[offset]
    offset += 1
    if b < 0x80:
        return b, offset
    val = (b & 0x7F) << 7
    b = data[offset]
    offset += 1
    if b < 0x80:
        return val | b, offset
    val = (val | (b & 0x7F)) << 7
    b = data[offset]
    offset += 1
    if b < 0x80:
        return val | b, offset
    val = (val | (b & 0x7F)) << 8
    b = data[offset]
    offset += 1
    return val | b, offset


def decode_u29_signed(data: bytes, offset: int) -> Tuple[int, int]:
    """Decode a signed 29-bit integer from data at offset."""
    val, offset = decode_u29(data, offset)
    if val & 0x10000000:
        val -= 0x20000000
    return val, offset


class AMF3Decoder:
    """Full-featured AMF3 Binary Deserializer."""
    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0
        self.string_table: List[str] = []
        self.object_table: List[Any] = []
        self.traits_table: List[TraitInfo] = []

    def has_more(self) -> bool:
        return self.offset < len(self.data)

    def read_u29(self) -> int:
        val, self.offset = decode_u29(self.data, self.offset)
        return val

    def read_u29_signed(self) -> int:
        val, self.offset = decode_u29_signed(self.data, self.offset)
        return val

    def read_string_raw(self) -> str:
        """Reads an AMF3 string without type marker."""
        header = self.read_u29()
        if (header & 1) == 0:
            index = header >> 1
            if index >= len(self.string_table):
                raise ValueError(f"Invalid string reference index: {index}")
            return self.string_table[index]

        byte_len = header >> 1
        if byte_len == 0:
            return ""

        s = self.data[self.offset : self.offset + byte_len].decode('utf-8', errors='replace')
        self.offset += byte_len
        self.string_table.append(s)
        return s

    def decode_value(self) -> Any:
        """Decodes the next AMF3 value."""
        if self.offset >= len(self.data):
            return None

        marker = self.data[self.offset]
        self.offset += 1

        if marker == MARKER_UNDEFINED or marker == MARKER_NULL:
            return None
        elif marker == MARKER_FALSE:
            return False
        elif marker == MARKER_TRUE:
            return True
        elif marker == MARKER_INTEGER:
            return self.read_u29_signed()
        elif marker == MARKER_DOUBLE:
            val = struct.unpack(">d", self.data[self.offset : self.offset + 8])[0]
            self.offset += 8
            return val
        elif marker == MARKER_STRING:
            return self.read_string_raw()
        elif marker == MARKER_XML_DOC or marker == MARKER_XML:
            header = self.read_u29()
            if (header & 1) == 0:
                return self.object_table[header >> 1]
            byte_len = header >> 1
            xml_str = self.data[self.offset : self.offset + byte_len].decode('utf-8', errors='replace')
            self.offset += byte_len
            self.object_table.append(xml_str)
            return xml_str
        elif marker == MARKER_DATE:
            header = self.read_u29()
            if (header & 1) == 0:
                return self.object_table[header >> 1]
            ms = struct.unpack(">d", self.data[self.offset : self.offset + 8])[0]
            self.offset += 8
            self.object_table.append(ms)
            return ms
        elif marker == MARKER_ARRAY:
            header = self.read_u29()
            if (header & 1) == 0:
                return self.object_table[header >> 1]

            dense_count = header >> 1
            arr: List[Any] = []
            self.object_table.append(arr)

            # Associative keys until empty string
            while True:
                key = self.read_string_raw()
                if not key:
                    break
                val = self.decode_value()
                # associative properties can be ignored or stored

            # Dense elements
            for _ in range(dense_count):
                arr.append(self.decode_value())
            return arr
        elif marker == MARKER_OBJECT:
            header = self.read_u29()
            if (header & 1) == 0:
                return self.object_table[header >> 1]

            # Inline object: check traits
            if (header & 2) == 0:
                # Trait reference
                trait_idx = header >> 2
                if trait_idx >= len(self.traits_table):
                    raise ValueError(f"Invalid trait reference index: {trait_idx}")
                traits = self.traits_table[trait_idx]
            else:
                # Inline traits
                is_ext = bool((header >> 2) & 1)
                is_dyn = bool((header >> 3) & 1)
                sealed_count = header >> 4
                class_alias = self.read_string_raw()
                sealed_names = [self.read_string_raw() for _ in range(sealed_count)]
                traits = TraitInfo(class_alias, is_ext, is_dyn, sealed_names)
                self.traits_table.append(traits)

            obj = AMF3Object(class_alias=traits.class_alias)
            self.object_table.append(obj)

            if traits.is_externalizable:
                # Externalizable: unsupported custom serialization
                pass
            else:
                # Sealed properties
                for prop_name in traits.sealed_prop_names:
                    obj[prop_name] = self.decode_value()

                # Dynamic properties
                if traits.is_dynamic:
                    while True:
                        prop_name = self.read_string_raw()
                        if not prop_name:
                            break
                        obj[prop_name] = self.decode_value()

            return obj
        elif marker == MARKER_BYTEARRAY:
            header = self.read_u29()
            if (header & 1) == 0:
                return self.object_table[header >> 1]
            byte_len = header >> 1
            b = self.data[self.offset : self.offset + byte_len]
            self.offset += byte_len
            self.object_table.append(b)
            return b
        else:
            raise ValueError(f"Unsupported AMF3 marker at offset {self.offset - 1}: 0x{marker:02X}")


# --- Serialization Functions ---

def encode_amf3_string(s: str) -> bytes:
    """Encode an AMF3 inline string."""
    b = s.encode('utf-8')
    return encode_u29((len(b) << 1) | 1) + b


def encode_amf3_value(val: Any) -> bytes:
    """Encode any Python primitive to AMF3 binary."""
    if val is None:
        return bytes([MARKER_NULL])
    elif isinstance(val, bool):
        return bytes([MARKER_TRUE if val else MARKER_FALSE])
    elif isinstance(val, AMF3Date):
        return bytes([MARKER_DATE]) + encode_u29(1) + struct.pack(">d", float(val))
    elif isinstance(val, int):
        if -0x10000000 <= val < 0x10000000:
            return bytes([MARKER_INTEGER]) + encode_u29(val)
        else:
            return bytes([MARKER_DOUBLE]) + struct.pack(">d", float(val))
    elif isinstance(val, float):
        return bytes([MARKER_DOUBLE]) + struct.pack(">d", val)
    elif isinstance(val, str):
        return bytes([MARKER_STRING]) + encode_amf3_string(val)
    elif isinstance(val, (bytes, bytearray)):
        b = bytes(val)
        return bytes([MARKER_BYTEARRAY]) + encode_u29((len(b) << 1) | 1) + b
    elif isinstance(val, list):
        out = bytearray([MARKER_ARRAY])
        out.extend(encode_u29((len(val) << 1) | 1))
        out.append(0x01) # empty string dense key
        for item in val:
            out.extend(encode_amf3_value(item))
        return bytes(out)
    elif isinstance(val, AMF3Object):
        return encode_typed_object(val.class_alias, dict(val))
    else:
        raise TypeError(f"Unsupported AMF3 value type: {type(val)}")


def encode_typed_object(class_alias: str, props: Dict[str, Any]) -> bytes:
    """Encode a strongly typed sealed AMF3 object."""
    prop_names = list(props.keys())
    traits_info = (len(prop_names) << 4) | 0x03 # inline object (1), inline sealed traits (2)

    out = bytearray([MARKER_OBJECT])
    out.extend(encode_u29(traits_info))
    out.extend(encode_amf3_string(class_alias))
    for name in prop_names:
        out.extend(encode_amf3_string(name))
    for name in prop_names:
        out.extend(encode_amf3_value(props[name]))
    return bytes(out)


def wrap_server_response(objects: List[bytes], return_code: int = 0) -> bytes:
    """
    Wraps response objects into the client's expected binary format:
    1. Header: 4-byte big-endian signed 32-bit integer return code (0 = success)
       [EngineServerCom.as:493]
    2. Body: Zlib-deflated AMF3 Array of response objects
       [EngineServerCom.as:500-523]
    """
    arr = bytearray([MARKER_ARRAY])
    arr.extend(encode_u29((len(objects) << 1) | 1))
    arr.append(0x01) # empty string dense key
    for obj in objects:
        arr.extend(obj)

    compressed_body = zlib.compress(bytes(arr))
    return struct.pack(">i", return_code) + compressed_body


# --- Pre-defined Game Response Builders ---

def build_abstract_exception(message: str, code: int = 1, checked: bool = False) -> AMF3Object:
    """
    Builds an AbstractException object:
    [RemoteClass(alias="com.frimastudio.commons.amf.exception.AbstractException")]
    [AbstractException.as:3-16]
    """
    props = {
        "message": message,
        "stackTrace": [],
        "code": code,
        "checked": checked,
        "resourceNameId": 0.0,
    }
    return AMF3Object("com.frimastudio.commons.amf.exception.AbstractException", **props)


def build_get_version_response(version: str = "android=1.11.2~ios=1.11.2", cdn_host: str = "127.0.0.1:8000") -> bytes:
    """
    Builds GetVersionResponse:
    [RemoteClass(alias="com.frimastudio.snowstorm.project.player.amf.GetVersionResponse")]
    [GetVersionResponse.as:6-20]
    Fields read by PlayerManagerGT.as:247-248:
    - version (String, e.g. "android=1.11.2~ios=1.11.2")
    - cdn (String, e.g. "127.0.0.1:8000")
    """
    props = {
        "exception": None,
        "version": version,
        "packageVersion": None,
        "packageSize": None,
        "cdn": cdn_host,
    }
    return encode_typed_object("com.frimastudio.snowstorm.project.player.amf.GetVersionResponse", props)


def build_ping_response(gameframe: float = 0.0) -> bytes:
    """
    Builds PingResponse:
    [RemoteClass(alias="com.frimastudio.snowstorm.core.player.amf.PingResponse")]
    [PingResponse.as:6-19]
    """
    props = {
        "exception": None,
        "gameframe": float(gameframe),
        "ping": True,
        "disconected": False,
    }
    return encode_typed_object("com.frimastudio.snowstorm.core.player.amf.PingResponse", props)


def build_get_token_response(token: str = "guest_token_revived", seed: int = 12345678) -> bytes:
    """
    Builds GetTokenResponse:
    [RemoteClass(alias="com.frimastudio.snowstorm.core.player.amf.GetTokenResponse")]
    [GetTokenResponse.as:6-17]
    """
    props = {
        "exception": None,
        "token": token,
        "seed": seed,
    }
    return encode_typed_object("com.frimastudio.snowstorm.core.player.amf.GetTokenResponse", props)


def build_login_response(player_id: int = 1) -> bytes:
    """
    Builds LoginResponse:
    [RemoteClass(alias="com.frimastudio.snowstorm.core.player.amf.LoginResponse")]
    [LoginResponse.as:6-15]
    """
    props = {
        "exception": None,
        "playerId": player_id,
    }
    return encode_typed_object("com.frimastudio.snowstorm.core.player.amf.LoginResponse", props)


def build_get_player_save_response(player_save_bytes: Optional[bytes] = None) -> bytes:
    """
    Builds GetPlayerSaveResponse:
    [RemoteClass(alias="com.frimastudio.snowstorm.project.player.amf.GetPlayerSaveResponse")]
    [GetPlayerSaveResponse.as:7-16]
    """
    props = {
        "exception": None,
        "playerSave": player_save_bytes,
    }
    return encode_typed_object("com.frimastudio.snowstorm.project.player.amf.GetPlayerSaveResponse", props)


def build_error_response(request_alias: str, message: str = "Unknown request", code: int = 1) -> bytes:
    """
    Builds an error response for an unsupported or failed request class.
    Sets the `exception` property to an AbstractException [AbstractException.as:3-16].
    [PlayerManagerGT.as:239-245, EngineServerCom.as:683-700]
    """
    if request_alias.endswith("Request"):
        resp_alias = request_alias[:-7] + "Response"
    else:
        resp_alias = request_alias + "Response"

    exc = build_abstract_exception(f"{message}: {request_alias}", code=code)
    props = {
        "exception": exc
    }
    return encode_typed_object(resp_alias, props)


class DecompressionLimitError(ValueError):
    """Raised when decompressed request body exceeds safety threshold."""
    pass


def decompress_with_limit(body: bytes, max_decomp_size: int = 4 * 1024 * 1024) -> bytes:
    """
    Decompresses zlib stream up to max_decomp_size bytes.
    Raises DecompressionLimitError if decompressed size exceeds max_decomp_size.
    Falls back to raw body if not zlib-compressed.
    """
    dobj = zlib.decompressobj()
    try:
        decomp = dobj.decompress(body, max_decomp_size + 1)
        if len(decomp) > max_decomp_size or len(dobj.unconsumed_tail) > 0:
            raise DecompressionLimitError(
                f"Decompressed payload exceeded maximum limit of {max_decomp_size} bytes"
            )
        return decomp
    except zlib.error:
        # Not compressed or corrupted zlib stream
        if len(body) > max_decomp_size:
            raise DecompressionLimitError(
                f"Raw payload exceeded maximum limit of {max_decomp_size} bytes"
            )
        return body


def parse_client_request(body: bytes, max_decomp_size: int = 4 * 1024 * 1024) -> Tuple[str, List[AMF3Object]]:
    """
    Parses client HTTP POST request body.
    Format [ServerComHTTP.as:376-389]:
    - Zlib deflated ByteArray
    - 2-byte unsigned short (big-endian) ExternalId string length
    - ExternalId UTF-8 string bytes
    - AMF3 serialized Array of request objects

    Returns (external_id, list_of_request_objects).
    Raises DecompressionLimitError if decompression exceeds max_decomp_size.
    """
    decomp = decompress_with_limit(body, max_decomp_size=max_decomp_size)

    if len(decomp) < 2:
        return "", []

    ext_id_len = struct.unpack(">H", decomp[:2])[0]
    ext_id = ""
    if len(decomp) >= 2 + ext_id_len:
        ext_id = decomp[2 : 2 + ext_id_len].decode('utf-8', errors='ignore')
        amf_data = decomp[2 + ext_id_len :]
    else:
        amf_data = decomp

    if not amf_data:
        return ext_id, []

    decoder = AMF3Decoder(amf_data)
    decoded_root = decoder.decode_value()

    if isinstance(decoded_root, list):
        return ext_id, [item for item in decoded_root if isinstance(item, AMF3Object)]
    elif isinstance(decoded_root, AMF3Object):
        return ext_id, [decoded_root]
    else:
        return ext_id, []
