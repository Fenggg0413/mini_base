#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------
# test_transaction.py
# 测试事务持久性
# -----------------------------------------------------------------------

import os
import sys
import time
import random
import signal
from src import storage_db
from src import transaction_db
from src import schema_db

def test_existing_table():
    """测试已存在的表"""
    # 选择一个已存在的表进行测试
    table_name = "test"
    
    print(f"使用已存在的表 {table_name} 进行测试")
    
    # 打开已存在的表
    storage_obj = storage_db.Storage(table_name.encode('utf-8'))
    
    return storage_obj

def show_table_data(storage_obj):
    """显示表数据"""
    print("\n当前表数据:")
    storage_obj.show_table_data()
    print()

def insert_with_transaction(storage_obj, records, crash_probability=0):
    """使用事务插入记录"""
    # 获取事务管理器
    txn_manager = transaction_db.get_transaction_manager()
    
    # 开始事务
    txn_id = txn_manager.begin_transaction()
    print(f"开始事务 {txn_id}")
    
    try:
        # 插入记录
        for i, record in enumerate(records):
            print(f"插入记录 {i+1}/{len(records)}: {record}")
            success = storage_obj.insert_record(record, txn_id)
            
            if not success:
                print(f"插入记录 {record} 失败")
                txn_manager.abort_transaction(txn_id)
                return False
            
            # 随机模拟崩溃
            if crash_probability > 0 and random.random() < crash_probability:
                print("模拟系统崩溃...")
                os._exit(1)  # 强制退出程序，不执行任何清理操作
        
        # 提交事务
        print(f"提交事务 {txn_id}")
        txn_manager.commit_transaction(txn_id)
        return True
    except Exception as e:
        print(f"事务执行出错: {str(e)}")
        try:
            txn_manager.abort_transaction(txn_id)
        except:
            pass
        return False

def update_with_transaction(storage_obj, condition_field_index, condition_value, update_field_index, update_value, crash_probability=0):
    """使用事务更新记录"""
    # 获取事务管理器
    txn_manager = transaction_db.get_transaction_manager()
    
    # 开始事务
    txn_id = txn_manager.begin_transaction()
    print(f"开始更新事务 {txn_id}")
    
    try:
        # 更新记录
        print(f"更新条件: 字段 {condition_field_index} = {condition_value}")
        print(f"更新内容: 字段 {update_field_index} = {update_value}")
        
        updated_count = storage_obj.update_record(
            condition_field_index,
            condition_value,
            update_field_index,
            update_value,
            txn_id
        )
        
        if updated_count == 0:
            print("未找到匹配记录，更新失败")
            txn_manager.abort_transaction(txn_id)
            return False
        
        print(f"更新了 {updated_count} 条记录")
        
        # 随机模拟崩溃
        if crash_probability > 0 and random.random() < crash_probability:
            print("模拟系统崩溃...")
            os._exit(1)  # 强制退出程序，不执行任何清理操作
        
        # 提交事务
        print(f"提交事务 {txn_id}")
        txn_manager.commit_transaction(txn_id)
        return True
    except Exception as e:
        print(f"事务执行出错: {str(e)}")
        try:
            txn_manager.abort_transaction(txn_id)
        except:
            pass
        return False

def main():
    """主函数"""
    print("事务持久性测试开始")
    
    # 初始化事务管理器
    txn_manager = transaction_db.get_transaction_manager()
    
    # 使用已存在的表进行测试
    storage_obj = None
    
    try:
        storage_obj = test_existing_table()
    except Exception as e:
        print(f"打开表失败: {str(e)}")
        return
    
    # 显示初始表数据
    show_table_data(storage_obj)
    
    # 测试选项
    print("测试选项:")
    print("1. 插入记录")
    print("2. 更新记录")
    print("3. 显示表数据")
    print("4. 模拟崩溃后的恢复")
    print("5. 退出")
    
    while True:
        choice = input("请选择操作 (1-5): ")
        
        if choice == '1':
            # 插入记录
            field_list = storage_obj.getFieldList()
            records = []
            
            num_records = int(input("请输入要插入的记录数量: "))
            crash_prob = float(input("请输入崩溃概率 (0-1): "))
            
            for i in range(num_records):
                record = []
                print(f"记录 {i+1}:")
                for j, field in enumerate(field_list):
                    field_name = field[0].strip().decode('utf-8')
                    field_type = field[1]
                    if field_type == 0 or field_type == 1:  # 字符串
                        value = input(f"  {field_name} (字符串): ")
                    elif field_type == 2:  # 整数
                        value = input(f"  {field_name} (整数): ")
                    elif field_type == 3:  # 布尔值
                        value = input(f"  {field_name} (布尔值): ")
                    record.append(value)
                records.append(record)
            
            # 使用事务插入记录
            insert_with_transaction(storage_obj, records, crash_prob)
            
            # 显示表数据
            show_table_data(storage_obj)
            
        elif choice == '2':
            # 更新记录
            field_list = storage_obj.getFieldList()
            
            # 显示字段列表
            print("字段列表:")
            for i, field in enumerate(field_list):
                field_name = field[0].strip().decode('utf-8')
                print(f"{i}: {field_name}")
            
            # 获取条件字段
            condition_field_idx = int(input("请输入条件字段索引: "))
            condition_value = input("请输入条件值: ")
            
            # 获取更新字段
            update_field_idx = int(input("请输入要更新的字段索引: "))
            update_value = input("请输入新值: ")
            
            # 获取崩溃概率
            crash_prob = float(input("请输入崩溃概率 (0-1): "))
            
            # 使用事务更新记录
            update_with_transaction(
                storage_obj,
                condition_field_idx,
                condition_value,
                update_field_idx,
                update_value,
                crash_prob
            )
            
            # 显示表数据
            show_table_data(storage_obj)
            
        elif choice == '3':
            # 显示表数据
            show_table_data(storage_obj)
            
        elif choice == '4':
            # 模拟崩溃
            print("模拟系统崩溃并恢复...")
            print("系统将在3秒后退出，然后您需要重新启动程序来测试恢复功能")
            time.sleep(3)
            os._exit(1)
            
        elif choice == '5':
            # 退出
            print("测试结束")
            break
            
        else:
            print("无效选择，请重新输入")

if __name__ == "__main__":
    main() 