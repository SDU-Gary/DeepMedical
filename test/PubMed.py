import requests
import re
import os
from bs4 import BeautifulSoup


def pubmed_crawler():
    key = input("请输入你想查找的信息：")
    local_folder = input("请输入你想存储的文件夹位置：")
    if not os.path.exists(local_folder):
        os.makedirs(local_folder)
    
    turl = "https://pubmed.ncbi.nlm.nih.gov/"
    tdata = requests.get(turl, params={"term": key}).text
    
    pat_alldocu = '<span class="value">(.*?)</span>'
    alldocu = re.compile(pat_alldocu, re.S).findall(tdata)
    
    num = int(input("请输入大致想获取的文章数目（总数为" + str(alldocu[0]) + "):"))
    
    downloaded_count = 0  # 记录已下载的文章数
    max_page = 50  # 最大页数限制，防止无限循环
    page = 1  # 当前页码
    
    # 持续爬取，直到获取足够数量的文章或达到最大页数限制
    while downloaded_count < num and page <= max_page:
        url = f"https://pubmed.ncbi.nlm.nih.gov/?term={key}&page={page}"
        print(f"正在处理第{page}页...")
        data = requests.get(url).text
        
        # 提取文章链接
        pat1_content_url = '<div class="docsum-wrap">.*?<.*?href="(.*?)".*?</a>'
        content_url = re.compile(pat1_content_url, re.S).findall(data)
        
        # 检查是否找到文章链接
        if not content_url:
            print(f"第{page}页没有找到文章链接，可能已到达最后一页")
            break
        
        hd = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
        # 处理当前页面的每篇文章
        for i in range(len(content_url)):
            # 如果已经下载了足够数量的文章，跳出循环
            if downloaded_count >= num:
                break
                
            # 每处理5篇文章显示一次进度
            if i > 0 and i % 5 == 0:
                print(f"当前进度: 已下载 {downloaded_count}/{num} 篇文章")
    
            curl = "https://pubmed.ncbi.nlm.nih.gov" + content_url[i]
            try:
                cdata = requests.get(curl, headers=hd).text
    
                # 提取PMID
                pmid_match = re.search(r'\/(\d+)\/*$', content_url[i])
                if pmid_match:
                    pmid = pmid_match.group(1)
                else:
                    continue  # 如果没有找到PMID, 跳过这篇文章
    
                pat3_content = '<div class="abstract-content selected".*?>(.*?)</div>'
                content_html = re.compile(pat3_content, re.S).findall(cdata)
                
                # 检查是否找到摘要内容
                if not content_html:
                    print(f"文章 {pmid} 没有找到摘要内容，尝试其他方式提取")
                    # 尝试使用BeautifulSoup直接从页面提取摘要
                    soup = BeautifulSoup(cdata, 'html.parser')
                    abstract_div = soup.select_one('.abstract-content')
                    if abstract_div:
                        content_text = abstract_div.get_text(strip=True)
                    else:
                        print(f"文章 {pmid} 可能没有摘要，跳过")
                        continue
                else:
                    # 使用BeautifulSoup解析找到的HTML，并获取纯文本内容
                    soup = BeautifulSoup(content_html[0], 'html.parser')
                    content_text = soup.get_text(strip=True)
    
                # 使用PMID作为文件名
                file_name = f"{pmid}.txt"
                file_path = os.path.join(local_folder, file_name)
    
                # 写入摘要内容到文件
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(content_text)
    
                downloaded_count += 1  # 成功下载后，计数器增加
    
            except Exception as err:
                print(f"处理文章 {curl} 时出现错误: {err}")
                continue  # 错误时继续尝试下一篇文章
    
        # 完成当前页面处理，增加页码
        page += 1

    # 输出最终结果
    if downloaded_count >= num:
        print(f"爬取完成! 成功下载了指定的 {num} 篇文章。")
    else:
        print(f"爬取完成! 尝试获取 {num} 篇文章, 但仅成功下载了 {downloaded_count} 篇文章。")
        print("可能原因: 搜索结果有限或大部分文章没有摘要。")

if __name__ == "__main__":
    pubmed_crawler()

