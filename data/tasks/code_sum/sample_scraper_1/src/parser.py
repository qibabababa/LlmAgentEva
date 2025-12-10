from bs4 import BeautifulSoup
from typing import Dict, List

def parse(html: str) -> Dict[str, List[str]]:
    """
    解析 HTML，返回标题与所有超链接。
    返回示例:
    {
        "title": "Example Domain",
        "links": ["https://www.iana.org/domains/example", ...]
    }
    """
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string.strip() if soup.title else ""
    links = [a["href"] for a in soup.find_all("a", href=True)]
    return {"title": title, "links": links}
