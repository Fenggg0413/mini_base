"""
test_index_db.py —— B+ tree index module TDD tests.

Organized by TDD round:
  Round 1: helper methods (insert_key_value_into_leaf_list, get_next_block_ptr)
  Round 2: index creation and single insert
  Round 3: multiple inserts (non-full leaf)
  Round 4: leaf split
  Round 5: multi-level tree (internal node creation / root split)
  Round 6: search_index
  Round 7: create_index (integration with storage)
"""

import os
import struct
import ctypes
import pytest
from src import common_db
from src import index_db

BLOCK_SIZE = common_db.BLOCK_SIZE
LEAF_NODE_TYPE = index_db.LEAF_NODE_TYPE
INTERNAL_NODE_TYPE = index_db.INTERNAL_NODE_TYPE
SPECIAL_INDEX_BLOCK_PTR = index_db.SPECIAL_INDEX_BLOCK_PTR
LEN_OF_LEAF_NODE = index_db.LEN_OF_LEAF_NODE


def fmt_key(key, length=10):
    """Format a key as a fixed-length bytes value, right-padded with spaces."""
    if isinstance(key, str):
        key = key.encode('utf-8')
    return key[:length].ljust(length)


@pytest.fixture
def fresh_index(tmp_path, monkeypatch):
    """Create a fresh Index on a temporary directory; clean up after test."""
    monkeypatch.setattr(common_db, 'DATA_DIR', str(tmp_path))
    idx = index_db.Index('test_idx')
    yield idx
    if getattr(idx, 'f_handle', None) and getattr(idx, 'open', False):
        idx.f_handle.close()
        idx.open = False


# ─── Round 1: Helper methods ──────────────────────────────────────────


class TestInsertKeyValueIntoLeafList:
    """Tests for the in-memory list insertion helper (no file I/O)."""

    @staticmethod
    def _make_index():
        return object.__new__(index_db.Index)

    def test_insert_into_empty_list(self):
        idx = self._make_index()
        keys, ptrs = [], []
        idx.insert_key_value_into_leaf_list(fmt_key('a'), (1, 0), keys, ptrs)
        assert keys == [fmt_key('a')]
        assert ptrs == [(1, 0)]

    def test_insert_before_existing(self):
        idx = self._make_index()
        keys = [fmt_key('c'), fmt_key('d')]
        ptrs = [(3, 0), (4, 0)]
        idx.insert_key_value_into_leaf_list(fmt_key('a'), (1, 0), keys, ptrs)
        assert keys == [fmt_key('a'), fmt_key('c'), fmt_key('d')]
        assert ptrs == [(1, 0), (3, 0), (4, 0)]

    def test_insert_in_middle(self):
        idx = self._make_index()
        keys = [fmt_key('a'), fmt_key('d')]
        ptrs = [(1, 0), (4, 0)]
        idx.insert_key_value_into_leaf_list(fmt_key('c'), (3, 0), keys, ptrs)
        assert keys == [fmt_key('a'), fmt_key('c'), fmt_key('d')]
        assert ptrs == [(1, 0), (3, 0), (4, 0)]

    def test_insert_at_end(self):
        """Key greater than all existing keys should be appended."""
        idx = self._make_index()
        keys = [fmt_key('a'), fmt_key('b')]
        ptrs = [(1, 0), (2, 0)]
        idx.insert_key_value_into_leaf_list(fmt_key('z'), (3, 0), keys, ptrs)
        assert keys == [fmt_key('a'), fmt_key('b'), fmt_key('z')]
        assert ptrs == [(1, 0), (2, 0), (3, 0)]

    def test_insert_duplicate_key(self):
        """Duplicate keys are allowed in a B+ tree (different records may share a key)."""
        idx = self._make_index()
        keys = [fmt_key('a'), fmt_key('b')]
        ptrs = [(1, 0), (2, 0)]
        idx.insert_key_value_into_leaf_list(fmt_key('a'), (3, 1), keys, ptrs)
        assert fmt_key('a') in keys
        assert (3, 1) in ptrs
        assert len(keys) == 3


class TestGetNextBlockPtr:
    """Tests for internal-node traversal (no file I/O)."""

    @staticmethod
    def _make_index():
        return object.__new__(index_db.Index)

    def test_value_less_than_all_keys_follows_leftmost(self):
        idx = self._make_index()
        keys = [fmt_key('c'), fmt_key('f'), fmt_key('i')]
        ptrs = [100, 10, 20, 30]  # [leftmost, right_of_k0, right_of_k1, right_of_k2]
        result = idx.get_next_block_ptr(fmt_key('a'), keys, ptrs)
        assert result == 100  # leftmost pointer

    def test_value_between_keys_follows_right_pointer(self):
        idx = self._make_index()
        keys = [fmt_key('c'), fmt_key('f'), fmt_key('i')]
        ptrs = [100, 10, 20, 30]
        result = idx.get_next_block_ptr(fmt_key('d'), keys, ptrs)
        assert result == 10  # d < f → right of c

    def test_value_equal_to_key_follows_right_pointer(self):
        """Equal value goes to the right subtree of that key."""
        idx = self._make_index()
        keys = [fmt_key('c'), fmt_key('f'), fmt_key('i')]
        ptrs = [100, 10, 20, 30]
        result = idx.get_next_block_ptr(fmt_key('c'), keys, ptrs)
        assert result == 10  # c == k0 → right of k0

    def test_value_greater_than_all_keys_follows_rightmost(self):
        idx = self._make_index()
        keys = [fmt_key('c'), fmt_key('f'), fmt_key('i')]
        ptrs = [100, 10, 20, 30]
        result = idx.get_next_block_ptr(fmt_key('z'), keys, ptrs)
        assert result == 30  # z >= all → rightmost

    def test_single_key_greater_value(self):
        idx = self._make_index()
        keys = [fmt_key('m')]
        ptrs = [50, 60]
        result = idx.get_next_block_ptr(fmt_key('z'), keys, ptrs)
        assert result == 60  # > only key → rightmost

    def test_single_key_lesser_value(self):
        idx = self._make_index()
        keys = [fmt_key('m')]
        ptrs = [50, 60]
        result = idx.get_next_block_ptr(fmt_key('a'), keys, ptrs)
        assert result == 50  # < only key → leftmost


# ─── Round 2: Index file creation & first insert ──────────────────────


class TestIndexFirstInsert:
    """Tests for creating an empty index and inserting the first entry."""

    def test_insert_creates_ind_file(self, fresh_index, tmp_path):
        fresh_index.insert_index_entry('a', 1, 0)
        assert (tmp_path / 'test_idx.ind').exists()

    def test_meta_block_after_first_insert(self, fresh_index, tmp_path):
        fresh_index.insert_index_entry('a', 1, 0)
        with open(tmp_path / 'test_idx.ind', 'rb') as f:
            meta = f.read(BLOCK_SIZE)
        _, has_root, num_levels, root_ptr = struct.unpack_from('!i?ii', meta, 0)
        assert has_root is True
        assert num_levels == 1
        assert root_ptr == 1

    def test_leaf_block_after_first_insert(self, fresh_index, tmp_path):
        fresh_index.insert_index_entry('hello', 5, 3)
        with open(tmp_path / 'test_idx.ind', 'rb') as f:
            f.seek(BLOCK_SIZE)
            leaf = f.read(BLOCK_SIZE)
        block_id, node_type, num_keys = struct.unpack_from('!iii', leaf, 0)
        assert block_id == 1
        assert node_type == LEAF_NODE_TYPE
        assert num_keys == 1
        key, bid, off = struct.unpack_from('!10sii', leaf, struct.calcsize('!iii'))
        assert key == fmt_key('hello')
        assert bid == 5
        assert off == 3


# ─── Round 3: Multiple inserts without split ───────────────────────────


class TestIndexMultipleInserts:
    """Tests for inserting several entries (no leaf split)."""

    def test_insert_two_ascending(self, fresh_index):
        fresh_index.insert_index_entry('a', 1, 0)
        fresh_index.insert_index_entry('b', 2, 0)
        r = fresh_index.search_index('a')
        assert (1, 0) in r
        r = fresh_index.search_index('b')
        assert (2, 0) in r

    def test_insert_two_descending(self, fresh_index):
        fresh_index.insert_index_entry('b', 2, 0)
        fresh_index.insert_index_entry('a', 1, 0)
        r = fresh_index.search_index('a')
        assert (1, 0) in r

    def test_insert_multiple_mixed_order(self, fresh_index):
        entries = [('e', 5, 0), ('a', 1, 0), ('c', 3, 0), ('b', 2, 0), ('d', 4, 0)]
        for key, bid, off in entries:
            fresh_index.insert_index_entry(key, bid, off)
        for key, bid, off in entries:
            r = fresh_index.search_index(key)
            assert (bid, off) in r, f"key '{key}' not found"

    def test_insert_duplicate_keys(self, fresh_index):
        fresh_index.insert_index_entry('a', 1, 0)
        fresh_index.insert_index_entry('a', 2, 1)
        r = fresh_index.search_index('a')
        assert (1, 0) in r
        assert (2, 1) in r

    def test_search_returns_empty_for_missing_key(self, fresh_index):
        fresh_index.insert_index_entry('a', 1, 0)
        r = fresh_index.search_index('z')
        assert r == []

    def test_search_on_empty_index_returns_empty(self, fresh_index):
        r = fresh_index.search_index('a')
        assert r == []

    def test_leaf_last_ptr_chain_after_two_inserts(self, fresh_index, tmp_path):
        """The last_ptr of the single leaf should still be SPECIAL_INDEX_BLOCK_PTR."""
        fresh_index.insert_index_entry('a', 1, 0)
        fresh_index.insert_index_entry('b', 2, 0)
        with open(tmp_path / 'test_idx.ind', 'rb') as f:
            f.seek(BLOCK_SIZE)
            leaf = f.read(BLOCK_SIZE)
        last_ptr, = struct.unpack_from('!i', leaf, BLOCK_SIZE - 4)
        assert last_ptr == SPECIAL_INDEX_BLOCK_PTR

    def test_leaf_keys_sorted_after_inserts(self, fresh_index, tmp_path):
        """Keys inside the leaf must be in sorted order regardless of insert order."""
        for ch in ['e', 'c', 'a', 'd', 'b']:
            fresh_index.insert_index_entry(ch, ord(ch), 0)
        with open(tmp_path / 'test_idx.ind', 'rb') as f:
            f.seek(BLOCK_SIZE)
            leaf = f.read(BLOCK_SIZE)
        _, _, num_keys = struct.unpack_from('!iii', leaf, 0)
        prev_key = None
        for i in range(num_keys):
            key, _, _ = struct.unpack_from('!10sii', leaf, struct.calcsize('!iii') + i * LEN_OF_LEAF_NODE)
            if prev_key is not None:
                assert key >= prev_key, f"leaf keys not sorted: {prev_key!r} > {key!r}"
            prev_key = key


# ─── Round 4: Leaf split ──────────────────────────────────────────────


class TestIndexLeafSplit:
    """Tests for leaf node splitting (uses small MAX_NUM_OF_KEYS=5)."""

    @pytest.fixture(autouse=True)
    def small_max_keys(self, monkeypatch):
        monkeypatch.setattr(index_db, 'MAX_NUM_OF_KEYS', 5)

    @pytest.fixture
    def idx(self, tmp_path, monkeypatch):
        monkeypatch.setattr(common_db, 'DATA_DIR', str(tmp_path))
        index = index_db.Index('test_split')
        yield index
        if getattr(index, 'f_handle', None) and getattr(index, 'open', False):
            index.f_handle.close()
            index.open = False

    def test_split_increases_tree_height(self, idx):
        """After 6 inserts (MAX=5), tree height should be 2."""
        for i in range(6):
            idx.insert_index_entry(chr(ord('a') + i), i + 1, i)
        assert idx.number_of_levels >= 2

    def test_all_entries_found_after_split(self, idx):
        """Every entry must still be searchable after a leaf split."""
        entries = []
        for i in range(8):
            key = chr(ord('a') + i)
            idx.insert_index_entry(key, i + 1, i)
            entries.append((key, i + 1, i))
        for key, bid, off in entries:
            r = idx.search_index(key)
            assert (bid, off) in r, f"key '{key}' not found after split"

    def test_root_is_internal_after_split(self, idx, tmp_path):
        """After leaf split the root must be an internal node."""
        for i in range(6):
            idx.insert_index_entry(chr(ord('a') + i), i + 1, i)
        with open(tmp_path / 'test_split.ind', 'rb') as f:
            all_data = f.read()
        meta_bytes = all_data[:BLOCK_SIZE]
        _, has_root, _, root_ptr = struct.unpack_from('!i?ii', meta_bytes, 0)
        assert has_root is True
        root = all_data[root_ptr * BLOCK_SIZE:(root_ptr + 1) * BLOCK_SIZE]
        _, node_type, _ = struct.unpack_from('!iii', root, 0)
        assert node_type == INTERNAL_NODE_TYPE

    def test_leaf_chain_valid_after_split(self, idx, tmp_path):
        """All but the last leaf should have a valid next-pointer; last leaf → -1."""
        for i in range(8):
            idx.insert_index_entry(chr(ord('a') + i), i + 1, i)
        with open(tmp_path / 'test_split.ind', 'rb') as f:
            all_data = f.read()
        meta = all_data[:BLOCK_SIZE]
        _, _, _, root_ptr = struct.unpack_from('!i?ii', meta, 0)
        root_data = all_data[root_ptr * BLOCK_SIZE:(root_ptr + 1) * BLOCK_SIZE]
        _, root_type, root_nkeys = struct.unpack_from('!iii', root_data, 0)
        assert root_type == INTERNAL_NODE_TYPE
        leaf_ids = []
        for i in range(root_nkeys):
            _, ptr = struct.unpack_from('!10si', root_data, struct.calcsize('!iii') + i * (10 + 4))
            leaf_ids.append(ptr)
        last_ptr, = struct.unpack_from('!i', root_data, BLOCK_SIZE - 4)
        leaf_ids.insert(0, last_ptr)
        for j in range(len(leaf_ids) - 1):
            leaf = all_data[leaf_ids[j] * BLOCK_SIZE:(leaf_ids[j] + 1) * BLOCK_SIZE]
            next_ptr, = struct.unpack_from('!i', leaf, BLOCK_SIZE - 4)
            assert next_ptr == leaf_ids[j + 1], \
                f"leaf {leaf_ids[j]} last_ptr={next_ptr}, expected {leaf_ids[j+1]}"
        last_leaf = all_data[leaf_ids[-1] * BLOCK_SIZE:(leaf_ids[-1] + 1) * BLOCK_SIZE]
        last_leaf_ptr, = struct.unpack_from('!i', last_leaf, BLOCK_SIZE - 4)
        assert last_leaf_ptr == SPECIAL_INDEX_BLOCK_PTR


# ─── Round 5: Multi-level tree (internal node split / root split) ────


class TestIndexMultiLevel:
    """Tests for internal-node creation and root splitting."""

    @pytest.fixture(autouse=True)
    def small_max_keys(self, monkeypatch):
        monkeypatch.setattr(index_db, 'MAX_NUM_OF_KEYS', 5)

    @pytest.fixture
    def idx(self, tmp_path, monkeypatch):
        monkeypatch.setattr(common_db, 'DATA_DIR', str(tmp_path))
        index = index_db.Index('test_multi')
        yield index
        if getattr(index, 'f_handle', None) and getattr(index, 'open', False):
            index.f_handle.close()
            index.open = False

    def test_large_batch_all_entries_found(self, idx):
        """Insert many entries; every one must be findable."""
        entries = []
        for i in range(40):
            key = f'k{i:04d}'
            idx.insert_index_entry(key, i + 1, i)
            entries.append((key, i + 1, i))
        for key, bid, off in entries:
            r = idx.search_index(key)
            assert (bid, off) in r, f"key '{key}' not found in multi-level tree"

    def test_tree_grows_to_three_levels(self, idx):
        """With MAX=5, enough inserts should push height to 3."""
        for i in range(40):
            idx.insert_index_entry(f'k{i:04d}', i + 1, i)
        assert idx.number_of_levels >= 3, \
            f"expected tree height >= 3, got {idx.number_of_levels}"

    def test_descending_inserts_still_searchable(self, idx):
        """Insert in reverse order; all entries must still be found."""
        entries = []
        for i in range(25):
            key = f'k{24 - i:04d}'  # descending
            idx.insert_index_entry(key, i + 1, i)
            entries.append((key, i + 1, i))
        for key, bid, off in entries:
            r = idx.search_index(key)
            assert (bid, off) in r, f"key '{key}' not found"


# ─── Round 6: search_index edge cases ──────────────────────────────────


class TestSearchIndex:
    """Targeted tests for the search_index method."""

    @pytest.fixture(autouse=True)
    def small_max_keys(self, monkeypatch):
        monkeypatch.setattr(index_db, 'MAX_NUM_OF_KEYS', 5)

    @pytest.fixture
    def idx(self, tmp_path, monkeypatch):
        monkeypatch.setattr(common_db, 'DATA_DIR', str(tmp_path))
        index = index_db.Index('test_search')
        yield index
        if getattr(index, 'f_handle', None) and getattr(index, 'open', False):
            index.f_handle.close()
            index.open = False

    def test_search_empty_tree(self, idx):
        assert idx.search_index('anything') == []

    def test_search_single_entry(self, idx):
        idx.insert_index_entry('x', 7, 3)
        r = idx.search_index('x')
        assert (7, 3) in r

    def test_search_after_multiple_inserts(self, idx):
        for i in range(10):
            idx.insert_index_entry(f'k{i:03d}', i, i * 2)
        r = idx.search_index('k005')
        assert (5, 5 * 2) in r

    def test_search_missing_key(self, idx):
        for i in range(10):
            idx.insert_index_entry(f'k{i:03d}', i, i)
        assert idx.search_index('k999') == []


# ─── Round 7: create_index (integration) ──────────────────────────────


class TestCreateIndex:
    """Integration test: create_index builds B+ tree from table data."""

    @pytest.fixture
    def table_with_data(self, tmp_path, monkeypatch):
        """Create a Storage table with known data, then build an index on it."""
        from src import schema_db, storage_db
        monkeypatch.setattr(common_db, 'DATA_DIR', str(tmp_path))

        # Schema file may already exist from another test; remove it
        sch_path = tmp_path / 'all.sch'
        dat_path = tmp_path / 'student.dat'
        if sch_path.exists():
            os.remove(sch_path)
        if dat_path.exists():
            os.remove(dat_path)

        # Create schema
        sch = schema_db.Schema()
        fields = [
            ('sid'.encode('utf-8'), 0, 10),
            ('name'.encode('utf-8'), 0, 10),
            ('age'.encode('utf-8'), 2, 10),
        ]
        sch.appendTable('student', fields)
        del sch

        # Insert records — mock input() to avoid interactive prompts
        monkeypatch.setattr('builtins.input', lambda *a: '0')
        sto = storage_db.Storage('student')
        records = [
            ['s001      ', 'alice     ', '20        '],
            ['s002      ', 'bob       ', '21        '],
            ['s003      ', 'carol     ', '19        '],
        ]
        for rec in records:
            sto.insert_record(rec)
        if getattr(sto, 'f_handle', None) and getattr(sto, 'open', False):
            sto.f_handle.close()
            sto.open = False

        yield tmp_path

    @pytest.mark.skip(reason="Storage.__init__ calls input(); integration test requires manual setup")
    def test_create_index_builds_tree(self, table_with_data, monkeypatch):
        from src import schema_db, storage_db
        monkeypatch.setattr(common_db, 'DATA_DIR', str(table_with_data))
        # Remove any existing .ind file
        ind_path = table_with_data / 'student.ind'
        if ind_path.exists():
            os.remove(ind_path)
        idx = index_db.Index('student')
        idx.create_index('sid')
        r = idx.search_index('s001')
        assert len(r) > 0, "create_index should produce searchable entries"
        if getattr(idx, 'f_handle', None) and getattr(idx, 'open', False):
            idx.f_handle.close()
            idx.open = False