# coding=utf-8
import logging
import logging.config
import os
import threading
import argparse
import json
import redis
import pydevd

# 创建一个logger
if os.path.exists('logging.conf'):
    logging.config.fileConfig('logging.conf')
else:
    logging.basicConfig()
logger = logging.getLogger('surveillance')

from camera import Camera


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--conf", required=True,
                    help="path to the JSON configuration file")
    args = vars(ap.parse_args())
    return args


def load_config(configpath):
    conf = json.load(configpath)
    return conf


class Looper(threading.Thread):
    def __init__(self, redis, conf):
        threading.Thread.__init__(self)
        self.redis = redis
        self.conf = conf

    def run(self):
        camera = Camera(self.conf, self.redis)
        camera.camera_init()
        camera.dynamic_capture()
        camera.camera_stop()


class Surveillance():
    def __init__(self, r, channels, conf):
        self.redis = r
        self.pubsub = self.redis.pubsub()
        self.pubsub.subscribe(channels)
        self.looper = None
        self.redis.set('RUNNING', 'false')
        self.conf = conf

    def work(self, item):
        print item['channel'], ":", item['data']

    def run(self):
        for item in self.pubsub.listen():
            if item['data'] == "KILL":
                if self.looper is not None:
                    value = self.redis.get("STOPFLAG")
                    if value is None or value == 'false':
                        # set flag, looper exit
                        self.redis.set("STOPFLAG", "true")
                        # wait for loop end
                        self.looper.join()
                        self.looper = None
                        logger.info('clear thread')
                    else:
                        logger.info('stop in progress')
                else:
                    logger.info("none for stop")
            if item['data'] == 'START':
                if self.looper is None:
                    self.redis.set("STOPFLAG", "false")
                    self.looper = Looper(self.redis, self.conf)
                    self.looper.start()
                else:
                    logger('already running')
            else:
                self.work(item)


if __name__ == "__main__":
    # pydevd.settrace('192.168.199.168', port=50000, stdoutToServer=True, stderrToServer=True)
    args = parse_args()
    # 加载配置文件
    conf = load_config(open(args["conf"]))
    logger.info('connecting to redis')
    r = redis.Redis('localhost', '6379')
    logger.info('redis connected')
    client = Surveillance(r, ['test'], conf)
    logger.info('start listener ')
    client.run()
