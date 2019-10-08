# @Time    : 2019/9/30 9:46
# @Author  : Libuda
# @FileName: aiohttp_spider.py
# @Software: PyCharm
import aiohttp
import asyncio
import aiomysql
from queue import Queue
from pyquery import PyQuery
import re


class Spider:
    def __init__(self):
        self.start_url = 'https://yq.aliyun.com/articles/'
        self.pool = ""
        self.stop = False
        self.waitting_url = Queue()
        self.seen_urls = set()

    def extract_urls(self, html):
        """
        从html中解析url  因为此处是占用cpu而不是占用io  所以在这里不需要使用async
        :return:
        """
        urls = []
        pq = PyQuery(html)
        for link in pq.items("a"):
            url = link.attr("href")
            if url and url.startwith("https") and url not in self.seen_urls:
                urls.append(url)
                self.waitting_url.put(url)
        return urls

    async def article_handler(self, url, session, pool):
        """
        获取文章详情并解析入库
        :param url:
        :param session:
        :return:
        """
        html = await self.fetch(url, session)
        self.seen_urls.add(url)
        self.extract_urls(html)
        pq = PyQuery(html)
        title = pq("#blog-title").text()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                insert_sql = "insert into spider(title) values('{}')".format(title)
                await cur.execute(insert_sql)

    async def consumer(self, pool, session):
        while not self.stop:
            url = self.waitting_url.get()
            if re.match("https://yq.aliyun.com/articles/\d*", url):
                if url not in self.seen_urls:
                    asyncio.ensure_future(self.article_handler(url, session, pool))
            else:
                if url not in self.seen_urls:
                    asyncio.ensure_future(self.init_urls(url, session))

    async def init_urls(self, url, session):
        html = await self.fetch(url, session)
        self.seen_urls.add(url)
        self.extract_urls(html=html)

    async def fetch(self, url, session):
        try:
            async with session.get(url) as response:
                if response.status in [200, 201]:
                    data = await response.text()
                    return data
        except Exception as e:
            print(e)

    async def main(self, loop):
        await aiomysql.create_pool(host="127.0.0.1", port=3306, user='root', password='root', db='aiospider',
                                   loop=loop, charset='utf8', autocommit=True)
        async with aiohttp.ClientSession() as session:
            asyncio.ensure_future(self.init_urls(self.start_url, session))
            asyncio.ensure_future(self.consumer(self.pool, session))

if __name__ == "__main__":
    spider = Spider()
    loop = asyncio.get_event_loop()
    asyncio.ensure_future(spider.main(loop))
    loop.run_forever()
