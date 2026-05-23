# -----------------------------------------------------------------------
# storage_db.py
# Author: Jingyu Han  hjymail@163.com
# -----------------------------------------------------------------------
# the module is to store tables in files
# Each table is stored in a separate file with the suffix ".dat".
# For example, the table named moviestar is stored in file moviestar.dat 
# -----------------------------------------------------------------------

# struct of file is as follows, each block is 4096
# ---------------------------------------------------
# block_0|block_1|...|block_n
# ----------------------------------------------------------------
from .common_db import BLOCK_SIZE

# structure of block_0, which stores the meta information and field information
# ---------------------------------------------------------------------------------
# block_id                                # 0
# number_of_dat_blocks                    # at first it is 0 because there is no data in the table
# number_of_fields or number_of_records   # the total number of fields for the table
# -----------------------------------------------------------------------------------------


# the data type is as follows
# ----------------------------------------------------------
# 0->str,1->varstr,2->int,3->bool
# ---------------------------------------------------------------


# structure of data block, whose block id begins with 1
# ----------------------------------------
# block_id       
# number of records
# record_0_offset         # it is a pointer to the data of record
# record_1_offset
# ...
# record_n_offset
# ....
# free space
# ...
# record_n
# ...
# record_1
# record_0
# -------------------------------------------

# structre of one record
# -----------------------------
# pointer                     #offset of table schema in block id 0
# length of record            # including record head and record content
# time stamp of last update  # for example,1999-08-22
# field_0_value
# field_1_value
# ...
# field_n_value
# -------------------------


import struct
import os
import ctypes
import datetime
from . import transaction_db
from . import common_db
from . import index_catalog


# --------------------------------------------
# the class can store table data into files
# functions include insert, delete and update
# --------------------------------------------

class Storage(object):

    # ------------------------------
    # constructor of the class
    # input:
    #       tablename
    # -------------------------------------
    def __init__(self, tablename):
        tablename = tablename.strip() if isinstance(tablename, str) else tablename.decode('utf-8').strip()

        self.record_list = []
        self.record_Position = []
        self.tableName = tablename

        if not os.path.exists(common_db.data_path(tablename + '.dat')):
            if common_db.VERBOSE:
                print(f'table file {tablename}.dat does not exist')
            self.f_handle = open(common_db.data_path(tablename + '.dat'), 'wb+')
            self.f_handle.close()
            self.open = False
            if common_db.VERBOSE:
                print(f'{tablename}.dat has been created')

        self.f_handle = open(common_db.data_path(tablename + '.dat'), 'rb+')
        if common_db.VERBOSE:
            print(f'table file {tablename}.dat has been opened')
        self.open = True

        self.dir_buf = ctypes.create_string_buffer(BLOCK_SIZE)
        self.f_handle.seek(0)
        self.dir_buf = self.f_handle.read(BLOCK_SIZE)
        my_len = len(self.dir_buf) if self.dir_buf else 0
        self.field_name_list = []

        if my_len == 0:
            self._init_new_table(tablename)
        else:
            self._load_existing_table()

        self._load_records()

    @classmethod
    def create_table(cls, tablename, field_list):
        """Programmatically create a new table without calling input().

        Args:
            tablename: Name of the table (str)
            field_list: List of (field_name, field_type, field_length) tuples
                        field_type: 0=str, 1=varstr, 2=int, 3=bool

        Returns:
            Storage instance with the table initialized
        """
        tablename = tablename.strip() if isinstance(tablename, str) else tablename.decode('utf-8').strip()

        dat_path = common_db.data_path(tablename + '.dat')
        if os.path.exists(dat_path):
            raise ValueError("Table '%s' already exists" % tablename)

        num_of_fields = len(field_list)

        buf = ctypes.create_string_buffer(BLOCK_SIZE)
        struct.pack_into('!iii', buf, 0, 0, 0, num_of_fields)

        begin_index = struct.calcsize('!iii')
        for fname, ftype, flen in field_list:
            fname_str = fname.strip() if isinstance(fname, str) else fname.strip().decode('utf-8')
            if len(fname_str) < 10:
                fname_str = ' ' * (10 - len(fname_str)) + fname_str
            fname_bytes = fname_str.encode('utf-8')
            struct.pack_into('!10sii', buf, begin_index, fname_bytes, int(ftype), int(flen))
            begin_index += struct.calcsize('!10sii')

        with open(dat_path, 'wb') as f:
            f.write(buf.raw)

        # Open as Storage — since file has data, __init__ will call _load_existing_table
        storage = cls(tablename)
        return storage

    def _init_new_table(self, tablename):
        """Initialize a new table by prompting user for field definitions."""
        beginIndex = 0
        self.num_of_fields = int(input(
            "please input the number of feilds in table " + tablename + ":"))
        if self.num_of_fields <= 0:
            self.data_block_num = 0
            return

        self.dir_buf = ctypes.create_string_buffer(BLOCK_SIZE)
        self.block_id = 0
        self.data_block_num = 0
        struct.pack_into('!iii', self.dir_buf, beginIndex, 0, 0, int(self.num_of_fields))

        beginIndex = beginIndex + struct.calcsize('!iii')

        for i in range(int(self.num_of_fields)):
            field_name = input("please input the name of field " + str(i) + " :")

            if len(field_name) < 10:
                field_name = ' ' * (10 - len(field_name.strip())) + field_name

            while True:
                field_type = input(
                    "please input the type of field(0-> str; 1-> varstr; 2-> int; 3-> boolean) " + str(i) + " :")
                if int(field_type) in [0, 1, 2, 3]:
                    break

            field_length = input("please input the length of field " + str(i) + " :")
            temp_tuple = (field_name, int(field_type), int(field_length))
            self.field_name_list.append(temp_tuple)
            field_name_bytes = field_name.encode('utf-8') if isinstance(field_name, str) else field_name

            struct.pack_into('!10sii', self.dir_buf, beginIndex, field_name_bytes, int(field_type),
                             int(field_length))
            beginIndex = beginIndex + struct.calcsize('!10sii')

        self.f_handle.seek(0)
        self.f_handle.write(self.dir_buf)
        self.f_handle.flush()

    def _load_existing_table(self):
        """Load field and record data from an existing table file."""
        self.block_id, self.data_block_num, self.num_of_fields = struct.unpack_from('!iii', self.dir_buf, 0)

        if common_db.VERBOSE:
            print('number of fields is ', self.num_of_fields)
        if common_db.VERBOSE:
            print('data_block_num', self.data_block_num)
        beginIndex = struct.calcsize('!iii')

        for i in range(self.num_of_fields):
            field_name, field_type, field_length = struct.unpack_from('!10sii', self.dir_buf,
                                                                      beginIndex + i * struct.calcsize('!10sii'))
            field_name_str = field_name.strip().decode('utf-8')
            temp_tuple = (field_name_str, field_type, field_length)
            self.field_name_list.append(temp_tuple)
            if common_db.VERBOSE:
                print(f"the {i}th field information (field name,field type,field length) is {temp_tuple}")

    def _load_records(self):
        """Load all records from data blocks into self.record_list."""
        record_head_len = struct.calcsize('!ii10s')
        record_content_len = sum(x[2] for x in self.field_name_list)

        Flag = 1
        while Flag <= self.data_block_num:
            self.f_handle.seek(BLOCK_SIZE * Flag)
            self.active_data_buf = self.f_handle.read(BLOCK_SIZE)
            self.block_id, self.Number_of_Records = struct.unpack_from('!ii', self.active_data_buf, 0)
            if common_db.VERBOSE:
                print('Block_ID=%s,   Contains %s data' % (self.block_id, self.Number_of_Records))
            if self.Number_of_Records > 0:
                for i in range(self.Number_of_Records):
                    self.record_Position.append((Flag, i))
                    offset = struct.unpack_from('!i', self.active_data_buf,
                                                struct.calcsize('!ii') + i * struct.calcsize('!i'))[0]
                    record = struct.unpack_from('!' + str(record_content_len) + 's', self.active_data_buf,
                                                offset + record_head_len)[0]
                    tmp = 0
                    tmpList = []
                    for field in self.field_name_list:
                        t = record[tmp:tmp + field[2]].strip()
                        tmp = tmp + field[2]
                        if field[1] == 2:
                            t = int(t)
                        elif field[1] == 3:
                            if isinstance(t, bytes):
                                t = t.strip() == b'1' or t.strip().lower() == b'true'
                            else:
                                t = t.strip().lower() in ('1', 'true')
                        else:
                            if isinstance(t, bytes):
                                t = t.decode('utf-8')
                        tmpList.append(t)
                    self.record_list.append(tuple(tmpList))
            Flag += 1

    # ------------------------------
    # return the record list of the table
    # input:
    #       
    # -------------------------------------
    def getRecord(self):
        return self.record_list

    # --------------------------------
    # to insert a record into table with transaction support
    # param insert_record: list
    # param txn_id: transaction ID, if None, no transaction is used
    # return: True or False
    # -------------------------------
    def insert_record(self, insert_record, txn_id=None):

        # example: ['xuyidan','23','123456']

        # step 1 : to check the insert_record is True or False

        tmpRecord = []
        for idx in range(len(self.field_name_list)):
            insert_record[idx] = insert_record[idx].strip()
            if self.field_name_list[idx][1] == 0 or self.field_name_list[idx][1] == 1:
                if len(insert_record[idx]) > self.field_name_list[idx][2]:
                    return False
                tmpRecord.append(insert_record[idx])
            if self.field_name_list[idx][1] == 2:
                try:
                    tmpRecord.append(int(insert_record[idx]))
                except (ValueError, TypeError):
                    return False
            if self.field_name_list[idx][1] == 3:
                try:
                    val = insert_record[idx].strip().lower()
                    tmpRecord.append(val in ('1', 'true'))
                except (ValueError, TypeError):
                    return False
            insert_record[idx] = ' ' * (self.field_name_list[idx][2] - len(insert_record[idx])) + insert_record[idx]

        # step2: Add tmpRecord to record_list ; change insert_record into inputstr
        inputstr = ''.join(insert_record)

        self.record_list.append(tuple(tmpRecord))

        # Step3: To calculate MaxNum in each Data Blocks
        record_content_len = len(inputstr)
        record_head_len = struct.calcsize('!ii10s')
        record_len = record_head_len + record_content_len
        MAX_RECORD_NUM = int((BLOCK_SIZE - struct.calcsize('!i') - struct.calcsize('!ii')) / (
                record_len + struct.calcsize('!i')))

        # Step4: To calculate new record Position
        if not len(self.record_Position):
            self.data_block_num += 1
            self.record_Position.append((1, 0))
        else:
            last_Position = self.record_Position[-1]
            if last_Position[1] == MAX_RECORD_NUM - 1:
                self.record_Position.append((last_Position[0] + 1, 0))
                self.data_block_num += 1
            else:
                self.record_Position.append((last_Position[0], last_Position[1] + 1))

        last_Position = self.record_Position[-1]
        
        # 如果启用了事务，记录后像
        if txn_id is not None:
            # 获取事务管理器
            txn_manager = transaction_db.get_transaction_manager()
            
            # 构造记录数据
            record_data = ctypes.create_string_buffer(record_len)
            record_schema_address = struct.calcsize('!iii')
            update_time = datetime.datetime.now().strftime('%Y-%m-%d')
            
            struct.pack_into('!ii10s', record_data, 0, record_schema_address, record_content_len, update_time.encode('utf-8'))
            struct.pack_into('!' + str(record_content_len) + 's', record_data, record_head_len, inputstr.encode('utf-8'))

            # 根据先记后写规则：插入操作只需要记录后像
            txn_manager.log_after_image(
                txn_id,
                self.tableName,
                record_data.raw,
                last_Position[0],
                BLOCK_SIZE - (last_Position[1] + 1) * record_len
            )

        # Step5: Write new record into file xxx.dat
        # update data_block_num in directory block
        self.f_handle.seek(0)
        self.buf = ctypes.create_string_buffer(struct.calcsize('!iii'))
        num_of_fields = getattr(self, 'num_of_fields', 0)
        struct.pack_into('!iii', self.buf, 0, 0, self.data_block_num, num_of_fields)
        self.f_handle.write(self.buf)
        self.f_handle.flush()

        # update data block head
        self.f_handle.seek(BLOCK_SIZE * last_Position[0])
        self.buf = ctypes.create_string_buffer(struct.calcsize('!ii'))
        struct.pack_into('!ii', self.buf, 0, last_Position[0], last_Position[1] + 1)
        self.f_handle.write(self.buf)
        self.f_handle.flush()

        # update data offset
        offset = struct.calcsize('!ii') + last_Position[1] * struct.calcsize('!i')
        beginIndex = BLOCK_SIZE - (last_Position[1] + 1) * record_len
        self.f_handle.seek(BLOCK_SIZE * last_Position[0] + offset)
        self.buf = ctypes.create_string_buffer(struct.calcsize('!i'))
        struct.pack_into('!i', self.buf, 0, beginIndex)
        self.f_handle.write(self.buf)
        self.f_handle.flush()

        # update data
        record_schema_address = struct.calcsize('!iii')
        update_time = datetime.datetime.now().strftime('%Y-%m-%d')
        self.f_handle.seek(BLOCK_SIZE * last_Position[0] + beginIndex)
        self.buf = ctypes.create_string_buffer(record_len)
        struct.pack_into('!ii10s', self.buf, 0, record_schema_address, record_content_len, update_time.encode('utf-8'))
        struct.pack_into('!' + str(record_content_len) + 's', self.buf, record_head_len, inputstr.encode('utf-8'))
        self.f_handle.write(self.buf.raw)
        self.f_handle.flush()

        # 如果启用了事务，确保持久化
        if txn_id is not None:
            # 确保数据写入磁盘
            os.fsync(self.f_handle.fileno())

        # 更新索引
        self._update_indexes('insert', tuple(tmpRecord), last_Position)

        return True

    # ------------------------------
    # show the data structure and its data
    # input:
    #       t
    # -------------------------------------

    def show_table_data(self):
        headers = []
        for x in self.field_name_list:
            name = x[0]
            if isinstance(name, bytes):
                name = name.decode('utf-8')
            headers.append(name.strip())
        if common_db.VERBOSE:
            print('|    '.join(headers))

        for record in self.record_list:
            if common_db.VERBOSE:
                print(record)

    # --------------------------------
    # to delete  the data file
    # input
    #       table name
    # output
    #       True or False
    # -----------------------------------
    def delete_table_data(self, tableName):

        # step 1: identify whether the file is still open
        if self.open == True:
            self.f_handle.close()
            self.open = False

        # step 2: remove the file from os   
        tableName = tableName.strip()
        if os.path.exists(common_db.data_path(tableName + '.dat')):
            os.remove(common_db.data_path(tableName + '.dat'))

        return True

    # ------------------------------
    # get the list of field information, each element of which is (field name, field type, field length)
    # input:
    #       
    # -------------------------------------

    def getFieldList(self):
        return self.field_name_list

    # ----------------------------------------
    # destructor
    # ------------------------------------------------
    def __del__(self):  # write the metahead information in head object to file
        if getattr(self, 'open', False) and getattr(self, 'f_handle', None):
            self.f_handle.seek(0)
            self.buf = ctypes.create_string_buffer(struct.calcsize('!iii'))
            data_block_num = getattr(self, 'data_block_num', 0)
            num_of_fields = getattr(self, 'num_of_fields', 0)
            struct.pack_into('!iii', self.buf, 0, 0, data_block_num, num_of_fields)
            self.f_handle.write(self.buf)
            self.f_handle.flush()
            self.f_handle.close()

    # ----------------------------------------------------------------------------------------
    # Get and validate a single record input from user.
    # Args:
    #    field_list: List of tuples containing field information (name, type, length)
    # Returns:
    #    list: Validated record values or None if input was cancelled
    # ----------------------------------------------------------------------------------------
    def get_record_input(self, field_list):
        record = []
        for field in field_list:
            while True:
                try:
                    # Get input for each field
                    prompt = f'Enter value for {field[0].strip()} (Type: {field[1]}, Max Length: {field[2]}): '
                    value = input(prompt)

                    # Validate and convert the input
                    is_valid, converted_value, error_msg = common_db.validate_and_convert_value(value, field[1], field[2])

                    if is_valid:
                        record.append(converted_value)
                        break
                    else:
                        if common_db.VERBOSE:
                            print(error_msg)
                        continue

                except Exception as e:
                    if common_db.VERBOSE:
                        print(f"An error occurred: {str(e)}")
                    continue

        return record

    # ----------------------------------------------------------------------------------------
    # Handle the process of inserting record into a table.
    # Args:
    #         data_obj: Storage object for the table
    #         field_list: List of tuples containing field information (name, type, length)
    # Returns:
    #         None
    # ----------------------------------------------------------------------------------------
    def insert_records_from_input(self):
        """
        处理记录插入，支持事务
        """
        # Prompt for a new record
        if common_db.VERBOSE:
            print('\nEnter a new record:')
        field_list = self.getFieldList()
        record = self.get_record_input(field_list)
        # Insert the record with transaction support if a transaction is active
        success = self.insert_record(record, common_db.current_transaction_id)

        if success:
            if common_db.VERBOSE:
                print('Record inserted successfully!')
        else:
            if common_db.VERBOSE:
                print('Failed to insert record. Please check your input.')

        # Display all records after insertion
        if common_db.VERBOSE:
            print('\nCurrent data in the table:')
        self.show_table_data()

    def get_record_by_position(self, block_id, record_id):
        """根据 (block_id, record_id) 位置读取单条记录，返回 tuple 或 None。"""
        if block_id <= 0 or block_id > self.data_block_num:
            return None

        self.f_handle.seek(BLOCK_SIZE * block_id)
        block_buf = self.f_handle.read(BLOCK_SIZE)
        if len(block_buf) < BLOCK_SIZE:
            return None

        _, num_records = struct.unpack_from('!ii', block_buf, 0)
        if record_id < 0 or record_id >= num_records:
            return None

        record_head_len = struct.calcsize('!ii10s')
        record_content_len = sum(x[2] for x in self.field_name_list)

        offset_pos = struct.calcsize('!ii') + record_id * struct.calcsize('!i')
        data_offset = struct.unpack_from('!i', block_buf, offset_pos)[0]

        record_raw = struct.unpack_from('!' + str(record_content_len) + 's', block_buf, data_offset + record_head_len)[0]

        tmp = 0
        values = []
        for field in self.field_name_list:
            val = record_raw[tmp:tmp + field[2]].strip()
            tmp += field[2]
            if field[1] == 2:
                val = int(val)
            elif field[1] == 3:
                if isinstance(val, bytes):
                    val = val.strip() == b'1' or val.strip().lower() == b'true'
                else:
                    val = val.strip().lower() in ('1', 'true')
            else:
                if isinstance(val, bytes):
                    val = val.decode('utf-8')
            values.append(val)

        return tuple(values)

    def _update_indexes(self, action, record, position):
        """在 DML 操作后维护索引。
        action: 'insert' 或 'delete'
        record: tuple，记录值
        position: (block_id, record_offset)
        """
        indexed_fields = index_catalog.get_indexed_fields(self.tableName)
        if not indexed_fields:
            return

        from . import index_db as _idx_mod

        field_map = {}
        for i, (fname, ftype, flen) in enumerate(self.field_name_list):
            fname_str = fname.strip() if isinstance(fname, str) else fname.strip().decode('utf-8')
            field_map[fname_str] = (i, ftype)

        for indexed_field in indexed_fields:
            if indexed_field not in field_map:
                continue
            idx = _idx_mod.Index(self.tableName)
            fi, ftype = field_map[indexed_field]
            field_value = record[fi]
            if ftype == 2:
                field_value = str(field_value)
            elif ftype == 3:
                field_value = '1' if field_value else '0'
            elif isinstance(field_value, bytes):
                field_value = field_value.decode('utf-8')

            if action == 'insert':
                idx.insert_index_entry(field_value, position[0], position[1])
            elif action == 'delete':
                idx.delete_index_entry(field_value, position[0], position[1])
            idx.close()

    def _find_matching_records(self, field_index, field_value):
        """Find indices of records matching the given field value."""
        matching_indices = []
        for i, record in enumerate(self.record_list):
            if self.field_name_list[field_index][1] == 2:  # Integer
                try:
                    if int(field_value) == record[field_index]:
                        matching_indices.append(i)
                except ValueError:
                    pass
            elif self.field_name_list[field_index][1] == 3:  # Boolean
                bool_value = field_value.lower() in ['true', '1']
                if bool_value == record[field_index]:
                    matching_indices.append(i)
            else:  # String
                record_value = record[field_index]
                if isinstance(record_value, bytes):
                    record_value = record_value.strip().decode('utf-8')
                else:
                    record_value = str(record_value).strip()
                if field_value.strip() == record_value:
                    matching_indices.append(i)
        return matching_indices

    # ------------------------------
    # Delete records directly from the file
    # Parameters:
    #   field_index: Index of the field to match
    #   field_value: Value of the field to match(str)
    # Returns:
    #   deleted_count: Number of deleted records
    # --------------------------------------
    def delete_record(self, field_index, field_value):
        if field_index < 0 or field_index >= len(self.field_name_list):
            if common_db.VERBOSE:
                print(f"Field index {field_index} is out of range")
            return 0

        to_delete_indices = self._find_matching_records(field_index, field_value)
        
        if not to_delete_indices:
            # Print debug information
            if common_db.VERBOSE:
                print("No matching records found. Please check if the field value is correct.")
            if common_db.VERBOSE:
                print(f"Search condition: Field {field_index} = '{field_value}'")
            if common_db.VERBOSE:
                print("Records in the table:")
            for i, record in enumerate(self.record_list):
                if common_db.VERBOSE:
                    print(f"Record {i}: {record}")
            return 0

        # 从索引中删除匹配记录
        for idx in to_delete_indices:
            record = self.record_list[idx]
            pos = self.record_Position[idx]
            self._update_indexes('delete', record, pos)

        # Save the number of data blocks before deletion
        old_data_block_num = self.data_block_num
        
        # Delete records from memory
        deleted_indices = sorted(to_delete_indices, reverse=True)  # Delete from back to front to avoid index changes
        for idx in deleted_indices:
            del self.record_list[idx]
            if idx < len(self.record_Position):
                del self.record_Position[idx]
        
        # Special handling if all records are deleted
        if not self.record_list:
            self.data_block_num = 0
            
            # Update the number of data blocks in the file header
            self.f_handle.seek(0)
            self.buf = ctypes.create_string_buffer(struct.calcsize('!iii'))
            struct.pack_into('!iii', self.buf, 0, 0, self.data_block_num, self.num_of_fields)
            self.f_handle.write(self.buf)
            self.f_handle.flush()
            
            return len(deleted_indices)
        
        # Calculate record content and header length
        record_head_len = struct.calcsize('!ii10s')
        record_content_len = sum(map(lambda x: x[2], self.field_name_list))
        record_len = record_head_len + record_content_len
        
        # Calculate the maximum number of records per block
        MAX_RECORD_NUM = int((BLOCK_SIZE - struct.calcsize('!ii')) / (record_len + struct.calcsize('!i')))
        
        # Recalculate record positions
        self.record_Position = []
        for i in range(len(self.record_list)):
            block_id = i // MAX_RECORD_NUM + 1
            record_id = i % MAX_RECORD_NUM
            self.record_Position.append((block_id, record_id))
        
        # Recalculate the number of data blocks
        self.data_block_num = (len(self.record_list) + MAX_RECORD_NUM - 1) // MAX_RECORD_NUM
        
        # Update the number of data blocks in the file header
        self.f_handle.seek(0)
        self.buf = ctypes.create_string_buffer(struct.calcsize('!iii'))
        struct.pack_into('!iii', self.buf, 0, 0, self.data_block_num, self.num_of_fields)
        self.f_handle.write(self.buf)
        self.f_handle.flush()
        
        # Rewrite each data block
        for block_id in range(1, self.data_block_num + 1):
            # Calculate the number of records in the current block
            records_in_block = sum(1 for pos in self.record_Position if pos[0] == block_id)
            
            # Create a data block buffer
            block_buf = ctypes.create_string_buffer(BLOCK_SIZE)
            
            # Write block ID and record count
            struct.pack_into('!ii', block_buf, 0, block_id, records_in_block)
            
            # Calculate the starting position of record offsets and data
            offset_index = struct.calcsize('!ii')
            data_begin_index = BLOCK_SIZE - records_in_block * record_len
            data_index = data_begin_index
            
            # Iterate through all records, find those belonging to the current block
            records_written = 0
            for i, pos in enumerate(self.record_Position):
                if pos[0] == block_id:
                    # Write record offset
                    struct.pack_into('!i', block_buf, offset_index, data_index)
                    offset_index += struct.calcsize('!i')
                    
                    # Convert record to string format
                    record = self.record_list[i]
                    record_str_list = []
                    for j, value in enumerate(record):
                        if self.field_name_list[j][1] == 2:  # Integer
                            field_str = str(value)
                        elif self.field_name_list[j][1] == 3:  # Boolean
                            field_str = '1' if value else '0'
                        else:  # String
                            if isinstance(value, bytes):
                                field_str = value.strip().decode('utf-8')
                            else:
                                field_str = str(value).strip()

                        # Pad with spaces to specified length
                        field_str = ' ' * (self.field_name_list[j][2] - len(field_str)) + field_str
                        record_str_list.append(field_str)
                    
                    inputstr = ''.join(record_str_list)
                    
                    # Write record header
                    record_schema_address = struct.calcsize('!iii')
                    update_time = datetime.datetime.now().strftime('%Y-%m-%d')
                    struct.pack_into('!ii10s', block_buf, data_index, record_schema_address, record_content_len, update_time.encode('utf-8'))
                    
                    # Write record content
                    struct.pack_into('!' + str(record_content_len) + 's', block_buf, data_index + record_head_len, inputstr.encode('utf-8'))

                    data_index += record_len
                    records_written += 1
            
            # Write the data block
            self.f_handle.seek(BLOCK_SIZE * block_id)
            self.f_handle.write(block_buf)
            self.f_handle.flush()
        
        # If the number of data blocks has decreased, clear the excess blocks
        if self.data_block_num < old_data_block_num:
            empty_block = ctypes.create_string_buffer(BLOCK_SIZE)
            for block_id in range(self.data_block_num + 1, old_data_block_num + 1):
                self.f_handle.seek(BLOCK_SIZE * block_id)
                self.f_handle.write(empty_block)
                self.f_handle.flush()
        
        return len(deleted_indices)
    
    # ------------------------------
    # Update records directly in the file
    # Parameters:
    #   condition_field_index: Index of the condition field
    #   condition_field_value: Value of the condition field(str)
    #   update_field_index: Index of the field to update
    #   update_field_value: New value for the field(str)
    #   txn_id: Transaction ID, if None, no transaction is used
    # Returns:
    #   updated_count: Number of updated records
    # --------------------------------------
    def update_record(self, condition_field_index, condition_field_value, update_field_index, update_field_value, txn_id=None):
        if condition_field_index < 0 or condition_field_index >= len(self.field_name_list):
            if common_db.VERBOSE:
                print(f"Condition field index {condition_field_index} is out of range")
            return 0
            
        if update_field_index < 0 or update_field_index >= len(self.field_name_list):
            if common_db.VERBOSE:
                print(f"Update field index {update_field_index} is out of range")
            return 0
        
        # Validate the type and length of the update value
        field_type = self.field_name_list[update_field_index][1]
        field_length = self.field_name_list[update_field_index][2]
        
        if len(update_field_value) > field_length:
            if common_db.VERBOSE:
                print(f"Update value length exceeds maximum field length {field_length}")
            return 0
            
        # Convert the update value to the correct type
        try:
            if field_type == 2:  # Integer
                update_value = int(update_field_value)
            elif field_type == 3:  # Boolean
                update_value = update_field_value.lower() in ['true', '1']
            else:  # String
                update_value = update_field_value.strip()
        except ValueError:
            if common_db.VERBOSE:
                print(f"Failed to convert update value to the required type")
            return 0
            
        # Find indices of records to update
        to_update_indices = self._find_matching_records(condition_field_index, condition_field_value)
        
        if not to_update_indices:
            # Print debug information
            if common_db.VERBOSE:
                print("No matching records found. Please check if the condition field value is correct.")
            if common_db.VERBOSE:
                print(f"Search condition: Field {condition_field_index} = '{condition_field_value}'")
            if common_db.VERBOSE:
                print("Records in the table:")
            for i, record in enumerate(self.record_list):
                if common_db.VERBOSE:
                    print(f"Record {i}: {record}")
            return 0

        # 判断被更新的字段是否有索引
        updated_field_name = self.field_name_list[update_field_index][0]
        if isinstance(updated_field_name, bytes):
            updated_field_name = updated_field_name.strip().decode('utf-8')
        else:
            updated_field_name = updated_field_name.strip()
        indexed_fields = index_catalog.get_indexed_fields(self.tableName)
        need_index_update = updated_field_name in indexed_fields
            
        # 获取事务管理器(如果启用事务)
        txn_manager = None
        if txn_id is not None:
            txn_manager = transaction_db.get_transaction_manager()
            
        # 计算记录内容和头部长度
        record_head_len = struct.calcsize('!ii10s')
        record_content_len = sum(map(lambda x: x[2], self.field_name_list))
        record_len = record_head_len + record_content_len

        # Update records in the file
        updated_count = 0
        for idx in to_update_indices:
            pos = self.record_Position[idx]
            
            # Read the data block
            self.f_handle.seek(BLOCK_SIZE * pos[0])
            block_buf = bytearray(self.f_handle.read(BLOCK_SIZE))
            
            # Get the record offset in the block
            offset_index = struct.calcsize('!ii') + pos[1] * struct.calcsize('!i')
            record_offset = struct.unpack_from('!i', block_buf, offset_index)[0]
            
            # 如果启用事务，记录前像（更新前的数据）
            if txn_id is not None:
                # 获取当前记录数据作为前像
                current_record_data = block_buf[record_offset:record_offset + record_len]
                
                # 根据先记后写规则：先记录前像
                txn_manager.log_before_image(
                    txn_id,
                    self.tableName,
                    current_record_data,
                    pos[0],
                    record_offset
                )
            
            # 更新内存中的记录
            record_list = list(self.record_list[idx])
            old_record = tuple(record_list)
            record_list[update_field_index] = update_value
            self.record_list[idx] = tuple(record_list)

            # 构建新记录 tuple 用于索引更新
            new_record = tuple(self.record_list[idx])

            # 如果更新字段有索引，先删旧索引再插新索引
            if need_index_update:
                pos = self.record_Position[idx]
                self._update_indexes('delete', old_record, pos)
                self._update_indexes('insert', new_record, pos)
            
            # Convert record to string format
            record = self.record_list[idx]
            record_str_list = []
            for j, value in enumerate(record):
                if self.field_name_list[j][1] == 2:  # Integer
                    field_str = str(value)
                elif self.field_name_list[j][1] == 3:  # Boolean
                    field_str = '1' if value else '0'
                else:  # String
                    if isinstance(value, bytes):
                        field_str = value.strip().decode('utf-8')
                    else:
                        field_str = str(value).strip()
                
                # Pad with spaces to specified length
                field_str = ' ' * (self.field_name_list[j][2] - len(field_str)) + field_str
                record_str_list.append(field_str)
            
            inputstr = ''.join(record_str_list)
            
            # 准备更新记录数据
            update_time = datetime.datetime.now().strftime('%Y-%m-%d')
            record_schema_address = struct.calcsize('!iii')
            
            # 更新记录头和内容
            struct.pack_into('!ii10s', block_buf, record_offset, record_schema_address, record_content_len, update_time.encode('utf-8'))
            struct.pack_into('!' + str(record_content_len) + 's', block_buf, record_offset + record_head_len, inputstr.encode('utf-8'))
            
            # 如果启用事务，记录后像（更新后的数据）
            if txn_id is not None:
                # 获取更新后的记录数据作为后像
                updated_record_data = block_buf[record_offset:record_offset + record_len]
                
                # 记录后像
                txn_manager.log_after_image(
                    txn_id,
                    self.tableName,
                    updated_record_data,
                    pos[0],
                    record_offset
                )
            
            # 写回数据块
            self.f_handle.seek(BLOCK_SIZE * pos[0])
            self.f_handle.write(block_buf)
            self.f_handle.flush()
            
            # 如果启用了事务，确保数据写入磁盘
            if txn_id is not None:
                os.fsync(self.f_handle.fileno())
                
            updated_count += 1
        
        return updated_count
