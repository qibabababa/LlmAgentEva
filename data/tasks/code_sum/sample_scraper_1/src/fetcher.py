import logging
import requests

from .config import TIMEOUT, MAX_PAGE_SIZE, HEADERS

logger = logging.getLogger(__name__)

def fetch_html(url: str) -> str:
    """
    下载指定 URL 的 HTML 文本。
    超出 MAX_PAGE_SIZE 时截断。
    """
    resp = requests.get(url, timeout=TIMEOUT, headers=HEADERS, stream=True)
    resp.raise_for_status()

    size = 0
    chunks = []
    for chunk in resp.iter_content(chunk_size=8192, decode_unicode=True):
        size += len(chunk)
        if size > MAX_PAGE_SIZE:
            logger.warning("Page truncated: %s", url)
            break
        chunks.append(chunk)
    return "".join(chunks)
