# coding=utf-8
import argparse
import json
import logging

import imutils
# import pydevd
import cv2
import datetime
from picamera.array import PiRGBArray
from picamera import PiCamera

from utils import TempImage
import time
import leancloud

# leancloud初始化
leancloud.init("jMR24M2bameqyYIDN4xuN65a-gzGzoHsz", "N7F5T0FN125WWa9GfbLWmArP")

# 创建一个logger
logger = logging.getLogger('surveillance')


class Surveillance:
    def __init__(self, conf, redis):
        self.conf = conf
        self.redis = redis
        self.camera = None
        self.rawCapture = None
        self.avg = None
        self.motionCounter = 0
        self.lastUploaded = None

    def camera_init(self):
        camera = PiCamera()
        camera.resolution = tuple(self.conf["resolution"])
        camera.framerate = self.conf["fps"]
        camera.vflip = self.conf["vertical_flip"]
        camera.hflip = self.conf["horizontal_flip"]
        self.rawCapture = PiRGBArray(camera, size=tuple(self.conf["resolution"]))

        # 等待摄像头模块启动, 随后初始化平均帧, 最后
        # 上传时间戳, 以及运动帧计数器
        logger.info("warming up...")
        time.sleep(self.conf["camera_warmup_time"])
        self.redis.set('CAMERA_INITED', 'true')
        self.avg = None
        self.lastUploaded = datetime.datetime.now()
        self.motionCounter = 0
        self.camera = camera

    def camera_stop(self):
        value = self.redis.get('CAMERA_INITED')
        if value is not None and value == 'true':
            logger.info('stoping camera')
            self.camera.close()
            self.camera = None
            logger.info('camera stopped')
        else:
            logger.warn('pls init camera first')

    def dynamic_capture(self):
        value = self.redis.get('CAMERA_INITED')
        if value is None or value == 'false':
            logger.warn('pls init camera first')
            return
        logger.info('start dynamic capture')
        # 从摄像头逐帧捕获数据
        for f in self.camera.capture_continuous(self.rawCapture, format="bgr", use_video_port=True):
            value = self.redis.get("STOPFLAG")
            if value == 'true':
                self.redis.set('RUNNING', 'false')
                logger.info('end looper thread')
                break
            else:
                self.redis.set('RUNNING', 'true')
                try:
                    # 抓取原始NumPy数组来表示图像并且初始化
                    # 时间戳以及occupied/unoccupied文本
                    frame = f.array
                    timestamp = datetime.datetime.now()
                    text = "Unoccupied"

                    # 调整帧尺寸，转换为灰阶图像并进行模糊
                    frame = imutils.resize(frame, width=500)
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    gray = cv2.GaussianBlur(gray, (21, 21), 0)

                    # 如果平均帧是None，初始化它
                    if self.avg is None:
                        logger.info("starting background model...")
                        self.avg = gray.copy().astype("float")
                        self.rawCapture.truncate(0)
                        continue

                    # accumulate the weighted average between the current frame and
                    # previous frames, then compute the difference between the current
                    # frame and running average
                    cv2.accumulateWeighted(gray, self.avg, 0.5)
                    frame_delta = cv2.absdiff(gray, cv2.convertScaleAbs(self.avg))

                    # 对变化图像进行阀值化, 膨胀阀值图像来填补
                    # 孔洞, 在阀值图像上找到轮廓线
                    thresh = cv2.threshold(frame_delta, self.conf["delta_thresh"], 255,
                                           cv2.THRESH_BINARY)[1]
                    thresh = cv2.dilate(thresh, None, iterations=2)
                    (cnts, _) = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL,
                                                 cv2.CHAIN_APPROX_SIMPLE)

                    # 遍历轮廓线
                    for c in cnts:
                        # if the contour is too small, ignore it
                        if cv2.contourArea(c) < self.conf["min_area"]:
                            continue

                        # 计算轮廓线的外框, 在当前帧上画出外框,
                        # 并且更新文本
                        (x, y, w, h) = cv2.boundingRect(c)
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                        text = "Occupied"

                    # 在当前帧上标记文本和时间戳
                    ts = timestamp.strftime("%A %d %B %Y %I:%M:%S%p")
                    cv2.putText(frame, "Room Status: {}".format(text), (10, 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                    cv2.putText(frame, ts, (10, frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX,
                                0.35, (0, 0, 255), 1)

                    # check to see if the room is occupied
                    if text == "Occupied":
                        # 检查是否符合大于最小上传间隔
                        if (timestamp - self.lastUploaded).seconds >= self.conf["min_upload_seconds"]:
                            # increment the motion counter
                            self.motionCounter += 1

                            # 当发现有变化的帧数大于设定值,就认为是有改变,决定上传
                            if self.motionCounter >= self.conf["min_motion_frames"]:
                                #  检查是否需要上传云存储
                                if self.conf["use_leancloud"]:
                                    # write the image to temporary file
                                    t = TempImage()
                                    cv2.imwrite(t.path, frame)
                                    try:
                                        with open(t.path) as f:
                                            avatar = leancloud.File(t.path, f)
                                            avatar.save()
                                    except Exception:
                                        logger.exception("upload leancloud error")
                                    finally:
                                        t.cleanup()

                                # 更新最后的update时间,避免频繁上传
                                self.lastUploaded = timestamp
                                # 上传后清空帧计数
                                self.motionCounter = 0

                    # otherwise, the room is not occupied
                    else:
                        self.motionCounter = 0

                    # clear the stream in preparation for the next frame
                    self.rawCapture.truncate(0)
                except BaseException:
                    logger.exception('exception happend')
        logger.info('end dynamic capture')


if __name__ == "__main__":
    pass
