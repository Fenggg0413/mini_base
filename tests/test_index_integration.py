"""
test_index_integration.py —— 索引集成测试：目录管理、delete_index_entry、
查询加速等。
"""

import os
import pytest
from src import common_db
from src import index_db
from src import index_catalog


BLOCK_SIZE = common_db.BLOCK_SIZE


@pytest.fixture
def tmp_data(tmp_path, monkeypatch):
    """Redirect DATA_DIR to tmp_path for isolation."""
    monkeypatch.setattr(common_db, 'DATA_DIR', str(tmp_path))
    # 确保目录存在
    os.makedirs(str(tmp_path), exist_ok=True)
    yield tmp_path


@pytest.fixture
def fresh_catalog(tmp_data):
    """Ensure a clean catalog file."""
    cat_path = common_db.data_path('index.cat')
    if os.path.exists(cat_path):
        os.remove(cat_path)
    return tmp_data


# ─── Index Catalog ─────────────────────────────────────────────────

class TestIndexCatalog:
    def test_add_and_get_index(self, fresh_catalog):
        assert index_catalog.add_index('student', 'sid') is True
        fields = index_catalog.get_indexed_fields('student')
        assert 'sid' in fields

    def test_add_duplicate_index_fails(self, fresh_catalog):
        index_catalog.add_index('student', 'sid')
        assert index_catalog.add_index('student', 'sid') is False

    def test_remove_index(self, fresh_catalog):
        index_catalog.add_index('student', 'sid')
        assert index_catalog.remove_index('student', 'sid') is True
        fields = index_catalog.get_indexed_fields('student')
        assert 'sid' not in fields

    def test_remove_nonexistent_index(self, fresh_catalog):
        assert index_catalog.remove_index('student', 'sid') is False

    def test_list_all_indexes(self, fresh_catalog):
        index_catalog.add_index('student', 'sid')
        index_catalog.add_index('course', 'cid')
        all_idx = index_catalog.list_all_indexes()
        assert ('student', 'sid') in all_idx
        assert ('course', 'cid') in all_idx

    def test_drop_table_indexes(self, fresh_catalog):
        index_catalog.add_index('student', 'sid')
        index_catalog.add_index('student', 'name')
        index_catalog.drop_table_indexes('student')
        assert index_catalog.get_indexed_fields('student') == []

    def test_multiple_indexes_on_same_table(self, fresh_catalog):
        index_catalog.add_index('student', 'sid')
        index_catalog.add_index('student', 'name')
        fields = index_catalog.get_indexed_fields('student')
        assert 'sid' in fields
        assert 'name' in fields


# ─── delete_index_entry ─────────────────────────────────────────────

class TestDeleteIndexEntry:
    @pytest.fixture
    def idx(self, tmp_data):
        index = index_db.Index('test_del', 'key')
        yield index
        if getattr(index, 'f_handle', None) and getattr(index, 'open', False):
            index.f_handle.close()
            index.open = False

    def test_delete_from_single_entry(self, idx):
        idx.insert_index_entry('a', 1, 0)
        assert idx.search_index('a') == [(1, 0)]
        assert idx.delete_index_entry('a', 1, 0) is True
        assert idx.search_index('a') == []

    def test_delete_nonexistent_returns_false(self, idx):
        idx.insert_index_entry('a', 1, 0)
        assert idx.delete_index_entry('b', 1, 0) is False
        assert idx.delete_index_entry('a', 2, 0) is False

    def test_delete_one_of_duplicate_keys(self, idx):
        idx.insert_index_entry('a', 1, 0)
        idx.insert_index_entry('a', 2, 1)
        assert idx.delete_index_entry('a', 1, 0) is True
        assert idx.search_index('a') == [(2, 1)]

    def test_delete_from_empty_tree(self, idx):
        assert idx.delete_index_entry('a', 1, 0) is False

    def test_delete_preserves_other_entries(self, idx):
        idx.insert_index_entry('a', 1, 0)
        idx.insert_index_entry('b', 2, 0)
        idx.insert_index_entry('c', 3, 0)
        assert idx.delete_index_entry('b', 2, 0) is True
        assert (1, 0) in idx.search_index('a')
        assert idx.search_index('b') == []
        assert (3, 0) in idx.search_index('c')

    @pytest.fixture
    def idx_small(self, tmp_path, monkeypatch):
        monkeypatch.setattr(common_db, 'DATA_DIR', str(tmp_path))
        monkeypatch.setattr(index_db, 'MAX_NUM_OF_KEYS', 5)
        index = index_db.Index('test_del_small', 'key')
        yield index
        if getattr(index, 'f_handle', None) and getattr(index, 'open', False):
            index.f_handle.close()
            index.open = False

    def test_delete_after_split(self, idx_small):
        for i in range(8):
            idx_small.insert_index_entry(chr(ord('a') + i), i + 1, i)
        # Delete a few entries (for i=2: key='c', block_id=3, offset=2)
        assert idx_small.delete_index_entry('c', 3, 2) is True
        assert idx_small.search_index('c') == []
        assert (1, 0) in idx_small.search_index('a')


# ─── Per-field .ind file isolation ─────────────────────────────────────

class TestPerFieldIndexFiles:
    def test_two_indexes_on_same_table_use_separate_files(self, tmp_data):
        """同一张表的两个字段索引必须落到不同 .ind 文件。"""
        idx_a = index_db.Index('students', 'name')
        idx_a.insert_index_entry('Alice', 1, 0)
        idx_a.close()

        idx_b = index_db.Index('students', 'age')
        idx_b.insert_index_entry('20', 1, 0)
        idx_b.close()

        assert os.path.exists(common_db.data_path('students.name.ind'))
        assert os.path.exists(common_db.data_path('students.age.ind'))
        assert not os.path.exists(common_db.data_path('students.ind'))

    def test_drop_one_index_keeps_the_other(self, tmp_data, fresh_catalog):
        """删一个字段索引不能删掉同表另一字段的索引文件。"""
        for field in ('name', 'age'):
            idx = index_db.Index('students', field)
            idx.insert_index_entry('x', 1, 0)
            idx.close()
            index_catalog.add_index('students', field)

        index_catalog.remove_index('students', 'name')

        assert not os.path.exists(common_db.data_path('students.name.ind'))
        assert os.path.exists(common_db.data_path('students.age.ind'))

    def test_search_returns_only_matching_field_records(self, tmp_data):
        """跨字段索引不应该串扰：搜 name='Alice' 不该返回 age 索引里同 key 的项。"""
        name_idx = index_db.Index('students', 'name')
        name_idx.insert_index_entry('Alice', 1, 0)
        name_idx.close()

        age_idx = index_db.Index('students', 'age')
        age_idx.insert_index_entry('Alice', 99, 99)
        age_idx.close()

        name_idx2 = index_db.Index('students', 'name')
        results = name_idx2.search_index('Alice')
        name_idx2.close()
        assert results == [(1, 0)]


def test_create_index_handles_duplicate_positions(isolated_data_dir, monkeypatch):
    """触发"position 元组重复"路径——验证 enumerate 修复。"""
    from src import index_db, storage_db
    monkeypatch.setattr(index_db, 'MAX_NUM_OF_KEYS', 5)
    sto = storage_db.Storage.create_table(
        't',
        [('name', 0, 10), ('age', 2, 4)],
    )
    sto.insert_record(['Alice', '20'])
    sto.insert_record(['Alice', '20'])  # 完全相同的字段值
    sto.insert_record(['Bob', '21'])
    del sto

    idx = index_db.Index('t', 'name')
    idx.create_index()
    results = idx.search_index('Alice')
    idx.close()
    assert len(results) == 2
    assert len(set(results)) == 2