#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------
# transaction_db.py
# 实现事务持久性相关功能
# -----------------------------------------------------------------------

import os
import struct
import datetime
from .common_db import BLOCK_SIZE
from . import common_db

# 事务状态常量
TRANSACTION_ACTIVE = 0
TRANSACTION_COMMITTED = 1
TRANSACTION_ABORTED = 2

LOG_RECORD_STATUS = 0x00
LOG_RECORD_IMAGE = 0x01


#--------------------------------
# 事务管理器类，负责管理事务的持久性
# 实现前像日志、后像日志、活动事务表和提交事务表
#--------------------------------
class TransactionManager:

    #----------------------------------
    # 初始化事务管理器
    # 功能：
    #   创建并初始化事务管理器实例
    # 处理内容：
    #   1. 初始化活动事务表和提交事务表
    #   2. 创建或打开前像和后像日志文件
    #   3. 初始化事务ID计数器
    #   4. 从日志恢复事务状态（如果存在）
    # 返回：
    #   无
    #----------------------------------
    def __init__(self):
        # 初始化事务管理器
        self.active_transactions = {}  # 活动事务表 {txn_id: (start_time, status)}
        self.committed_transactions = {}  # 提交事务表 {txn_id: commit_time}
        
        # 创建日志文件
        if not os.path.exists(common_db.data_path('before_image.log')):
            with open(common_db.data_path('before_image.log'), 'wb') as f:
                pass

        if not os.path.exists(common_db.data_path('after_image.log')):
            with open(common_db.data_path('after_image.log'), 'wb') as f:
                pass

        # 初始化日志文件句柄
        self.before_image_file = open(common_db.data_path('before_image.log'), 'rb+')
        self.after_image_file = open(common_db.data_path('after_image.log'), 'rb+')
        
        # 获取日志文件当前大小
        self.before_image_file.seek(0, 2)  # 移动到文件末尾
        self.before_image_size = self.before_image_file.tell()
        
        self.after_image_file.seek(0, 2)  # 移动到文件末尾
        self.after_image_size = self.after_image_file.tell()
        
        # 初始化下一个事务ID
        self.next_txn_id = 1
        
        # 从日志中恢复事务状态（如果有）
        self._recover_transactions()


    #----------------------------------
    # 开始一个新事务
    # 功能：
    #   创建并启动一个新的事务
    # 参数：
    #   无
    # 返回：
    #   txn_id: 新创建的事务ID
    #----------------------------------
    def begin_transaction(self):
        txn_id = self.next_txn_id
        self.next_txn_id += 1
        
        start_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.active_transactions[txn_id] = (start_time, TRANSACTION_ACTIVE)
        
        return txn_id

    #----------------------------------
    # 提交事务
    # 功能：
    #   将指定的事务标记为已提交状态
    # 参数：
    #   txn_id: 要提交的事务ID
    # 返回：
    #   True: 提交成功
    # 异常：
    #   ValueError: 如果事务不存在或已被提交/中止
    #----------------------------------
    def commit_transaction(self, txn_id):
        if txn_id not in self.active_transactions:
            raise ValueError(f"Transaction {txn_id} does not exist or has been committed/aborted")
        
        # 更新事务状态
        commit_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.active_transactions[txn_id] = (self.active_transactions[txn_id][0], TRANSACTION_COMMITTED)
        self.committed_transactions[txn_id] = commit_time
        
        # 将提交事务记录写入日志
        self._log_transaction_status(txn_id, TRANSACTION_COMMITTED)
        
        # 刷新日志文件
        self.before_image_file.flush()
        self.after_image_file.flush()
        
        # 可选：从活动事务表中移除事务
        # del self.active_transactions[txn_id]
        
        return True

    #----------------------------------
    # 中止事务
    # 功能：
    #   将指定的事务标记为已中止状态
    # 参数：
    #   txn_id: 要中止的事务ID
    # 返回：
    #   True: 中止成功
    # 异常：
    #   ValueError: 如果事务不存在或已被提交/中止
    #----------------------------------
    def abort_transaction(self, txn_id):
        if txn_id not in self.active_transactions:
            raise ValueError(f"Transaction {txn_id} does not exist or has been committed/aborted")
        
        # 更新事务状态
        self.active_transactions[txn_id] = (self.active_transactions[txn_id][0], TRANSACTION_ABORTED)
        
        # 将中止事务记录写入日志
        self._log_transaction_status(txn_id, TRANSACTION_ABORTED)
        
        # 刷新日志文件
        self.before_image_file.flush()
        self.after_image_file.flush()
        
        return True


    #----------------------------------
    # 记录事务状态变更到日志
    # 功能：
    #   将事务状态变更（如提交、中止）记录到前像和后像日志
    # 参数：
    #   txn_id: 事务ID
    #   status: 事务状态（TRANSACTION_ACTIVE、TRANSACTION_COMMITTED或TRANSACTION_ABORTED）
    # 返回：
    #   无
    #----------------------------------
    def _log_transaction_status(self, txn_id, status):
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"TXN_STATUS,{txn_id},{status},{timestamp}\n"
        
        for log_file in (self.before_image_file, self.after_image_file):
            log_file.seek(0, 2)
            log_file.write(struct.pack('!B', LOG_RECORD_STATUS))
            log_file.write(log_entry.encode('utf-8'))
        
        self.before_image_size = self.before_image_file.tell()
        self.after_image_size = self.after_image_file.tell()


    #----------------------------------
    # 记录前像到日志文件
    # 功能：
    #   在对记录进行修改前，将原始记录数据写入前像日志
    # 参数：
    #   txn_id: 事务ID
    #   table_name: 表名（字符串或字节类型）
    #   record_data: 记录的原始数据
    #   block_id: 记录所在的块ID
    #   record_offset: 记录在块内的偏移量
    # 返回：
    #   True: 记录成功
    # 异常：
    #   ValueError: 如果事务不存在或不处于活动状态
    #----------------------------------
    def log_before_image(self, txn_id, table_name, record_data, block_id, record_offset):
        if txn_id not in self.active_transactions or self.active_transactions[txn_id][1] != TRANSACTION_ACTIVE:
            raise ValueError(f"Transaction {txn_id} is not active")
        return self._log_image(self.before_image_file, txn_id, table_name, record_data, block_id, record_offset, 'before')

    def log_after_image(self, txn_id, table_name, record_data, block_id, record_offset):
        if txn_id not in self.active_transactions or self.active_transactions[txn_id][1] != TRANSACTION_ACTIVE:
            raise ValueError(f"Transaction {txn_id} is not active")
        return self._log_image(self.after_image_file, txn_id, table_name, record_data, block_id, record_offset, 'after')

    def _log_image(self, log_file, txn_id, table_name, record_data, block_id, record_offset, image_type):
        if isinstance(table_name, str):
            table_name_bytes = table_name.encode('utf-8')
        else:
            table_name_bytes = table_name

        location_bytes = f"{block_id}:{record_offset}".encode('utf-8')

        try:
            if not isinstance(record_data, bytes):
                if hasattr(record_data, 'raw'):
                    record_data = record_data.raw
                else:
                    record_data = bytes(record_data)
        except Exception as e:
            if common_db.VERBOSE:
                print(f"无法将record_data转换为字节: {str(e)}")
            record_data = b'ERROR: Cannot convert to bytes'

        log_header = struct.pack('!IQI20s50s',
                                txn_id,
                                int(datetime.datetime.now().timestamp() * 1000),
                                len(record_data),
                                table_name_bytes,
                                location_bytes)

        log_file.seek(0, 2)
        log_file.write(struct.pack('!B', LOG_RECORD_IMAGE))
        log_file.write(log_header)
        log_file.write(record_data)

        if image_type == 'before':
            self.before_image_size = log_file.tell()
        else:
            self.after_image_size = log_file.tell()

        log_file.flush()
        os.fsync(log_file.fileno())

        return True


    def _read_log_entry(self, log_file):
        """Read a single log entry from the current file position.
        
        Returns a tuple (entry_type, entry_data) where:
          entry_type is LOG_RECORD_STATUS or LOG_RECORD_IMAGE
          entry_data is a dict with parsed fields
        Returns None if end of file or unrecoverable error.
        """
        pos = log_file.tell()
        magic_byte = log_file.read(1)
        if not magic_byte:
            return None
        
        record_type = struct.unpack('!B', magic_byte)[0]
        
        if record_type == LOG_RECORD_STATUS:
            line = b''
            while True:
                ch = log_file.read(1)
                if not ch or ch == b'\n':
                    break
                line += ch
            try:
                line_str = line.decode('utf-8')
                parts = line_str.split(',')
                if len(parts) >= 3:
                    txn_id = int(parts[1])
                    status = int(parts[2])
                    return (LOG_RECORD_STATUS, {'txn_id': txn_id, 'status': status})
            except Exception as e:
                if common_db.VERBOSE:
                    print(f"解析事务状态记录时出错: {str(e)}")
            return None
        
        elif record_type == LOG_RECORD_IMAGE:
            header_size = struct.calcsize('!IQI20s50s')
            log_header = log_file.read(header_size)
            if len(log_header) < header_size:
                return None
            try:
                txn_id, timestamp, record_len, table_name_bytes, location_bytes = struct.unpack('!IQI20s50s', log_header)
                record_data = log_file.read(record_len)
                if len(record_data) < record_len:
                    return None
                table_name = table_name_bytes.split(b'\x00')[0].decode('utf-8')
                location = location_bytes.split(b'\x00')[0].decode('utf-8')
                return (LOG_RECORD_IMAGE, {
                    'txn_id': txn_id,
                    'timestamp': timestamp,
                    'record_len': record_len,
                    'table_name': table_name,
                    'location': location,
                    'record_data': record_data,
                })
            except struct.error as e:
                if common_db.VERBOSE:
                    print(f"解析二进制日志记录时出错: {str(e)}")
                return None
        else:
            return None

    def _recover_transactions(self):
        if common_db.VERBOSE:
            print("开始事务恢复过程...")
        
        if self.before_image_size == 0 and self.after_image_size == 0:
            if common_db.VERBOSE:
                print("没有找到需要恢复的日志")
            return
        
        committed_txns = set()
        active_txns = set()
        
        self.after_image_file.seek(0)
        while True:
            entry = self._read_log_entry(self.after_image_file)
            if entry is None:
                break
            entry_type, entry_data = entry
            if entry_type == LOG_RECORD_STATUS:
                txn_id = entry_data['txn_id']
                status = entry_data['status']
                if status == TRANSACTION_COMMITTED:
                    committed_txns.add(txn_id)
                    if txn_id in active_txns:
                        active_txns.remove(txn_id)
                elif status == TRANSACTION_ACTIVE:
                    if txn_id not in committed_txns:
                        active_txns.add(txn_id)
        
        if common_db.VERBOSE:
            print(f"分析阶段完成: 找到 {len(committed_txns)} 个已提交事务, {len(active_txns)} 个未完成事务")
        
        for txn_id in committed_txns:
            self.committed_transactions[txn_id] = 'recovered'
        
        if committed_txns:
            if common_db.VERBOSE:
                print("开始重做阶段...")
            self._redo_committed_transactions(committed_txns)
        
        if active_txns:
            if common_db.VERBOSE:
                print("开始撤销阶段...")
            self._undo_uncommitted_transactions(active_txns)
        
        if common_db.VERBOSE:
            print("恢复过程完成")

    def _redo_committed_transactions(self, committed_txns):
        self.after_image_file.seek(0)
        while True:
            entry = self._read_log_entry(self.after_image_file)
            if entry is None:
                break
            entry_type, entry_data = entry
            if entry_type == LOG_RECORD_IMAGE:
                if entry_data['txn_id'] in committed_txns:
                    try:
                        block_id, record_offset = map(int, entry_data['location'].split(':'))
                        self._write_record_to_file(
                            entry_data['table_name'],
                            entry_data['record_data'],
                            block_id,
                            int(record_offset)
                        )
                        if common_db.VERBOSE:
                            print(f"重做: 事务 {entry_data['txn_id']} 写入表 {entry_data['table_name']}, 位置 {entry_data['location']}")
                    except Exception as e:
                        if common_db.VERBOSE:
                            print(f"重做记录时出错: {str(e)}")

    def _undo_uncommitted_transactions(self, active_txns):
        undo_entries = []
        
        self.before_image_file.seek(0)
        while True:
            entry = self._read_log_entry(self.before_image_file)
            if entry is None:
                break
            entry_type, entry_data = entry
            if entry_type == LOG_RECORD_IMAGE:
                if entry_data['txn_id'] in active_txns:
                    undo_entries.append(entry_data)
        
        undo_entries.sort(key=lambda x: x['timestamp'], reverse=True)
        
        processed_locations = set()
        
        for entry in undo_entries:
            location_key = f"{entry['table_name']}:{entry['location']}"
            
            if location_key not in processed_locations:
                try:
                    block_id, record_offset = map(int, entry['location'].split(':'))
                    self._write_record_to_file(entry['table_name'], entry['record_data'], block_id, int(record_offset))
                    if common_db.VERBOSE:
                        print(f"撤销: 事务 {entry['txn_id']} 恢复表 {entry['table_name']}, 位置 {entry['location']}")
                    processed_locations.add(location_key)
                except Exception as e:
                    if common_db.VERBOSE:
                        print(f"撤销记录时出错: {str(e)}")


    #----------------------------------
    # 将记录数据写入到数据文件的指定位置
    # 功能：
    #   将记录数据写入到数据文件的指定块和偏移位置
    # 参数：
    #   table_name: 表名（字符串或字节类型）
    #   record_data: 要写入的记录数据（字节类型）
    #   block_id: 目标块ID
    #   record_offset: 目标块内的偏移量
    # 返回：
    #   True: 写入成功
    #   False: 写入失败
    #----------------------------------
    def _write_record_to_file(self, table_name, record_data, block_id, record_offset):
        """将记录数据写入到数据文件的指定位置"""
        try:
            # 确保表名是字符串类型
            if isinstance(table_name, bytes):
                table_name_str = table_name.decode('utf-8')
            else:
                table_name_str = table_name

            # 确保record_data是字节类型
            if isinstance(record_data, str):
                record_data = record_data.encode('utf-8')

            # 打开数据文件
            file_path = common_db.data_path(f"{table_name_str}.dat")
            if not os.path.exists(file_path):
                if common_db.VERBOSE:
                    print(f"数据文件 {file_path} 不存在，无法恢复数据")
                return False
                
            with open(file_path, 'rb+') as f:
                # 定位到指定块和偏移
                f.seek(BLOCK_SIZE * block_id + record_offset)
                
                # 写入记录数据
                f.write(record_data)
                f.flush()
                os.fsync(f.fileno())  # 确保数据写入磁盘
                
            return True
        except Exception as e:
            if common_db.VERBOSE:
                print(f"写入数据文件时出错: {str(e)}")
            return False
    
    #----------------------------------
    # 析构函数
    # 功能：
    #   在对象被销毁时关闭日志文件
    # 参数：
    #   无
    # 返回：
    #   无
    #----------------------------------
    def __del__(self):
        """析构函数，关闭日志文件"""
        try:
            if hasattr(self, 'before_image_file') and self.before_image_file:
                self.before_image_file.close()
            
            if hasattr(self, 'after_image_file') and self.after_image_file:
                self.after_image_file.close()
        except Exception:
            pass

# 全局事务管理器实例
transaction_manager = None

#----------------------------------
# 获取全局事务管理器实例
# 功能：
#   获取或创建全局事务管理器实例（单例模式）
# 参数：
#   无
# 返回：
#   transaction_manager: 全局事务管理器实例
#----------------------------------
def get_transaction_manager():
    """获取全局事务管理器实例"""
    global transaction_manager
    if transaction_manager is None:
        transaction_manager = TransactionManager()
    return transaction_manager 