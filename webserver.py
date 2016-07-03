# coding=utf-8
import calendar
from datetime import tzinfo, timedelta, datetime

import leancloud
import redis
import time
from flask import Flask
from flask import redirect, url_for
from flask import render_template

app = Flask(__name__)
redis = redis.Redis('localhost', '6379')
# leancloud初始化
leancloud.init("jMR24M2bameqyYIDN4xuN65a-gzGzoHsz", "N7F5T0FN125WWa9GfbLWmArP")


@app.route("/")
def index():
    value = redis.get('RUNNING')
    if value == 'true':
        running = True
    else:
        running = False
    return render_template('index.html', running=running)


@app.route("/start")
def start():
    redis.publish('test', 'START')
    time.sleep(3)
    return redirect(url_for('index'))


@app.route("/stop")
def stop():
    redis.publish('test', 'KILL')
    time.sleep(3)
    return redirect(url_for('index'))


@app.route('/photos')
def list():
    File = leancloud.Object.extend('_File')
    query = File.query
    query.add_descending('createdAt').limit(50)
    photos = ({'name': p.get('name'), 'url': p.get('url'),
               'created_at': convert_time(p.created_at)} for p in query.find())
    return render_template('snapshot.html', photos=photos)


def convert_time(c_time):
    assert isinstance(c_time, datetime)
    if c_time:
        # get integer timestamp to avoid precision lost
        timestamp = calendar.timegm(c_time.timetuple())
        local_dt = datetime.fromtimestamp(timestamp)
        return local_dt.strftime('%Y-%m-%d %H:%M:%S')
    else:
        return ''


if __name__ == "__main__":
    app.run(host='0.0.0.0')
