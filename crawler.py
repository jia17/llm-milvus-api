#!/usr/bin/env python3
"""
KubeSphere开发指南爬虫
抓取https://dev-guide.kubesphere.io/extension-dev-guide/zh/的所有内容
"""

import requests
from bs4 import BeautifulSoup
import time
import os
from urllib.parse import urljoin, urlparse
from pathlib import Path
import json
import html2text
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class KubeSphereDocCrawler:
    def __init__(self, base_url="https://dev-guide.kubesphere.io/extension-dev-guide/zh/"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.visited_urls = set()
        self.content_data = []
        self.h2md = html2text.HTML2Text()
        self.h2md.ignore_links = False
        self.h2md.ignore_images = False
        
        # 确保data目录存在
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
    
    def fetch_page(self, url):
        """获取页面内容"""
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 404:
                logging.warning(f"页面不存在 {url}")
                return None
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logging.error(f"获取页面失败 {url}: {e}")
            return None
    
    def extract_navigation_links(self, html_content, base_url):
        """提取导航菜单中的所有链接"""
        soup = BeautifulSoup(html_content, 'html.parser')
        links = set()
        
        # 预定义的主要章节路径
        main_sections = [
            "/extension-dev-guide/zh/overview/",
            "/extension-dev-guide/zh/quickstart/", 
            "/extension-dev-guide/zh/feature-customization/",
            "/extension-dev-guide/zh/examples/",
            "/extension-dev-guide/zh/packaging-and-release/",
            "/extension-dev-guide/zh/best-practices/",
            "/extension-dev-guide/zh/FAQ/",
            "/extension-dev-guide/zh/migration/",
            "/extension-dev-guide/zh/references/"
        ]
        
        # 添加预定义的主要章节
        for section in main_sections:
            full_url = urljoin(base_url, section)
            links.add(full_url)
        
        # 查找页面中的所有内部链接
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('/extension-dev-guide/zh/'):
                full_url = urljoin(base_url, href)
                links.add(full_url)
            elif href.startswith('http') and 'dev-guide.kubesphere.io/extension-dev-guide/zh/' in href:
                links.add(href)
        
        # 额外检查可能的子页面
        subsection_patterns = [
            "overview", "quickstart", "feature-customization", "examples", 
            "packaging-and-release", "best-practices", "FAQ", "migration", "references"
        ]
        
        for pattern in subsection_patterns:
            # 检查每个主要章节的可能子页面
            potential_urls = [
                f"/extension-dev-guide/zh/{pattern}/",
                f"/extension-dev-guide/zh/{pattern}/index.html",
                f"/extension-dev-guide/zh/{pattern}.html"
            ]
            for url_path in potential_urls:
                full_url = urljoin(base_url, url_path)
                links.add(full_url)
        
        return list(links)
    
    def extract_content(self, html_content, url):
        """提取页面主要内容"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 移除导航、侧边栏、脚注等
        for element in soup.find_all(['nav', 'aside', 'footer', 'header']):
            element.decompose()
        
        # 移除脚本和样式
        for element in soup.find_all(['script', 'style']):
            element.decompose()
        
        # 查找主要内容区域
        main_content = (
            soup.find('main') or 
            soup.find('article') or 
            soup.find('div', class_=lambda x: x and 'content' in x.lower()) or
            soup.find('div', id=lambda x: x and 'content' in x.lower()) or
            soup.body
        )
        
        if not main_content:
            return None, None
        
        # 提取标题
        title_elem = soup.find('h1') or soup.find('title')
        title = title_elem.get_text().strip() if title_elem else urlparse(url).path.split('/')[-1]
        
        # 转换为markdown
        markdown_content = self.h2md.handle(str(main_content))
        
        return title, markdown_content
    
    def crawl_all_pages(self):
        """爬取所有页面"""
        logging.info("开始爬取KubeSphere开发指南...")
        
        # 获取首页
        html_content = self.fetch_page(self.base_url)
        if not html_content:
            logging.error("无法获取首页内容")
            return
        
        # 提取所有链接
        all_links = self.extract_navigation_links(html_content, self.base_url)
        all_links.append(self.base_url)  # 包含首页
        
        logging.info(f"发现 {len(all_links)} 个页面链接")
        
        # 爬取每个页面
        for i, url in enumerate(all_links, 1):
            if url in self.visited_urls:
                continue
                
            logging.info(f"正在爬取 ({i}/{len(all_links)}): {url}")
            html_content = self.fetch_page(url)
            
            if html_content:
                title, content = self.extract_content(html_content, url)
                if title and content:
                    self.content_data.append({
                        'url': url,
                        'title': title,
                        'content': content
                    })
                    self.visited_urls.add(url)
            
            # 礼貌等待
            time.sleep(1)
        
        logging.info(f"爬取完成，共获取 {len(self.content_data)} 个页面内容")
    
    def save_as_markdown(self):
        """保存为markdown文档"""
        output_path = self.data_dir / "kubesphere_dev_guide.md"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# KubeSphere扩展开发指南\n\n")
            f.write("本文档来源：https://dev-guide.kubesphere.io/extension-dev-guide/zh/\n\n")
            f.write("---\n\n")
            
            for page in self.content_data:
                f.write(f"# {page['title']}\n\n")
                f.write(f"来源：{page['url']}\n\n")
                f.write(page['content'])
                f.write("\n\n---\n\n")
        
        logging.info(f"Markdown文档已保存到: {output_path}")
        return output_path
    
    def save_as_pdf(self):
        """保存为PDF文档"""
        try:
            output_path = self.data_dir / "kubesphere_dev_guide.pdf"
            doc = SimpleDocTemplate(str(output_path), pagesize=letter)
            styles = getSampleStyleSheet()
            
            # 创建支持中文的样式
            title_style = ParagraphStyle(
                'ChineseTitle',
                parent=styles['Heading1'],
                fontName='Helvetica-Bold',
                fontSize=16,
                spaceAfter=12,
                alignment=TA_LEFT
            )
            
            body_style = ParagraphStyle(
                'ChineseBody',
                parent=styles['Normal'],
                fontName='Helvetica',
                fontSize=10,
                spaceAfter=6,
                alignment=TA_LEFT
            )
            
            story = []
            
            # 添加文档标题
            story.append(Paragraph("KubeSphere扩展开发指南", title_style))
            story.append(Spacer(1, 12))
            
            for page in self.content_data:
                # 页面标题
                story.append(Paragraph(page['title'], title_style))
                story.append(Spacer(1, 6))
                
                # 来源URL
                story.append(Paragraph(f"来源：{page['url']}", body_style))
                story.append(Spacer(1, 6))
                
                # 内容（简化处理，去掉markdown格式）
                clean_content = page['content'].replace('#', '').replace('*', '').replace('`', '')
                paragraphs = clean_content.split('\n\n')
                
                for para in paragraphs[:20]:  # 限制段落数量避免PDF过大
                    if para.strip():
                        story.append(Paragraph(para.strip(), body_style))
                        story.append(Spacer(1, 3))
                
                story.append(Spacer(1, 12))
            
            doc.build(story)
            logging.info(f"PDF文档已保存到: {output_path}")
            return output_path
            
        except Exception as e:
            logging.error(f"PDF生成失败: {e}")
            return None

def main():
    """主函数"""
    crawler = KubeSphereDocCrawler()
    
    # 爬取所有页面
    crawler.crawl_all_pages()
    
    if not crawler.content_data:
        logging.error("没有获取到任何内容")
        return
    
    # 保存为markdown
    md_path = crawler.save_as_markdown()
    
    # 保存为PDF
    pdf_path = crawler.save_as_pdf()
    
    print(f"\n爬取完成！")
    print(f"📄 Markdown文档: {md_path}")
    if pdf_path:
        print(f"📄 PDF文档: {pdf_path}")
    print(f"📊 共爬取 {len(crawler.content_data)} 个页面")

if __name__ == "__main__":
    main()