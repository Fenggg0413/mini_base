#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from src import schema_db
from src import common_db

def test_schema():
    # 删除已有的schema文件，以便重新创建
    if os.path.exists(common_db.data_path('all.sch')):
        os.remove(common_db.data_path('all.sch'))
    
    # 创建schema对象
    sch = schema_db.Schema()
    
    # 创建学生表
    student_fields = [
        ('sid'.encode('utf-8'), 0, 3),    # 字符串类型的学号，长度3
        ('name'.encode('utf-8'), 1, 10),  # 变长字符串类型的姓名，长度10
        ('dept'.encode('utf-8'), 0, 6),   # 字符串类型的系，长度6
        ('age'.encode('utf-8'), 2, 3)     # 整数类型的年龄，长度3
    ]
    sch.appendTable('students', student_fields)
    
    # 创建课程表
    course_fields = [
        ('cid'.encode('utf-8'), 0, 3),        # 字符串类型的课程号，长度3
        ('cname'.encode('utf-8'), 1, 20),     # 变长字符串类型的课程名，长度20
        ('dept'.encode('utf-8'), 1, 10),      # 变长字符串类型的系，长度10
        ('credit'.encode('utf-8'), 2, 3)      # 整数类型的学分，长度3
    ]
    sch.appendTable('courses', course_fields)
    
    # 查看表结构
    print("\n测试查看学生表结构:")
    sch.viewTableStructure('students')
    
    print("\n测试查看课程表结构:")
    sch.viewTableStructure('courses')
    
    # 查看所有表名
    print("\n测试查看所有表名:")
    sch.viewTableNames()
    
    # 删除学生表并验证
    print("\n测试删除学生表:")
    sch.delete_table_schema('students')
    sch.viewTableNames()
    
    # 关闭schema对象，确保数据写入文件
    del sch
    
    # 重新打开schema文件，验证数据已正确保存
    print("\n测试重新加载schema文件:")
    sch2 = schema_db.Schema()
    sch2.viewTableNames()
    sch2.viewTableStructure('courses')

if __name__ == "__main__":
    test_schema()

