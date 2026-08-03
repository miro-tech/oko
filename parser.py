import socket
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

import requests

URL = "https://gist.githubusercontent.com/Darlene-Alderson-FSOCIETY/86fa5f2ad8ff17c182f4009c87c0911b/raw/OkoVPN_Telegram_RE_s_B.txt"

SNI = "turkmenportal.com"


def resolve(host):
    try:
        return socket.gethostbyname(host)
    except:
        return None


text = requests.get(URL, timeout=30).text.strip()

result = []

for line in text.splitlines():
    line = line.strip()

    if not line.startswith("vless://"):
        continue

    p = urlparse(line)

    host = p.hostname
    ip = resolve(host)

    if not ip:
        print(f"Skip {host}")
        continue

    query = dict(parse_qsl(p.query))

    query["host"] = host
    query["sni"] = SNI
    query["allowInsecure"] = "1"

    new_netloc = p.netloc.replace(host, ip, 1)

    new_url = urlunparse((
        p.scheme,
        new_netloc,
        p.path,
        "",
        urlencode(query),
        p.fragment
    ))

    result.append(new_url)

with open("configs.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(result))

print(f"Saved {len(result)} configs")
