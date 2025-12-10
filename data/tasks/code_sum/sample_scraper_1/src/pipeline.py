"""
命令行入口：串联 fetcher 与 parser。
"""
import argparse
import json
import sys

from .fetcher import fetch_html
from .parser import parse

def main(argv=None):
    parser = argparse.ArgumentParser(description="Simple web info scraper")
    parser.add_argument("url", help="URL to scrape")
    args = parser.parse_args(argv)

    html = fetch_html(args.url)
    data = parse(html)
    print(json.dumps(data, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
