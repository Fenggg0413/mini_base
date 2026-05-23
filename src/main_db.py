# -----------------------
# main_db.py
# author: Jingyu Han   hjymail@163.com
# modified by: Ning Wang, Yidan Xu
# -----------------------------------
# This is the main loop of the program
# ---------------------------------------

import struct
import sys
import ctypes
import os

from . import head_db  # the main memory structure of table schema
from . import schema_db  # the module to process table schema
from . import storage_db  # the module to process the storage of instance

from . import query_plan_db  # for SQL clause of which data is stored in binary format
from . import lex_db  # for lex, where data is stored in binary format
from . import parser_db  # for yacc, where ddata is tored in binary format
from . import common_db  # the global variables, functions, constants in the program
from . import transaction_db  # 导入事务管理模块
from . import index_db  # 导入索引管理模块
from . import index_catalog  # 导入索引目录管理模块

PROMPT_STR = 'Input your choice  \n1:add a new table structure and data \n2:delete a table structure and data\
\n3:view a table structure and data \n4:delete all tables and data \n5:select from where clause\
\n6:delete a row according to field keyword \n7:update a row according to field keyword \
\n8:begin a transaction \n9:commit transaction \n10:abort transaction \
\n11:create an index on a table field \n12:drop an index \n13:view all indexes \
\n. to quit):\n'


# --------------------------
# the main loop, which needs further implementation
# ---------------------------

def main():
    # main loops for the whole program
    print('main function begins to execute')

    # 初始化事务管理器并进行崩溃恢复
    print("初始化事务管理器并进行崩溃恢复...")
    txn_manager = transaction_db.get_transaction_manager()
    print("事务初始化完成")

    # The instance data of table is stored in binary format, which corresponds to chapter 2-8 of textbook

    schemaObj = schema_db.Schema()  # to create a schema object, which contains the schema of all tables
    dataObj = None
    choice = input(PROMPT_STR)

    while True:

        if choice == '1':  # add a new table and lines of data
            tableName = input('please enter your new table name:')
            insertFieldList = []
            if tableName.strip() not in schemaObj.get_table_name_list():
                dataObj = storage_db.Storage(tableName)
                insertFieldList = dataObj.getFieldList()
                schemaObj.appendTable(tableName, insertFieldList)
            else:
                dataObj = storage_db.Storage(tableName)
                schemaObj.viewTableStructure(tableName)
                dataObj.insert_records_from_input()
                del dataObj

            choice = input(PROMPT_STR)





        elif choice == '2':  # delete a table from schema file and data file

            table_name = input('please input the name of the table to be deleted:')
            if schemaObj.find_table(table_name.strip()):
                if schemaObj.delete_table_schema(table_name.strip()):
                    # 先删除该表的所有索引
                    index_catalog.drop_table_indexes(table_name.strip())
                    dataObj = storage_db.Storage(table_name.strip())
                    dataObj.delete_table_data(table_name.strip())
                    del dataObj
                else:
                    print('the deletion from schema file fail')
            else:
                print(f'there is no table {table_name.strip()} in the schema file')


            choice = input(PROMPT_STR)



        elif choice == '3':  # view the table structure and all the data

            print(schemaObj.headObj.tableNames)
            table_name = input('please input the name of the table to be displayed:')
            if table_name.strip():
                if schemaObj.find_table(table_name.strip()):
                    schemaObj.viewTableStructure(table_name)
                    dataObj = storage_db.Storage(table_name.strip())
                    dataObj.show_table_data()
                    del dataObj
                else:
                    print('table name is None')

            choice = input(PROMPT_STR)



        elif choice == '4':  # delete all the table structures and their data
            table_name_list = list(schemaObj.get_table_name_list())
            # to be inserted here -> to delete from data files
            for i in range(len(table_name_list)):
                table_name = table_name_list[i].strip()

                if table_name:
                    # 删除该表的所有索引
                    index_catalog.drop_table_indexes(table_name)
                    stObj = storage_db.Storage(table_name)
                    stObj.delete_table_data(table_name.strip())  # delete table data
                    del stObj

            schemaObj.deleteAll()  # delete schema from schema file

            choice = input(PROMPT_STR)


        elif choice == '5':  # process SELECT FROM WHERE clause
            print('#        Your Query is to SQL QUERY                  #')
            sql_str = input('please enter the select from where clause:')
            lex_db.set_lex_handle()  # to set the global_lexer in common_db.py
            parser_db.set_handle()  # to set the global_parser in common_db.py
            common_db.global_syn_tree = None
            common_db.global_logical_tree = None

            try:
                common_db.global_syn_tree = common_db.global_parser.parse(sql_str.strip(),
                                                                          lexer=common_db.global_lexer)  # construct the global_syn_tree
                query_plan_db.construct_logical_tree()
                query_plan_db.execute_logical_tree()
            except Exception as e:
                print('WRONG SQL INPUT! %s' % str(e))
            print('#----------------------------------------------------#')
            choice = input(PROMPT_STR)


        elif choice == '6':  # delete a line of data from the storage file given the keyword
            table_name = input('please input the name of the table to be deleted from:')
            field_input = input('please input the field name and the corresponding keyword (fieldname:keyword):')
            
            if ":" in field_input:
                field_name, field_value = field_input.split(":", 1)
                field_name = field_name.strip()
                field_value = field_value.strip()
                
                if schemaObj.find_table(table_name.strip()):
                    dataObj = storage_db.Storage(table_name.strip())
                    field_list = dataObj.getFieldList()
                    
                    field_index = -1
                    for i, field in enumerate(field_list):
                        fname = field[0].strip()
                        if isinstance(fname, bytes):
                            fname = fname.decode('utf-8')
                        if fname == field_name:
                            field_index = i
                            break
                    
                    if field_index == -1:
                        print(f"Field '{field_name}' does not exist in table '{table_name.strip()}'")
                    else:
                        deleted_count = dataObj.delete_record(field_index, field_value)
                        
                        if deleted_count > 0:
                            print(f"Deleted {deleted_count} record(s).")
                            print("\nCurrent data in the table:")
                            dataObj.show_table_data()
                        else:
                            print(f"No matching records found.")
                    
                    del dataObj
                else:
                    print(f'Table {table_name.strip()} does not exist')
            else:
                print("Input format error! Correct format: fieldname:keyword")

            choice = input(PROMPT_STR)

        elif choice == '7':  # update a line of data given the keyword
            table_name = input('please input the name of the table:')
            field_name = input('please input the field name:')
            keyword = input('please input the keyword to identify the row:')
            update_field = input('please input the field name to be updated:')
            update_value = input('please input the new value:')
            
            if schemaObj.find_table(table_name.strip()):
                dataObj = storage_db.Storage(table_name.strip())
                field_list = dataObj.getFieldList()
                
                condition_field_index = -1
                update_field_index = -1
                
                for i, field in enumerate(field_list):
                    fname = field[0].strip()
                    if isinstance(fname, bytes):
                        fname = fname.decode('utf-8')
                    if fname == field_name:
                        condition_field_index = i
                    if fname == update_field:
                        update_field_index = i
                
                if condition_field_index == -1:
                    print(f"Field '{field_name}' does not exist in table '{table_name.strip()}'")
                elif update_field_index == -1:
                    print(f"Field '{update_field}' does not exist in table '{table_name.strip()}'")
                else:
                    field_type = field_list[update_field_index][1]
                    max_length = field_list[update_field_index][2]
                    
                    valid, converted_value, error_msg = common_db.validate_and_convert_value(update_value, field_type, max_length)
                    
                    if valid:
                        updated_count = dataObj.update_record(
                            condition_field_index, 
                            keyword, 
                            update_field_index, 
                            converted_value,
                            common_db.current_transaction_id
                        )
                        
                        if updated_count > 0:
                            print(f"Updated {updated_count} record(s).")
                            print("\nCurrent data in the table:")
                            dataObj.show_table_data()
                        else:
                            print(f"No matching records found.")
                    else:
                        print(f"Invalid update value: {error_msg}")
                
                del dataObj
            else:
                print(f'Table {table_name.strip()} does not exist')
                
            choice = input(PROMPT_STR)
            
        elif choice == '8':  # begin a transaction
            # 检查是否已有活动事务
            if common_db.current_transaction_id is not None:
                print(f"Transaction {common_db.current_transaction_id} is already active. Commit or abort it before starting a new one.")
            else:
                # 获取事务管理器并开始新事务
                txn_manager = transaction_db.get_transaction_manager()
                common_db.current_transaction_id = txn_manager.begin_transaction()
                print(f"Transaction {common_db.current_transaction_id} started. All subsequent operations will be part of this transaction.")
                print("Use option 9 to commit, or option 10 to abort the transaction.")
            
            choice = input(PROMPT_STR)
            
        elif choice == '9':  # commit transaction
            if common_db.current_transaction_id is None:
                print("No active transaction to commit. Start a transaction with option 8 first.")
            else:
                txn_manager = transaction_db.get_transaction_manager()
                try:
                    txn_manager.commit_transaction(common_db.current_transaction_id)
                    print(f"Transaction {common_db.current_transaction_id} committed successfully.")
                    common_db.current_transaction_id = None
                except Exception as e:
                    print(f"Failed to commit transaction: {str(e)}")
            
            choice = input(PROMPT_STR)
        
        elif choice == '10':  # abort transaction
            if common_db.current_transaction_id is None:
                print("No active transaction to abort. Start a transaction with option 8 first.")
            else:
                txn_manager = transaction_db.get_transaction_manager()
                try:
                    txn_manager.abort_transaction(common_db.current_transaction_id)
                    print(f"Transaction {common_db.current_transaction_id} aborted.")
                    common_db.current_transaction_id = None
                except Exception as e:
                    print(f"Failed to abort transaction: {str(e)}")
            
            choice = input(PROMPT_STR)
        
        elif choice == '11':  # 创建索引
            table_name = input('please input the table name:').strip()
            if not schemaObj.find_table(table_name):
                print(f'Table {table_name} does not exist')
            else:
                field_name = input('please input the field name to index:').strip()
                field_list = schemaObj.viewTableStructure(table_name)
                if field_list is None:
                    print('Failed to get table structure')
                else:
                    found = False
                    for fn in field_list:
                        fn_str = fn[0].strip() if isinstance(fn[0], str) else fn[0].strip().decode('utf-8')
                        if fn_str == field_name:
                            found = True
                            break
                    if not found:
                        print(f"Field '{field_name}' does not exist in table '{table_name}'")
                    else:
                        indexed = index_catalog.get_indexed_fields(table_name)
                        if field_name in indexed:
                            print(f"Index on '{table_name}.{field_name}' already exists")
                        else:
                            idx = index_db.Index(table_name)
                            ok = idx.create_index(field_name)
                            idx.close()
                            if ok:
                                index_catalog.add_index(table_name, field_name)
                                print(f"Index on '{table_name}.{field_name}' created successfully")
                            else:
                                print(f"Failed to create index on '{table_name}.{field_name}'")

            choice = input(PROMPT_STR)

        elif choice == '12':  # 删除索引
            table_name = input('please input the table name:').strip()
            field_name = input('please input the field name to drop index:').strip()
            if index_catalog.remove_index(table_name, field_name):
                print(f"Index on '{table_name}.{field_name}' dropped successfully")
            else:
                print(f"No index found on '{table_name}.{field_name}'")

            choice = input(PROMPT_STR)

        elif choice == '13':  # 查看所有索引
            all_indexes = index_catalog.list_all_indexes()
            if not all_indexes:
                print('No indexes found')
            else:
                print('Indexes:')
                for tname, fname in all_indexes:
                    print(f'  {tname}.{fname}')
            choice = input(PROMPT_STR)
        
        elif choice == '.':
            print('main loop finishies')
            del schemaObj
            break

        else:
            if choice not in ['1','2','3','4','5','6','7','8','9','10','11','12','13']:
                print(f"Invalid choice: '{choice}'. Please enter a number 1-13 or '.' to quit.")

    print('main loop finish!')

if __name__ == '__main__':
    main()
