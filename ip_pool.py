import time
import redis
import requests
from flask import Flask, jsonify
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from selenium.webdriver.common.by import By
import datetime
import threading

app = Flask(__name__)

# 创建一个锁对象
lock = threading.Lock()
# 创建应用上下文
app.app_context().push()

# 全局变量
available_ips = []
proxies_count = 0
# 连接到Redis
redis_client = redis.StrictRedis(host='192.168.1.134', port=6379, decode_responses=True)


def get_checkerproxy_data():
    """
    获取 https://checkerproxy.net 网站的免费代理
    :return:
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")

    # 初始化一个浏览器驱动（无头模式）
    driver = webdriver.Chrome(options=chrome_options)
    appointed_time = str(datetime.date.today() + datetime.timedelta())
    # 打开目标网页
    url = f"https://checkerproxy.net/archive/{appointed_time}"
    driver.get(url)

    # 等待一段时间，确保页面完全加载（你可能需要根据实际情况调整等待时间）
    driver.implicitly_wait(10)
    time.sleep(5)
    # 通过ID定位到textarea元素并获取内容
    textarea = driver.find_element(By.ID, "find_result")
    content = textarea.get_attribute("value")

    # 关闭浏览器
    driver.quit()

    # 保存获取到的代理
    with open("useful_ip.txt", "w", encoding="utf8") as f2:
        f2.write(content)


def check_proxy(ip):
    """
    测试ip的可用性
    :param ip:
    :return:

    """
    url = "https://www.baidu.com"
    try:
        html = requests.request("GET", url, proxies={'http': ip}, timeout=10)
        if html.status_code == 200:
            return True
    except Exception as e:
        pass
    return False


def save_to_redis(ip):
    """
    保存ip
    :param ip:
    :return:
    """
    redis_client.sadd('available_proxies', ip)


def get_proxy_from_redis():
    """
    获取ip
    :return:
    """
    return redis_client.spop('available_proxies')


# 读取并检查代理文件
def load_proxies_from_file(filename):
    with open(filename, 'r') as file:
        proxies = file.read().splitlines()
    return proxies


def save_proxies_to_file(filename, proxies):
    with open(filename, 'w') as file:
        file.write('\n'.join(proxies))


def get_and_remove_top_n_proxies(filename, n):
    proxies = load_proxies_from_file(filename)
    top_n_proxies = proxies[:n]
    del proxies[:n]
    save_proxies_to_file(filename, proxies)
    return top_n_proxies


def one_pencent_get_proxy():
    available_ips = get_and_remove_top_n_proxies('useful_ip.txt', 30)
    if not available_ips:
        get_checkerproxy_data()
        available_ips = get_and_remove_top_n_proxies('useful_ip.txt', 30)
    return available_ips


@app.route('/get_proxy')
def get_proxy():
    global available_ips  # 声明为全局变量
    # 读取并检查代理文件
    proxies_count = len(redis_client.smembers('available_proxies'))

    def update_proxies():
        global available_ips  # 声明为全局变量
        global proxies_count  # 声明为全局变量
        with lock:
            available_ips = one_pencent_get_proxy()
            while proxies_count < 30 and available_ips:
                ip = available_ips.pop()
                if check_proxy(ip):
                    save_to_redis(ip)
                    proxies_count += 1
                if not available_ips:
                    available_ips = one_pencent_get_proxy()

    if proxies_count < 20:
        # 开启一个新线程来执行循环
        update_thread = threading.Thread(target=update_proxies)
        update_thread.start()

    return jsonify({"proxy": get_proxy_from_redis()})


if __name__ == '__main__':
    app.run(debug=True)