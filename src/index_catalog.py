'''
index_catalog.py
索引目录管理模块，维护 data/index.cat 二进制文件。
格式：每个条目 24 字节 (10s + 10s + i)，分别为 table_name, field_name, is_active。
'''

import struct
import os
from . import common_db

CATALOG_ENTRY_SIZE = struct.calcsize('!10s10si')
MAX_CATALOG_ENTRIES = 200


def _catalog_path():
    return common_db.data_path('index.cat')


def _ensure_catalog():
    if not os.path.exists(_catalog_path()):
        with open(_catalog_path(), 'wb') as f:
            buf = b'\x00' * (CATALOG_ENTRY_SIZE * MAX_CATALOG_ENTRIES)
            f.write(buf)


def _fmt_name(name):
    if isinstance(name, str):
        name = name.encode('utf-8')
    return name[:10].ljust(10)


def get_indexed_fields(table_name):
    _ensure_catalog()
    table_name = _fmt_name(table_name)
    fields = []
    with open(_catalog_path(), 'rb') as f:
        for _ in range(MAX_CATALOG_ENTRIES):
            raw = f.read(CATALOG_ENTRY_SIZE)
            if len(raw) < CATALOG_ENTRY_SIZE:
                break
            tname, fname, active = struct.unpack('!10s10si', raw)
            if active == 1 and tname == table_name:
                fields.append(fname.strip().decode('utf-8'))
    return fields


def list_all_indexes():
    _ensure_catalog()
    indexes = []
    with open(_catalog_path(), 'rb') as f:
        for _ in range(MAX_CATALOG_ENTRIES):
            raw = f.read(CATALOG_ENTRY_SIZE)
            if len(raw) < CATALOG_ENTRY_SIZE:
                break
            tname, fname, active = struct.unpack('!10s10si', raw)
            if active == 1:
                indexes.append((tname.strip().decode('utf-8'),
                                fname.strip().decode('utf-8')))
    return indexes


def add_index(table_name, field_name):
    _ensure_catalog()
    table_name_fmt = _fmt_name(table_name)
    field_name_fmt = _fmt_name(field_name)

    entries = []
    with open(_catalog_path(), 'rb') as f:
        for _ in range(MAX_CATALOG_ENTRIES):
            raw = f.read(CATALOG_ENTRY_SIZE)
            if len(raw) < CATALOG_ENTRY_SIZE:
                break
            entries.append(raw)

    for raw in entries:
        tname, fname, active = struct.unpack('!10s10si', raw)
        if tname == table_name_fmt and fname == field_name_fmt and active == 1:
            return False

    for i, raw in enumerate(entries):
        tname, fname, active = struct.unpack('!10s10si', raw)
        if active == 0:
            entries[i] = struct.pack('!10s10si', table_name_fmt, field_name_fmt, 1)
            with open(_catalog_path(), 'wb') as f:
                for e in entries:
                    f.write(e)
            return True

    return False


def remove_index(table_name, field_name):
    _ensure_catalog()
    table_name_fmt = _fmt_name(table_name)
    field_name_fmt = _fmt_name(field_name)

    entries = []
    with open(_catalog_path(), 'rb') as f:
        for _ in range(MAX_CATALOG_ENTRIES):
            raw = f.read(CATALOG_ENTRY_SIZE)
            if len(raw) < CATALOG_ENTRY_SIZE:
                break
            entries.append(raw)

    found = False
    for i, raw in enumerate(entries):
        tname, fname, active = struct.unpack('!10s10si', raw)
        if tname == table_name_fmt and fname == field_name_fmt and active == 1:
            entries[i] = struct.pack('!10s10si', b'\x00' * 10, b'\x00' * 10, 0)
            found = True
            break

    if found:
        with open(_catalog_path(), 'wb') as f:
            for e in entries:
                f.write(e)

        ind_path = common_db.data_path(f'{table_name.strip()}.{field_name.strip()}.ind')
        if os.path.exists(ind_path):
            os.remove(ind_path)

    return found


def drop_table_indexes(table_name):
    _ensure_catalog()
    indexed_fields = get_indexed_fields(table_name)
    for field_name in indexed_fields:
        remove_index(table_name, field_name)