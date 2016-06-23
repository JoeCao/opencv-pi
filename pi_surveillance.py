# coding=utf-8
import argparse
import json

import imutils
import pydevd
import cv2
import datetime
from picamera.array import PiRGBArray
from picamera import PiCamera

from utils import TempImage
import time
import leancloud

leancloud.init("jMR24M2bameqyYIDN4xuN65a-gzGzoHsz", "N7F5T0FN125WWa9GfbLWmArP")


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--conf", required=True,
                    help="path to the JSON configuration file")
    args = vars(ap.parse_args())
    return args


def load_config(configpath):
    conf = json.load(configpath)
    return conf


def camare():
    # 初始化摄像头并且获取一个指向原始数据的引用
    camera = PiCamera()
    camera.resolution = tuple(conf["resolution"])
    camera.framerate = conf["fps"]
    camera.vflip = conf["vertical_flip"]
    camera.hflip = conf["horizontal_flip"]
    rawCapture = PiRGBArray(camera, size=tuple(conf["resolution"]))

    # 等待摄像头模块启动, 随后初始化平均帧, 最后
    # 上传时间戳, 以及运动帧计数器
    print "[INFO] warming up..."
    time.sleep(conf["camera_warmup_time"])
    avg = None
    lastUploaded = datetime.datetime.now()
    motionCounter = 0

    # 从摄像头逐帧捕获数据
    for f in camera.capture_continuous(rawCapture, format="bgr", use_video_port=True):
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
        if avg is None:
            print "[INFO] starting background model..."
            avg = gray.copy().astype("float")
            rawCapture.truncate(0)
            continue

        # accumulate the weighted average between the current frame and
        # previous frames, then compute the difference between the current
        # frame and running average
        cv2.accumulateWeighted(gray, avg, 0.5)
        frameDelta = cv2.absdiff(gray, cv2.convertScaleAbs(avg))

        # 对变化图像进行阀值化, 膨胀阀值图像来填补
        # 孔洞, 在阀值图像上找到轮廓线
        thresh = cv2.threshold(frameDelta, conf["delta_thresh"], 255,
                               cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        (cnts, _) = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL,
                                     cv2.CHAIN_APPROX_SIMPLE)

        # 遍历轮廓线
        for c in cnts:
            # if the contour is too small, ignore it
            if cv2.contourArea(c) < conf["min_area"]:
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
            # check to see if enough time has passed between uploads
            if (timestamp - lastUploaded).seconds >= conf["min_upload_seconds"]:
                # increment the motion counter
                motionCounter += 1

                # check to see if the number of frames with consistent motion is
                # high enough
                if motionCounter >= conf["min_motion_frames"]:
                    # check to see if dropbox sohuld be used
                    if conf["use_leancloud"]:
                        # write the image to temporary file
                        t = TempImage()
                        cv2.imwrite(t.path, frame)
                        try:
                            with open(t.path) as f:
                                avatar = leancloud.File(t.path, f)
                                avatar.save()
                        finally:
                            t.cleanup()

                    # update the last uploaded timestamp and reset the motion
                    # counter
                    lastUploaded = timestamp
                    motionCounter = 0

        # otherwise, the room is not occupied
        else:
            motionCounter = 0

        # check to see if the frames should be displayed to screen
        # if conf["show_video"]:
        #     # display the security feed
        #     cv2.imshow("Security Feed", frame)
        #     key = cv2.waitKey(1) & 0xFF
        #
        #     # if the `q` key is pressed, break from the lop
        #     if key == ord("q"):
        #         break

        # clear the stream in preparation for the next frame
        rawCapture.truncate(0)


if __name__ == "__main__":
    # pydevd.settrace('192.168.199.168', port=50000, stdoutToServer=True, stderrToServer=True)
    # 构建 argument parser 并解析参数
    args = parse_args()
    # 过滤警告，加载配置文件并且初始化Dropbox
    # 客户端
    conf = load_config(open(args["conf"]))
    print conf['resolution']
    camare()
