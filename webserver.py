# coding=utf-8
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
    photos = query.find()
    return render_template('snapshot.html', photos=photos)


if __name__ == "__main__":
    app.run(host='0.0.0.0')
