import os

# 默认超时时间（秒）
TIMEOUT = int(os.getenv("SCRAPER_TIMEOUT", "10"))

# 允许爬取的最大页面大小（字节）
MAX_PAGE_SIZE = int(os.getenv("SCRAPER_MAX_SIZE", "1048576"))  # 1 MB

# User-Agent
HEADERS = {
    "User-Agent": os.getenv(
        "SCRAPER_UA",
        "SampleScraper/0.1 (+https://example.com/bot)"
    )
}
