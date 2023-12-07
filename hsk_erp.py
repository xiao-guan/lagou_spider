from flask import Flask, render_template
import pymongo

app = Flask(__name__)

# 设置 MongoDB 连接
client = pymongo.MongoClient('mongodb://127.0.0.1')
mydb = client["lagou"]
ios_col = mydb["ios"]
java_col = mydb["java"]


# 定义路由
@app.route('/')
def index():
    return "测试：<a href='/test'>/test</a>, ios：<a href='/ios'>/ios</a>, java：<a href='/java'>/java</a>"


@app.route('/test')
def test():
    return "这是测试页面"


@app.route('/ios')
def show_ios_data():
    ios_data = ios_col.find()
    return render_template('data.html', data=ios_data)


@app.route('/java')
def show_java_data():
    java_data = java_col.find()
    return render_template('data.html', data=java_data)


if __name__ == '__main__':
    app.run(debug=True)
