#---------------------------------
# head_db.py
# author: Jingyu Han    hjymail@163.com
#--------------------------------------
# the main memory structure of table schema
# 
#------------------------------------
class Header(object): 
    def __init__(self,nameList,fieldDict,inistored, inLen, off):
        self.isStored=inistored
        self.lenOfTableNum=inLen
        self.offsetOfBody=off
        self.tableNames=nameList
        self.tableFields=fieldDict
