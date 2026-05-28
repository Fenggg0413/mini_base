'''
index_db.py
B+ tree index implementation for mini_base.
'''

import struct
import os
from . import common_db
import ctypes

MAX_NUM_OF_KEYS = 200

LEAF_NODE_TYPE = 1
INTERNAL_NODE_TYPE = 0
SPECIAL_INDEX_BLOCK_PTR = -1
LEN_OF_LEAF_NODE = 10 + 4 + 4
INTERNAL_ENTRY_SIZE = 10 + 4
HEADER_SIZE = struct.calcsize('!iii')


class Index(object):

    def __init__(self, tablename, index_field):
        tablename = tablename.strip()
        index_field = index_field.strip()
        self.tablename = tablename
        self.index_field = index_field
        self.open = False
        self.f_handle = None
        self.has_root = False
        self.number_of_levels = 0
        self.root_node_ptr = 0

        ind_path = common_db.data_path(f'{tablename}.{index_field}.ind')

        if not os.path.exists(ind_path):
            self.f_handle = open(ind_path, 'wb+')
            meta = ctypes.create_string_buffer(common_db.BLOCK_SIZE)
            struct.pack_into('!i?ii', meta, 0, 0, False, 0, 0)
            self.f_handle.seek(0)
            self.f_handle.write(meta)
            self.f_handle.flush()
        else:
            self.f_handle = open(ind_path, 'rb+')
            self._read_meta()

        self.open = True

    def __del__(self):
        if getattr(self, 'open', False) and getattr(self, 'f_handle', None):
            self.f_handle.close()
        self.open = False

    def close(self):
        if self.open and self.f_handle:
            self._write_meta()
            self.f_handle.flush()
            self.f_handle.close()
            self.open = False

    @staticmethod
    def _format_key(field_value, length=10):
        if isinstance(field_value, str):
            field_value = field_value.encode('utf-8')
        return field_value[:length].ljust(length)

    def _read_meta(self):
        self.f_handle.seek(0)
        buf = self.f_handle.read(common_db.BLOCK_SIZE)
        if len(buf) >= struct.calcsize('!i?ii'):
            _, has_root, num_levels, root_ptr = struct.unpack_from('!i?ii', buf, 0)
            self.has_root = has_root
            self.number_of_levels = num_levels
            self.root_node_ptr = root_ptr

    def _write_meta(self):
        meta = ctypes.create_string_buffer(common_db.BLOCK_SIZE)
        struct.pack_into('!i?ii', meta, 0, 0, self.has_root, self.number_of_levels, self.root_node_ptr)
        self.f_handle.seek(0)
        self.f_handle.write(meta)
        self.f_handle.flush()

    def _read_block(self, block_id):
        self.f_handle.seek(block_id * common_db.BLOCK_SIZE)
        return self.f_handle.read(common_db.BLOCK_SIZE)

    def _write_block(self, block_id, data):
        if isinstance(data, ctypes.Array):
            data = bytes(data)
        self.f_handle.seek(block_id * common_db.BLOCK_SIZE)
        self.f_handle.write(data)
        self.f_handle.flush()

    def _allocate_block(self):
        self.f_handle.seek(0, 2)
        file_size = self.f_handle.tell()
        new_block_id = max(file_size // common_db.BLOCK_SIZE, 1)
        if new_block_id < 1:
            new_block_id = 1
        empty = ctypes.create_string_buffer(common_db.BLOCK_SIZE)
        self.f_handle.seek(new_block_id * common_db.BLOCK_SIZE)
        self.f_handle.write(empty)
        self.f_handle.flush()
        return new_block_id

    def _write_leaf_node(self, block_id, num_keys, keys, ptrs, last_ptr):
        buf = ctypes.create_string_buffer(common_db.BLOCK_SIZE)
        struct.pack_into('!iii', buf, 0, block_id, LEAF_NODE_TYPE, num_keys)
        for i in range(num_keys):
            off = HEADER_SIZE + i * LEN_OF_LEAF_NODE
            struct.pack_into('!10sii', buf, off, keys[i], ptrs[i][0], ptrs[i][1])
        struct.pack_into('!i', buf, common_db.BLOCK_SIZE - 4, last_ptr)
        self._write_block(block_id, buf)

    def _write_internal_node(self, block_id, num_keys, keys, ptrs, last_ptr):
        buf = ctypes.create_string_buffer(common_db.BLOCK_SIZE)
        struct.pack_into('!iii', buf, 0, block_id, INTERNAL_NODE_TYPE, num_keys)
        for i in range(num_keys):
            off = HEADER_SIZE + i * INTERNAL_ENTRY_SIZE
            struct.pack_into('!10si', buf, off, keys[i], ptrs[i])
        struct.pack_into('!i', buf, common_db.BLOCK_SIZE - 4, last_ptr)
        self._write_block(block_id, buf)

    def insert_key_value_into_leaf_list(self, insert_key, ptr_tuple, key_list, ptr_list):
        if len(key_list) > 0:
            pos = -1
            for i in range(len(key_list)):
                current_key = key_list[i]
                if current_key == insert_key:
                    pos = i
                    break
                elif current_key > insert_key:
                    pos = i
                    break
            if pos == -1:
                pos = len(key_list)
            key_list.insert(pos, insert_key)
            ptr_list.insert(pos, ptr_tuple)
        elif len(key_list) == 0:
            key_list.append(insert_key)
            ptr_list.append(ptr_tuple)

    def _insert_key_ptr_into_internal_list(self, insert_key, insert_ptr, key_list, ptr_list):
        if len(key_list) > 0:
            pos = -1
            for i in range(len(key_list)):
                current_key = key_list[i]
                if current_key == insert_key:
                    pos = i
                    break
                elif current_key > insert_key:
                    pos = i
                    break
            if pos == -1:
                pos = len(key_list)
            key_list.insert(pos, insert_key)
            ptr_list.insert(pos, insert_ptr)
        elif len(key_list) == 0:
            key_list.append(insert_key)
            ptr_list.append(insert_ptr)

    def get_next_block_ptr(self, current_value, index_key_list, index_ptr_list):
        for i in range(len(index_key_list)):
            if current_value < index_key_list[i]:
                return index_ptr_list[i]
        return index_ptr_list[len(index_key_list)]

    def _create_new_root(self, promoted_key, left_ptr, right_ptr):
        new_root_id = self._allocate_block()
        self._write_internal_node(new_root_id, 1, [promoted_key], [right_ptr], left_ptr)
        self.has_root = True
        self.number_of_levels += 1
        self.root_node_ptr = new_root_id
        self._write_meta()
        return new_root_id

    def insert_index_entry(self, field_value, block_id, offset):
        key = self._format_key(field_value)
        ptr_tuple = (block_id, offset)

        self._read_meta()

        if not self.has_root:
            first_leaf_id = self._allocate_block()
            self._write_leaf_node(first_leaf_id, 1, [key], [ptr_tuple], SPECIAL_INDEX_BLOCK_PTR)
            self.has_root = True
            self.number_of_levels = 1
            self.root_node_ptr = first_leaf_id
            self._write_meta()
            return

        path = []
        current_ptr = self.root_node_ptr
        level = 0

        while level < self.number_of_levels - 1:
            node_data = self._read_block(current_ptr)
            _, node_type, num_keys = struct.unpack_from('!iii', node_data, 0)

            if node_type != INTERNAL_NODE_TYPE:
                return

            keys = []
            ptrs = []
            for i in range(num_keys):
                off = HEADER_SIZE + i * INTERNAL_ENTRY_SIZE
                k, p = struct.unpack_from('!10si', node_data, off)
                keys.append(k)
                ptrs.append(p)
            last_ptr, = struct.unpack_from('!i', node_data, common_db.BLOCK_SIZE - 4)

            path.append((current_ptr, last_ptr, keys, ptrs))

            combined_ptrs = [last_ptr] + list(ptrs)
            current_ptr = self.get_next_block_ptr(key, keys, combined_ptrs)
            level += 1

        leaf_block_id = current_ptr
        leaf_data = self._read_block(leaf_block_id)
        _, node_type, num_keys = struct.unpack_from('!iii', leaf_data, 0)

        if node_type != LEAF_NODE_TYPE:
            return

        keys = []
        ptrs = []
        for i in range(num_keys):
            off = HEADER_SIZE + i * LEN_OF_LEAF_NODE
            k, bid, oid = struct.unpack_from('!10sii', leaf_data, off)
            keys.append(k)
            ptrs.append((bid, oid))
        last_ptr, = struct.unpack_from('!i', leaf_data, common_db.BLOCK_SIZE - 4)

        self.insert_key_value_into_leaf_list(key, ptr_tuple, keys, ptrs)

        promoted_key = None
        new_right_id = None

        if len(keys) > MAX_NUM_OF_KEYS:
            split_idx = len(keys) // 2
            left_keys = keys[:split_idx]
            left_ptrs = ptrs[:split_idx]
            right_keys = keys[split_idx:]
            right_ptrs = ptrs[split_idx:]

            promoted_key = right_keys[0]
            new_right_id = self._allocate_block()

            self._write_leaf_node(leaf_block_id, len(left_keys), left_keys, left_ptrs, new_right_id)
            self._write_leaf_node(new_right_id, len(right_keys), right_keys, right_ptrs, last_ptr)
        else:
            self._write_leaf_node(leaf_block_id, len(keys), keys, ptrs, last_ptr)

        for i in range(len(path) - 1, -1, -1):
            if promoted_key is None:
                break

            parent_block_id, parent_last_ptr, parent_keys, parent_ptrs = path[i]

            self._insert_key_ptr_into_internal_list(promoted_key, new_right_id, parent_keys, parent_ptrs)

            if len(parent_keys) > MAX_NUM_OF_KEYS:
                mid = len(parent_keys) // 2

                left_keys = parent_keys[:mid]
                left_ptrs = parent_ptrs[:mid]

                promoted_key = parent_keys[mid]

                right_keys = parent_keys[mid + 1:]
                right_ptrs = parent_ptrs[mid + 1:]
                left_last_ptr = parent_last_ptr
                right_last_ptr = parent_ptrs[mid]

                new_right_id = self._allocate_block()

                self._write_internal_node(parent_block_id, len(left_keys), left_keys, left_ptrs, left_last_ptr)
                self._write_internal_node(new_right_id, len(right_keys), right_keys, right_ptrs, right_last_ptr)
            else:
                self._write_internal_node(parent_block_id, len(parent_keys), parent_keys, parent_ptrs, parent_last_ptr)
                promoted_key = None
                new_right_id = None

        if promoted_key is not None:
            self._create_new_root(promoted_key, self.root_node_ptr, new_right_id)

    def search_index(self, field_value):
        key = self._format_key(field_value)
        self._read_meta()

        if not self.has_root:
            return []

        current_ptr = self.root_node_ptr
        level = 0

        while level < self.number_of_levels - 1:
            node_data = self._read_block(current_ptr)
            _, node_type, num_keys = struct.unpack_from('!iii', node_data, 0)

            if node_type != INTERNAL_NODE_TYPE:
                break

            keys = []
            ptrs = []
            for i in range(num_keys):
                off = HEADER_SIZE + i * INTERNAL_ENTRY_SIZE
                k, p = struct.unpack_from('!10si', node_data, off)
                keys.append(k)
                ptrs.append(p)
            last_ptr, = struct.unpack_from('!i', node_data, common_db.BLOCK_SIZE - 4)

            combined_ptrs = [last_ptr] + ptrs
            current_ptr = self.get_next_block_ptr(key, keys, combined_ptrs)
            level += 1

        leaf_data = self._read_block(current_ptr)
        _, node_type, num_keys = struct.unpack_from('!iii', leaf_data, 0)

        if node_type != LEAF_NODE_TYPE:
            return []

        results = []
        for i in range(num_keys):
            off = HEADER_SIZE + i * LEN_OF_LEAF_NODE
            k, bid, oid = struct.unpack_from('!10sii', leaf_data, off)
            if k == key:
                results.append((bid, oid))
        return results

    def delete_index_entry(self, field_value, block_id, offset):
        key = self._format_key(field_value)
        ptr_tuple = (block_id, offset)

        self._read_meta()

        if not self.has_root:
            return False

        current_ptr = self.root_node_ptr
        level = 0

        while level < self.number_of_levels - 1:
            node_data = self._read_block(current_ptr)
            _, node_type, num_keys = struct.unpack_from('!iii', node_data, 0)
            if node_type != INTERNAL_NODE_TYPE:
                return False
            keys = []
            ptrs = []
            for i in range(num_keys):
                off = HEADER_SIZE + i * INTERNAL_ENTRY_SIZE
                k, p = struct.unpack_from('!10si', node_data, off)
                keys.append(k)
                ptrs.append(p)
            last_ptr, = struct.unpack_from('!i', node_data, common_db.BLOCK_SIZE - 4)
            combined_ptrs = [last_ptr] + ptrs
            current_ptr = self.get_next_block_ptr(key, keys, combined_ptrs)
            level += 1

        leaf_data = self._read_block(current_ptr)
        _, node_type, num_keys = struct.unpack_from('!iii', leaf_data, 0)
        if node_type != LEAF_NODE_TYPE:
            return False

        keys = []
        ptrs = []
        for i in range(num_keys):
            off = HEADER_SIZE + i * LEN_OF_LEAF_NODE
            k, bid, oid = struct.unpack_from('!10sii', leaf_data, off)
            keys.append(k)
            ptrs.append((bid, oid))
        last_ptr, = struct.unpack_from('!i', leaf_data, common_db.BLOCK_SIZE - 4)

        found = False
        new_keys = []
        new_ptrs = []
        for i in range(num_keys):
            if keys[i] == key and ptrs[i] == ptr_tuple and not found:
                found = True
                continue
            new_keys.append(keys[i])
            new_ptrs.append(ptrs[i])

        if not found:
            return False

        self._write_leaf_node(current_ptr, len(new_keys), new_keys, new_ptrs, last_ptr)
        return True

    def create_index(self):
        from . import storage_db, schema_db

        self._read_meta()
        if self.has_root:
            return False

        sto = storage_db.Storage(self.tablename)
        field_list = sto.getFieldList()

        field_index = -1
        for i, (name, ftype, flen) in enumerate(field_list):
            n = name.strip() if isinstance(name, str) else name.strip().decode('utf-8')
            if n == self.index_field:
                field_index = i
                break

        if field_index == -1:
            sto.f_handle.close()
            sto.open = False
            return False

        for i, pos in enumerate(sto.record_Position):
            blk_id, rec_id = pos
            record = sto.record_list[i]
            field_value = record[field_index]
            if isinstance(field_value, int):
                field_value = str(field_value)
            elif isinstance(field_value, bool):
                field_value = '1' if field_value else '0'
            self.insert_index_entry(field_value, blk_id, rec_id)

        if getattr(sto, 'f_handle', None) and getattr(sto, 'open', False):
            sto.f_handle.close()
            sto.open = False
        return True


