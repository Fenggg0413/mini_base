#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------
# transaction_db.py
# 实现事务持久性相关功能
# -----------------------------------------------------------------------

import os
import struct
import ctypes
import datetime
from .common_db import BLOCK_SIZE
from . import common_db

# 事务状态常量
TRANSACTION_ACTIVE = 0
TRANSACTION_COMMITTED = 1
TRANSACTION_ABORTED = 2

# 操作类型常量
OPERATION_INSERT = 0
OPERATION_UPDATE = 1


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
        # 简单日志格式：事务ID, 状态, 时间戳
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"TXN_STATUS,{txn_id},{status},{timestamp}\n"
        
        # 写入两个日志文件
        self.before_image_file.seek(0, 2)  # 移动到文件末尾
        self.before_image_file.write(log_entry.encode('utf-8'))
        self.before_image_size = self.before_image_file.tell()
        
        self.after_image_file.seek(0, 2)  # 移动到文件末尾
        self.after_image_file.write(log_entry.encode('utf-8'))
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
        # 确保事务存在且活动
        if txn_id not in self.active_transactions or self.active_transactions[txn_id][1] != TRANSACTION_ACTIVE:
            raise ValueError(f"Transaction {txn_id} is not active")
        
        # 构造日志条目
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 确保表名是字节类型
        if isinstance(table_name, str):
            table_name_bytes = table_name.encode('utf-8')
        else:
            table_name_bytes = table_name
            
        # 确保位置信息是字节类型
        location_str = f"{block_id}:{record_offset}"
        location_bytes = location_str.encode('utf-8')
        
        # 确保record_data是字节类型
        try:
            if not isinstance(record_data, bytes):
                if hasattr(record_data, 'raw'):
                    record_data = record_data.raw
                else:
                    record_data = bytes(record_data)
        except Exception as e:
            print(f"无法将record_data转换为字节: {str(e)}")
            record_data = b'ERROR: Cannot convert to bytes'
        
        # 前像日志条目头部
        log_header = struct.pack('!IQI20s50s', 
                                txn_id,  # 事务ID
                                int(datetime.datetime.now().timestamp() * 1000),  # 时间戳（毫秒）
                                len(record_data),  # 记录长度
                                table_name_bytes,  # 表名
                                location_bytes)  # 位置信息
        
        # 写入日志条目
        self.before_image_file.seek(0, 2)  # 移动到文件末尾
        self.before_image_file.write(log_header)
        self.before_image_file.write(record_data)
        self.before_image_size = self.before_image_file.tell()
        
        # 确保数据写入磁盘
        self.before_image_file.flush()
        os.fsync(self.before_image_file.fileno())
        
        return True



    #----------------------------------
    # 记录后像到日志文件
    # 功能：
    #   在对记录进行修改后，将新的记录数据写入后像日志
    # 参数：
    #   txn_id: 事务ID
    #   table_name: 表名（字符串或字节类型）
    #   record_data: 记录的新数据
    #   block_id: 记录所在的块ID
    #   record_offset: 记录在块内的偏移量
    # 返回：
    #   True: 记录成功
    # 异常：
    #   ValueError: 如果事务不存在或不处于活动状态
    #----------------------------------
    def log_after_image(self, txn_id, table_name, record_data, block_id, record_offset):

        # 确保事务存在且活动
        if txn_id not in self.active_transactions or self.active_transactions[txn_id][1] != TRANSACTION_ACTIVE:
            raise ValueError(f"Transaction {txn_id} is not active")
        
        # 构造日志条目
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 确保表名是字节类型
        if isinstance(table_name, str):
            table_name_bytes = table_name.encode('utf-8')
        else:
            table_name_bytes = table_name
            
        # 确保位置信息是字节类型
        location_str = f"{block_id}:{record_offset}"
        location_bytes = location_str.encode('utf-8')
        
        # 确保record_data是字节类型
        try:
            if not isinstance(record_data, bytes):
                if hasattr(record_data, 'raw'):
                    record_data = record_data.raw
                else:
                    record_data = bytes(record_data)
        except Exception as e:
            print(f"无法将record_data转换为字节: {str(e)}")
            record_data = b'ERROR: Cannot convert to bytes'
        
        # 后像日志条目头部
        log_header = struct.pack('!IQI20s50s', 
                                txn_id,  # 事务ID
                                int(datetime.datetime.now().timestamp() * 1000),  # 时间戳（毫秒）
                                len(record_data),  # 记录长度
                                table_name_bytes,  # 表名
                                location_bytes)  # 位置信息
        
        # 写入日志条目
        self.after_image_file.seek(0, 2)  # 移动到文件末尾
        self.after_image_file.write(log_header)
        self.after_image_file.write(record_data)
        self.after_image_size = self.after_image_file.tell()
        
        # 确保数据写入磁盘
        self.after_image_file.flush()
        os.fsync(self.after_image_file.fileno())
        
        return True


    #----------------------------------
    # 从日志中恢复事务状态
    # 功能：
    #   在系统启动或崩溃恢复时，从日志文件中恢复事务状态
    # 处理流程：
    #   1. 分析阶段：确定已提交和未提交的事务
    #   2. 重做阶段：重做已提交事务的操作
    #   3. 撤销阶段：撤销未提交事务的操作
    # 参数：
    #   无
    # 返回：
    #   无
    #----------------------------------
    def _recover_transactions(self):
        print("开始事务恢复过程...")
        
        # 检查日志文件大小
        if self.before_image_size == 0 and self.after_image_size == 0:
            print("没有找到需要恢复的日志")
            return
            
        # 第一步：分析阶段 - 确定提交的和未提交的事务
        committed_txns = set()  # 已提交事务的集合
        active_txns = set()     # 活动（未提交）事务的集合
        
        # 从日志中提取事务状态信息 - 改进方式处理混合格式的日志
        self.after_image_file.seek(0)
        
        # 逐字节扫描日志文件，寻找文本记录
        offset = 0
        while offset < self.after_image_size:
            try:
                self.after_image_file.seek(offset)
                # 读取足够大的块来检查是否为TXN_STATUS记录
                chunk = self.after_image_file.read(10)
                
                # 检查是否为文本记录
                if chunk.startswith(b'TXN_STATUS'):
                    # 读取整行
                    self.after_image_file.seek(offset)
                    line = b''
                    while True:
                        char = self.after_image_file.read(1)
                        if not char or char == b'\n':
                            break
                        line += char
                    
                    # 解析事务状态记录
                    try:
                        line_str = line.decode('utf-8')
                        parts = line_str.split(',')
                        if len(parts) >= 3:
                            txn_id = int(parts[1])
                            status = int(parts[2])
                            
                            if status == TRANSACTION_COMMITTED:
                                committed_txns.add(txn_id)
                                if txn_id in active_txns:
                                    active_txns.remove(txn_id)
                            elif status == TRANSACTION_ACTIVE:
                                if txn_id not in committed_txns:
                                    active_txns.add(txn_id)
                    except Exception as e:
                        print(f"解析事务状态记录时出错: {str(e)}")
                    
                    # 移动到下一行
                    offset += len(line) + 1  # +1 for newline
                else:
                    # 可能是二进制记录，尝试按二进制格式解析
                    try:
                        # 跳过二进制记录
                        # 尝试读取日志头部结构
                        self.after_image_file.seek(offset)
                        log_header = self.after_image_file.read(struct.calcsize('!IQI20s50s'))
                        
                        if len(log_header) == struct.calcsize('!IQI20s50s'):
                            try:
                                txn_id, timestamp, record_len, table_name_bytes, location_bytes = struct.unpack('!IQI20s50s', log_header)
                                # 移动到下一个记录
                                offset += struct.calcsize('!IQI20s50s') + record_len
                            except struct.error:
                                # 如果解析失败，移动到下一个字节
                                offset += 1
                        else:
                            # 读取不完整，移动到下一个字节
                            offset += 1
                    except Exception:
                        # 任何错误，移动到下一个字节
                        offset += 1
            except Exception as e:
                print(f"分析日志时出错: {str(e)}")
                offset += 1
        
        print(f"分析阶段完成: 找到 {len(committed_txns)} 个已提交事务, {len(active_txns)} 个未完成事务")
        
        # 第二步：重做阶段 - 重做所有已提交事务的操作
        if committed_txns:
            print("开始重做阶段...")
            # 处理后像日志中的已提交事务
            self._redo_committed_transactions(committed_txns)
            
        # 第三步：撤销阶段 - 撤销所有未提交事务的操作
        if active_txns:
            print("开始撤销阶段...")
            # 处理前像日志中的未提交事务
            self._undo_uncommitted_transactions(active_txns)
            
        print("恢复过程完成")


    #----------------------------------
    # 重做已提交事务的操作
    # 功能：
    #   根据后像日志，重做所有已提交事务的操作
    # 处理流程：
    #   1. 扫描后像日志文件
    #   2. 对于已提交事务的每个操作，将其应用到数据文件
    # 参数：
    #   committed_txns: 已提交事务ID的集合
    # 返回：
    #   无
    #----------------------------------
    def _redo_committed_transactions(self, committed_txns):
        # 重置文件指针到开始位置
        self.after_image_file.seek(0)
        
        # 遍历整个后像日志文件
        offset = 0
        while offset < self.after_image_size:
            try:
                # 尝试读取日志头部
                self.after_image_file.seek(offset)
                log_header = self.after_image_file.read(struct.calcsize('!IQI20s50s'))
                
                # 如果是文本格式的日志条目（事务状态记录），跳过这一行
                if log_header.startswith(b'TXN_STATUS'):
                    # 跳过这一行
                    line_end = log_header.find(b'\n')
                    if line_end != -1:
                        offset += (line_end + 1)
                    else:
                        # 如果没有找到换行符，移动到下一个字节
                        offset += 1
                    continue
                
                # 解析日志头部
                try:
                    txn_id, timestamp, record_len, table_name_bytes, location_bytes = struct.unpack('!IQI20s50s', log_header)
                    
                    # 如果事务已提交，则重做操作
                    if txn_id in committed_txns:
                        # 读取记录数据
                        record_data = self.after_image_file.read(record_len)
                        
                        # 解析表名和位置信息
                        table_name = table_name_bytes.split(b'\x00')[0].decode('utf-8')
                        location = location_bytes.split(b'\x00')[0].decode('utf-8')
                        
                        try:
                            block_id, record_offset = map(int, location.split(':'))
                            
                            # 重写数据到数据文件
                            self._write_record_to_file(table_name, record_data, block_id, int(record_offset))
                            print(f"重做: 事务 {txn_id} 写入表 {table_name}, 位置 {location}")
                        except Exception as e:
                            print(f"重做记录时出错: {str(e)}")
                    
                    # 移动到下一个日志条目
                    offset += struct.calcsize('!IQI20s50s') + record_len
                    
                except struct.error:
                    # 如果解析失败，移动到下一个字节
                    offset += 1
                    
            except Exception as e:
                print(f"处理后像日志时出错: {str(e)}")
                offset += 1


    #----------------------------------
    # 撤销未提交事务的操作
    # 功能：
    #   根据前像日志，撤销所有未提交事务的操作
    # 处理流程：
    #   1. 扫描前像日志文件
    #   2. 收集所有未提交事务的操作
    #   3. 按时间戳倒序排序操作（最近的先撤销）
    #   4. 对每个位置只处理最早的一个前像
    # 参数：
    #   active_txns: 未提交事务ID的集合
    # 返回：
    #   无
    #----------------------------------
    def _undo_uncommitted_transactions(self, active_txns):
        # 要按时间戳倒序处理前像日志（先处理最近的操作）
        # 创建一个列表来存储所有需要撤销的日志条目
        undo_entries = []
        
        # 重置文件指针到开始位置
        self.before_image_file.seek(0)
        
        # 遍历整个前像日志文件
        offset = 0
        while offset < self.before_image_size:
            try:
                # 尝试读取日志头部
                self.before_image_file.seek(offset)
                log_header = self.before_image_file.read(struct.calcsize('!IQI20s50s'))
                
                # 如果是文本格式的日志条目（事务状态记录），跳过这一行
                if log_header.startswith(b'TXN_STATUS'):
                    # 跳过这一行
                    line_end = log_header.find(b'\n')
                    if line_end != -1:
                        offset += (line_end + 1)
                    else:
                        # 如果没有找到换行符，移动到下一个字节
                        offset += 1
                    continue
                
                # 解析日志头部
                try:
                    txn_id, timestamp, record_len, table_name_bytes, location_bytes = struct.unpack('!IQI20s50s', log_header)
                    
                    # 如果事务未提交，则收集前像信息
                    if txn_id in active_txns:
                        # 读取记录数据
                        record_data = self.before_image_file.read(record_len)
                        # 确保record_data是字节类型
                        if isinstance(record_data, str):
                            record_data = record_data.encode('utf-8')
                        
                        # 解析表名和位置信息
                        table_name = table_name_bytes.split(b'\x00')[0].decode('utf-8')
                        location = location_bytes.split(b'\x00')[0].decode('utf-8')
                        
                        # 添加到撤销条目列表
                        undo_entries.append({
                            'txn_id': txn_id,
                            'timestamp': timestamp,
                            'table_name': table_name,
                            'location': location,
                            'record_data': record_data
                        })
                    
                    # 移动到下一个日志条目
                    offset += struct.calcsize('!IQI20s50s') + record_len
                    
                except struct.error:
                    # 如果解析失败，移动到下一个字节
                    offset += 1
                    
            except Exception as e:
                print(f"处理前像日志时出错: {str(e)}")
                offset += 1
        
        # 按时间戳倒序排序
        undo_entries.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # 对每个位置只处理最早的一个前像（避免重复撤销）
        processed_locations = set()
        
        # 执行撤销操作
        for entry in undo_entries:
            location_key = f"{entry['table_name']}:{entry['location']}"
            
            if location_key not in processed_locations:
                try:
                    block_id, record_offset = map(int, entry['location'].split(':'))
                    
                    # 写回原始数据
                    self._write_record_to_file(entry['table_name'], entry['record_data'], block_id, int(record_offset))
                    print(f"撤销: 事务 {entry['txn_id']} 恢复表 {entry['table_name']}, 位置 {entry['location']}")
                    
                    # 标记该位置已处理
                    processed_locations.add(location_key)
                except Exception as e:
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
                # 尝试使用字节类型的表名
                if isinstance(table_name, str):
                    file_path = common_db.data_path(table_name.encode('utf-8') + b'.dat')
                else:
                    file_path = common_db.data_path(table_name + b'.dat')

                if not os.path.exists(file_path):
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
        except:
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