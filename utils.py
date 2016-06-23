# coding=utf-8
# 导入必要的包
import uuid
import os


class TempImage:
    def __init__(self, basePath=".", ext=".jpg"):
        # 创建文件路径
        self.path = "{base_path}/{rand}{ext}".format(base_path=basePath,
                                                     rand=str(uuid.uuid4()), ext=ext)

    def cleanup(self):
        # 删除文件
        os.remove(self.path)
