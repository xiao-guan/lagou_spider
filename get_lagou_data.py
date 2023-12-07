# -*- coding: utf-8 -*-

import threading
import json
import time

import pymongo
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import requests

with open("setting.json", "r", encoding="utf8") as config:
    config_data = json.load(config)

client = pymongo.MongoClient('mongodb://127.0.0.1')
# 创建一个锁对象
lock = threading.Lock()

# 设置最大线程数
max_threads = config_data["thread_num"]

# 创建一个Semaphore，初始值为最大线程数
thread_semaphore = threading.Semaphore(max_threads)


def get_proxy():
    """
    获取代理ip
    :return:
    """
    proxy_ip = json.loads(requests.request("GET", url="http://127.0.0.1:5000/get_proxy").text)
    return proxy_ip['proxy']


def get_search_list(save_detail=False):
    """
    根据setting.json获取数据列表
    keyword: 岗位关键字
    city: 城市
    pageNo: 一页大概十四行数据
    :return:
    """
    payload = config_data["payload"]
    proxy_ip = {'http': 'http://127.0.0.1:7890', 'https': 'http://127.0.0.1:7890'}
    for keyword in payload["keywords"]:
        for city in payload["city"]:
            for i in range(int(payload["pageNo"])):
                # proxy_ip = {"http": get_proxy()}
                # if not proxy_ip["http"]:
                #     proxy_ip = proxy_ip["http"]
                data = {"keyword": keyword, "city": city, "pageNo": i}
                response = None
                while not response:
                    try:
                        time.sleep(1)
                        # proxies = proxy_ip,
                        response = requests.request("GET", config_data["url"], headers=config_data["headers"],
                                                    params=data, proxies=proxy_ip, timeout=10)
                    except requests.exceptions.ProxyError as e:
                        proxy_ip = get_proxy()

                # 使用 Beautiful Soup 解析页面源代码
                soup = BeautifulSoup(response.text, 'html.parser')
                # 当前页面为空则换个城市搜索
                page_element = soup.find('div', class_='mK9Xu')
                if page_element:
                    break
                # 定位到指定的 script 元素
                script_element = soup.find('script', id='__NEXT_DATA__')

                # 提取该元素的文本内容
                if script_element:
                    script_content = script_element.text
                    # 在这里你可以对 script_content 进行进一步处理

                    # 打印或返回文本内容
                    contents = json.loads(script_content)["props"]["pageProps"]["positionCardVos"]
                    # 保存到mongodb
                    positionId_list = save_list_page_to_mongodb(contents)
                    if save_detail:
                        for positionId in positionId_list:
                            def save_detail():
                                # 等待获取Semaphore的许可
                                # with thread_semaphore:
                                detail = None
                                free_proxy = False
                                while not detail:
                                    try:
                                        detail = get_search_detail(positionId, free_proxy)
                                    except Exception as e:
                                        free_proxy = not free_proxy
                                    else:
                                        with lock:
                                            save_detail_page_to_mongodb(detail)
                            save_detail()
                            time.sleep(1)
                            # 开线程大概率被封ip，不开线程又非常慢
                            # update_thread = threading.Thread(target=save_detail)
                            # update_thread.start()
                else:
                    return False
    return True


def connect_lagou_collection():
    """
    打开lagou库的lagou集合
    :return:
    """
    mydb = client["lagou"]
    mycol = mydb["cplusplus"]
    return mycol


def save_list_page_to_mongodb(contents):
    """
    :param contents: 根据positionId去保存列表页的内容
    :return:
    """
    positionId_list = []
    mycol = connect_lagou_collection()
    mycol.create_index([("positionId", pymongo.ASCENDING)], unique=True)
    for content in contents:
        new_dict = {"positionId": content["positionId"],
                    "companyId": content["companyId"],
                    "positionName": content["positionName"],
                    "companyName": content["companyName"],
                    "companySize": content["companySize"],
                    "city": content["city"],
                    "salary": content["salary"],
                    "salaryMonth": content["salaryMonth"],
                    "workYear": content["workYear"],
                    "education": content["education"]}
        positionId_list.append(content["positionId"])
        mycol.update_one(
            {"positionId": content["positionId"]},  # filter条件
            {"$set": new_dict},  # 更新或插入的数据
            upsert=True  # 如果找不到匹配的文档，就插入新的文档
        )

    return positionId_list


def save_detail_page_to_mongodb(content):
    """
    这个页面反爬得厉害，没钱买好用的动态ip可能爬不了
    :param contents: 根据positionId去保存详情页的内容
    :return:
    """
    new_dict = {"positionId": content["positionId"],
                "jobDetail": content["jobDetail"],
                "hrName": content["hrName"],
                "timeInfo": content["timeInfo"]}
    print(new_dict)
    mycol = connect_lagou_collection()
    mycol.update_one({"positionId": content["positionId"]}, {"$set": new_dict})


def get_search_detail(positionId, free_proxy):
    chrome_options = Options()
    # 开启静默模式
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-application-cache")
    # prefs = {"profile.managed_default_content_settings.images": 2}
    # chrome_options.add_experimental_option("prefs", prefs)
    chrome_options.add_argument("--ignore-certificate-errors")
    # chrome_options.page_load_strategy = 'eager'
    # if free_proxy:
    #     proxy_ip = get_proxy()
    #     chrome_options.add_argument(f"--proxy-server=http://{proxy_ip}")
    # else:
    # chrome_options.add_argument("--proxy-server=http://192.168.1.87:7890")
    # chrome_options.add_argument("--proxy-server=http://127.0.0.1:7890")
    # chrome_options.add_argument("--proxy-server=https://127.0.0.1:7890")
    browser = webdriver.Chrome(chrome_options)
    browser.get(f'https://www.lagou.com/wn/jobs/{positionId}.html')
    page_source = browser.page_source
    # 使用 Beautiful Soup 解析页面源代码
    soup = BeautifulSoup(page_source, 'html.parser')
    # 使用 XPath 定位到元素
    detail_dict = {"positionId": positionId,
                   "hrName": soup.find('div', class_='publisher_name').find('span').text,
                   "timeInfo": soup.find('span', id="timeInfo").text,
                   "jobDetail": soup.find('dd', class_='job_bt').find('div').text.replace('\n', '')}
    return detail_dict


def main():
    get_search_list(False)


if __name__ == '__main__':
    main()
