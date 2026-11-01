#!/usr/bin/env python3
"""Exercise actual Pascal JNI entry point with a simulated JNI table on Linux.
This is not an Android runtime or a JVM ABI test. Optional argument: lawful map.
"""
import ctypes as c
import os
import struct
import sys
import tempfile

lib = c.CDLL(sys.argv[1])
configure = lib.Java_com_kamremake_androidprobe_NativeProbeService_nativeConfigureInput
configure.argtypes = [c.c_void_p, c.c_void_p, c.c_int32]
configure.restype = c.c_int32
assert configure(None, None, 0) == 0
assert configure(None, None, -1) == 0
assert configure(None, None, 283) == 283
print('Native input configuration: host timeout preserved; invalid values rejected')
GET = c.CFUNCTYPE(c.c_void_p, c.c_void_p, c.c_void_p, c.c_void_p)
RELEASE = c.CFUNCTYPE(None, c.c_void_p, c.c_void_p, c.c_void_p)
NEW = c.CFUNCTYPE(c.c_void_p, c.c_void_p, c.c_int32)
SET = c.CFUNCTYPE(None, c.c_void_p, c.c_void_p, c.c_int32, c.c_int32, c.POINTER(c.c_int32))
keep = []
@GET
def get(env, text, flag): return text
@RELEASE
def release(env, text, chars): pass
@NEW
def new(env, length):
    value = (c.c_int32 * length)()
    keep.append(value)
    return c.addressof(value)
@SET
def put(env, array, start, length, source): c.memmove(array + 4 * start, source, 4 * length)
table = (c.c_void_p * 231)()
for index, function in [(169, get), (170, release), (179, new), (211, put)]:
    table[index] = c.cast(function, c.c_void_p).value
pointer = c.cast(table, c.c_void_p)
env = c.pointer(pointer)
read = lib.Java_com_kamremake_androidprobe_NativeProbeService_nativeReadMap
read.argtypes = [c.c_void_p, c.c_void_p, c.c_void_p]
read.restype = c.c_void_p
def parse(path):
    text = c.create_string_buffer(os.fsencode(path))
    if not read(env, None, c.addressof(text)): return None
    return list(keep[-1])
with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'synthetic.map')
    data = struct.pack('<ii', 2, 2) + b''.join(bytes([i+1, 0, i+10, 0, 0, 255]) + bytes(17) for i in range(4))
    with open(path, 'wb') as f: f.write(data[:12])
    assert parse(path) is None, 'truncated map accepted'
    with open(path, 'wb') as f: f.write(data)
    result = parse(path)
    assert result and result[:3] == [2, 2, 46] and len(result) == 7
    assert [((v >> 8) & 255) for v in result[3:]] == [10, 11, 12, 13]
    print('Synthetic JNI map 2x2, height sum 46; truncation rejected')
if len(sys.argv) > 2:
    result = parse(sys.argv[2])
    assert result and result[:3] == [128, 128, 543249] and len(result) == 16387
    print('Local OER05 JNI map 128x128, height sum 543249')
