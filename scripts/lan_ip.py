"""打印本机在局域网中的 IPv4 地址（取默认出口网卡）。"""
from __future__ import annotations

import socket


def main() -> None:
    ip = ""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.settimeout(1.0)
        s.connect(("8.8.8.8", 80))      # 只为查路由，不真的发包
        ip = s.getsockname()[0]
    except OSError:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except OSError:
            ip = ""
    finally:
        s.close()
    print(ip)


if __name__ == "__main__":
    main()
