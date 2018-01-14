import flask
from flask import request
import redis
import time
import json


'''
为什么用 gunicorn？
subcribe 函数用来做 sse 的，stream() 函数不会结束，
不会返回，python 没有原生的多线程，
gunicorn 是一个 python 的 web 服务器，可以启动 python 程序
有 100 个人同时在线，服务就会有100个进程在服务，同时监听 redis 频道
使用 gunicorn 启动代码，实现并发
实际上，是 gunicorn 接管了服务器，我们的程序只是提供数据，程序挂了，但 gunicorn 在运行
# 使用 gunicorn 启动
gunicorn --worker-class=gevent -t 9999 redischat:app
# 开启 debug 输出
gunicorn --log-level debug --worker-class=gevent -t 999 redis_chat81:app
# 把 gunicorn 输出写入到 gunicorn.log 文件中
gunicorn --log-level debug --access-logfile gunicorn.log --worker-class=gevent -t 999 redis_chat81:app
'''

# 连接上本机的 redis 服务器
# 所以要先打开 redis 服务器
# sqlite 和 mysql 写入和读取数据都要到硬盘读写，速度没那么快
# redis 数据库特点：内存数据库，至少比硬盘速度快 10倍
# redis 是一个独立的服务器，我们只做了发消息，收消息，具体逻辑 redis 做的，我们只是发函数
# 实际上是一个存储字典的服务器，字典存储很快
red = redis.Redis(host='localhost', port=6379, db=0)
print('redis', red)

app = flask.Flask(__name__)
app.secret_key = 'key'

# 发布聊天广播的 redis 频道
chat_channel = 'chat'


def stream():
    '''
    监听 redis 广播并 sse 到客户端
    '''
    # 对每一个用户 创建一个[发布订阅]对象
    pubsub = red.pubsub()
    # 订阅广播频道
    pubsub.subscribe(chat_channel)
    # 监听订阅的广播， 每个人都会监听这个频道
    for message in pubsub.listen():
        print(message)
        if message['type'] == 'message':
            data = message['data'].decode('utf-8')
            # 用 sse 返回给前端，yield 相当于 return，
            # 但是并不结束，下一次调用到下一个
            yield 'data: {}\n\n'.format(data)


@app.route('/subscribe')
def subscribe():
    # 规定发送给前端数据的类型，如果是'text/event-stream'类型，
    # 浏览器和你的连接不会断开
    # stream()函数 给浏览器发消息以 yield 的形式发送的
    return flask.Response(stream(),
                          mimetype="text/event-stream")


@app.route('/')
def index_view():
    return flask.render_template('index.html')


def current_time():
    return int(time.time())


@app.route('/chat/add', methods=['POST'])
def chat_add():
    msg = request.get_json()
    name = msg.get('name', '')
    if name == '':
        name = '<匿名>'
    content = msg.get('content', '')
    channel = msg.get('channel', '')
    r = {
        'name': name,
        'content': content,
        'channel': channel,
        'created_time': current_time(),
    }
    message = json.dumps(r, ensure_ascii=False)
    print('debug', message)
    # 用 redis 发布消息，前端接收服务器数据的方式是被动的
    red.publish(chat_channel, message)
    return 'OK'


if __name__ == '__main__':
    config = dict(
        host= '0.0.0.0',
        debug=True,
    )
    app.run(**config)
