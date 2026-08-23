#!/usr/bin/env python3

import os
import base64
import json
import random
import re
import time
import uuid
from urllib.parse import quote, urlsplit, urlunsplit, parse_qsl, urlencode

import requests
import urllib3


# ============================================================
# CONFIG
# ============================================================

GIST_ID = os.environ["GIST_ID"]
GITHUB_TOKEN = os.environ["GHUB_TOKEN"]
GIST_FILENAME = "oko.txt"

BACKEND = "https://command.gatoscongress.top"
CABINET = "https://cabinet.capitalabsorb.top"

UA_OKHTTP = "okhttp/4.12.0"
UA_V2RAY = "v2rayNG/1.8.5"

TIMEOUT = 20
CONNECT_TIMEOUT = 12

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)


# ============================================================
# SESSION
# ============================================================

session = requests.Session()

session.headers.update({
    "Accept": "application/json",
})


# ============================================================
# HTTP
# ============================================================

def http_req(method, url, **kwargs):

    headers = kwargs.pop("headers", None)

    try:
        r = session.request(
            method,
            url,
            headers=headers,
            timeout=(CONNECT_TIMEOUT, TIMEOUT),
            allow_redirects=True,
            verify=False,
            **kwargs
        )

        return {
            "code": r.status_code,
            "body": r.text,
            "headers": r.headers,
            "error": None,
        }

    except requests.RequestException as e:

        return {
            "code": 0,
            "body": "",
            "headers": {},
            "error": str(e),
        }


# ============================================================
# UUID
# ============================================================

def gen_uuid_v4():
    return str(uuid.uuid4())


# ============================================================
# STEP 1
# Регистрация устройства
# ============================================================

def register_device():

    device_id = gen_uuid_v4()

    r = http_req(
        "POST",
        BACKEND + "/v1/devices/register",

        headers={
            "Accept": "application/json",
        },

        json={
            "device_id": device_id,
            "platform": "android",
            "os_version": "14",
            "app_version": "1.0.11",
            "push_token": "",
        },
    )

    if r["code"] != 200:

        print(
            f"  [1] REG FAIL "
            f"http={r['code']} "
            f"err={r['error']} "
            f"body={r['body'][:200]}"
        )

        return None

    try:
        data = json.loads(r["body"])

    except json.JSONDecodeError:

        print("  [1] invalid JSON")
        print(r["body"][:500])

        return None

    device_token = data.get("device_token")

    if not device_token:

        print("  [1] no device_token")
        print("      response:", data)

        return None

    print(
        f"  [1] device зарегистрирован: "
        f"{device_id}"
    )

    return {
        "device_id": device_id,
        "device_token": device_token,
    }


# ============================================================
# STEP 2
# Логин по email
# ============================================================

def login_cabinet():

    email = (
        "oko_"
        + str(int(time.time()))
        + "_"
        + str(random.randint(1000, 9999))
        + "@protonmail.com"
    )

    r = http_req(
        "POST",
        CABINET + "/auth/email/start",

        headers={
            "Accept": "application/json",
        },

        json={
            "email": email,
        },
    )

    if r["code"] != 200:

        print(
            f"  [2] LOGIN FAIL "
            f"http={r['code']} "
            f"body={r['body'][:200]}"
        )

        return None

    try:
        data = json.loads(r["body"])

    except json.JSONDecodeError:

        print("  [2] invalid JSON")
        print(r["body"][:500])

        return None

    if not data.get("success"):

        print("  [2] LOGIN not success")
        print("      response:", data)

        return None

    print(f"  [2] логин: {email}")

    return email


# ============================================================
# STEP 3
# Получение subscription URL
# ============================================================

def fetch_sub_url():

    r = http_req(
        "GET",
        CABINET + "/account",

        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(X11; Linux x86_64) "
                "AppleWebKit/537.36"
            ),
        },
    )

    if r["code"] != 200:

        print(
            f"  [3] ACCOUNT FAIL "
            f"http={r['code']}"
        )

        return None

    html = r["body"]

    match = re.search(
        r'id="vpn-access-value"[^>]*>([^<]+)',
        html
    )

    if not match:

        print(
            "  [3] subscription URL "
            "not found on /account"
        )

        return None

    sub_url = match.group(1).strip()

    status = ""
    ends = ""

    m_status = re.search(
        r'subscriptionStatus:\s*"([^"]+)"',
        html
    )

    if m_status:
        status = m_status.group(1)

    m_end = re.search(
        r'subscriptionEnd:\s*"([^"]+)"',
        html
    )

    if m_end:
        ends = m_end.group(1)

    print(
        f"  [3] subscription: {sub_url} "
        f"(status={status}, до {ends})"
    )

    return sub_url


# ============================================================
# STEP 4
# Получение конфигов
# ============================================================

def fetch_configs(sub_url):

    r = http_req(
        "GET",
        sub_url,

        headers={
            "User-Agent": UA_V2RAY,
        },
    )

    if r["code"] != 200:

        print(
            f"  [4] SUB FAIL "
            f"http={r['code']}"
        )

        return None

    body = r["body"]

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    try:
        configs = json.loads(body)

    except json.JSONDecodeError:

        # ----------------------------------------------------
        # Base64 fallback
        # ----------------------------------------------------

        try:

            decoded = base64.b64decode(
                body.strip()
            ).decode(
                "utf-8",
                errors="replace"
            )

        except Exception:

            decoded = ""

        if "://" in decoded:

            print(
                "  [4] получен "
                "base64-формат (fallback)"
            )

            return {
                "__raw_links__": [
                    line.strip()
                    for line in decoded.splitlines()
                    if line.strip()
                ]
            }

        print("  [4] SUB parse fail")

        return None

    if not isinstance(
        configs,
        (list, dict)
    ):

        print("  [4] SUB parse fail")

        return None

    print(
        f"  [4] JSON-конфигов: "
        f"{len(configs)}"
    )

    return configs


# ============================================================
# URL PARAMETER ENCODING
# ============================================================

def encode_kv(params):

    result = []

    for key, value in params.items():

        if value is None or value == "":
            continue

        result.append(
            str(key)
            + "="
            + quote(
                str(value),
                safe=""
            )
        )

    return "&".join(result)


# ============================================================
# REMARK
# ============================================================

def make_remark(addr):

    base = addr.split(".")[0]

    mapping = {
        "us1": "US-us1",
        "nl1": "NL-nl1",
        "fr1": "FR-fr1",
        "sg": "SG-sg",
        "au1": "AT-au1",
        "sp1": "ES-sp1",
        "pl1": "PL-pl1",
        "ru3": "RU-ru3",

        "ruservice2": "RU-ruservice2",
        "ruservice3": "RU-ruservice3",
        "ruservice4": "RU-ruservice4",
        "ruservice5": "RU-ruservice5",
    }

    return mapping.get(
        base,
        base
    )


# ============================================================
# VLESS
# ============================================================

def build_vless_from_outbound(ob):

    settings = ob.get(
        "settings",
        {}
    )

    vnext = settings.get(
        "vnext",
        []
    )

    if not vnext:
        return None

    v = vnext[0]

    users = v.get(
        "users",
        []
    )

    if not users:
        return None

    user = users[0]

    if not all(
        key in v
        for key in (
            "address",
            "port",
        )
    ):
        return None

    if "id" not in user:
        return None

    addr = v["address"]
    port = v["port"]
    uuid_value = user["id"]

    enc = user.get(
        "encryption",
        "none"
    )

    flow = user.get(
        "flow",
        ""
    )

    ss = ob.get(
        "streamSettings",
        {}
    )

    network = ss.get(
        "network",
        "tcp"
    )

    security = ss.get(
        "security",
        "none"
    )

    tls = ss.get(
        "tlsSettings",
        {}
    )

    reality = ss.get(
        "realitySettings",
        {}
    )

    q = {
        "encryption": enc,
    }

    if security and security != "none":
        q["security"] = security

    # ========================================================
    # REALITY
    # ========================================================

    if security == "reality":

        if reality.get("serverName"):
            q["sni"] = reality["serverName"]

        if reality.get("publicKey"):
            q["pbk"] = reality["publicKey"]

        if reality.get("shortId"):
            q["sid"] = reality["shortId"]

        if reality.get("spiderX"):
            q["spx"] = reality["spiderX"]

        if reality.get("fingerprint"):
            q["fp"] = reality["fingerprint"]

        elif tls.get("fingerprint"):
            q["fp"] = tls["fingerprint"]

    # ========================================================
    # TLS
    # ========================================================

    else:

        q["sni"] = (
            tls.get("serverName")
            or addr
        )

        if tls.get("fingerprint"):
            q["fp"] = (
                tls["fingerprint"]
            )

        if tls.get("alpn"):
            q["alpn"] = ",".join(
                tls["alpn"]
            )

    if flow:
        q["flow"] = flow

    q["type"] = network

    # ========================================================
    # XHTTP
    # ========================================================

    if network == "xhttp":

        xh = ss.get(
            "xhttpSettings",
            {}
        )

        q["host"] = xh.get(
            "host",
            addr
        )

        q["path"] = xh.get(
            "path",
            "/"
        )

        mode = xh.get(
            "mode",
            ""
        )

        if mode and mode != "auto":
            q["mode"] = mode

        extra = xh.get(
            "extra",
            {}
        )

        xmux = extra.get(
            "xmux"
        )

        if isinstance(
            xmux,
            dict
        ):

            parts = []

            for key, value in xmux.items():

                if isinstance(
                    value,
                    (dict, list)
                ):

                    value = json.dumps(
                        value,
                        separators=(
                            ",",
                            ":"
                        ),
                        ensure_ascii=False
                    )

                parts.append(
                    f"{key}={value}"
                )

            if parts:
                q["xmux"] = (
                    ",".join(parts)
                )

        if extra.get(
            "xPaddingBytes"
        ):

            q["xPaddingBytes"] = (
                extra["xPaddingBytes"]
            )

        if "noSSEHeader" in extra:

            q["noSSEHeader"] = (
                "true"
                if extra["noSSEHeader"]
                else "false"
            )

        if "noGRPCHeader" in extra:

            q["noGRPCHeader"] = (
                "true"
                if extra["noGRPCHeader"]
                else "false"
            )

        if extra.get(
            "scMaxEachPostBytes"
        ):

            q["scMaxEachPostBytes"] = (
                extra[
                    "scMaxEachPostBytes"
                ]
            )

        if extra.get(
            "scMinPostsIntervalMs"
        ):

            q["scMinPostsIntervalMs"] = (
                extra[
                    "scMinPostsIntervalMs"
                ]
            )

        if extra.get(
            "scStreamUpServerSecs"
        ):

            q["scStreamUpServerSecs"] = (
                extra[
                    "scStreamUpServerSecs"
                ]
            )

    # ========================================================
    # WS
    # ========================================================

    elif network == "ws":

        ws = ss.get(
            "wsSettings",
            {}
        )

        headers = ws.get(
            "headers",
            {}
        )

        q["host"] = headers.get(
            "Host",
            addr
        )

        q["path"] = ws.get(
            "path",
            "/"
        )

    # ========================================================
    # GRPC
    # ========================================================

    elif network == "grpc":

        grpc = ss.get(
            "grpcSettings",
            {}
        )

        if grpc.get(
            "serviceName"
        ):

            q["serviceName"] = (
                grpc["serviceName"]
            )

        if "multiMode" in grpc:

            q["mode"] = (
                "multi"
                if grpc["multiMode"]
                else "gun"
            )

    # ========================================================
    # TCP
    # ========================================================

    elif network == "tcp":

        tcp = ss.get(
            "tcpSettings",
            {}
        )

        header = tcp.get(
            "header",
            {}
        )

        if header.get(
            "type"
        ) == "http":

            q["headerType"] = "http"

            request = header.get(
                "request",
                {}
            )

            headers = request.get(
                "headers",
                {}
            )

            host = headers.get(
                "Host",
                []
            )

            if isinstance(
                host,
                list
            ) and host:

                q["host"] = host[0]

    remark = make_remark(
        addr
    )

    return (
        "vless://"
        + str(uuid_value)
        + "@"
        + str(addr)
        + ":"
        + str(port)
        + "?"
        + encode_kv(q)
        + "#"
        + quote(
            remark,
            safe="@._- "
        )
    )


# ============================================================
# TROJAN
# ============================================================

def build_trojan_from_outbound(ob):

    servers = (
        ob.get("settings", {})
        .get("servers", [])
    )

    if not servers:
        return None

    s = servers[0]

    if not all(
        key in s
        for key in (
            "address",
            "port",
            "password",
        )
    ):
        return None

    ss = ob.get(
        "streamSettings",
        {}
    )

    security = ss.get(
        "security",
        "tls"
    )

    tls = ss.get(
        "tlsSettings",
        {}
    )

    network = ss.get(
        "network",
        "tcp"
    )

    q = {
        "security": security,
        "type": network,
    }

    if tls.get(
        "serverName"
    ):

        q["sni"] = (
            tls["serverName"]
        )

    if tls.get(
        "fingerprint"
    ):

        q["fp"] = (
            tls["fingerprint"]
        )

    if network == "ws":

        ws = ss.get(
            "wsSettings",
            {}
        )

        q["path"] = ws.get(
            "path",
            "/"
        )

        q["host"] = (
            ws.get(
                "headers",
                {}
            ).get(
                "Host",
                s["address"]
            )
        )

    remark = make_remark(
        s["address"]
    )

    return (
        "trojan://"
        + quote(
            str(s["password"]),
            safe=""
        )
        + "@"
        + str(s["address"])
        + ":"
        + str(s["port"])
        + "?"
        + encode_kv(q)
        + "#"
        + quote(
            remark,
            safe="@._- "
        )
    )


# ============================================================
# SHADOWSOCKS
# ============================================================

def build_ss_from_outbound(ob):

    servers = (
        ob.get("settings", {})
        .get("servers", [])
    )

    if not servers:
        return None

    s = servers[0]

    required = (
        "address",
        "port",
        "password",
        "method",
    )

    if not all(
        key in s
        for key in required
    ):
        return None

    userinfo = base64.b64encode(
        (
            str(s["method"])
            + ":"
            + str(s["password"])
        ).encode()
    ).decode()

    remark = make_remark(
        s["address"]
    )

    return (
        "ss://"
        + userinfo
        + "@"
        + str(s["address"])
        + ":"
        + str(s["port"])
        + "#"
        + quote(
            remark,
            safe="@._- "
        )
    )


# ============================================================
# VMESS
# ============================================================

def build_vmess_from_outbound(ob):

    vnext = (
        ob.get("settings", {})
        .get("vnext", [])
    )

    if not vnext:
        return None

    v = vnext[0]

    users = v.get(
        "users",
        []
    )

    if not users:
        return None

    user = users[0]

    if not all(
        key in v
        for key in (
            "address",
            "port",
        )
    ):
        return None

    ss = ob.get(
        "streamSettings",
        {}
    )

    obj = {
        "v": "2",

        "ps": make_remark(
            v["address"]
        ),

        "add": v["address"],

        "port": str(
            v["port"]
        ),

        "id": user.get(
            "id",
            ""
        ),

        "aid": str(
            user.get(
                "alterId",
                0
            )
        ),

        "scy": user.get(
            "security",
            "auto"
        ),

        "net": ss.get(
            "network",
            "tcp"
        ),

        "type": "none",

        "host": "",

        "path": "",

        "tls": ss.get(
            "security",
            ""
        ),
    }

    if obj["net"] == "ws":

        ws = ss.get(
            "wsSettings",
            {}
        )

        obj["path"] = ws.get(
            "path",
            "/"
        )

        host = (
            ws.get(
                "headers",
                {}
            ).get(
                "Host"
            )
        )

        if host:
            obj["host"] = host

    raw = json.dumps(
        obj,
        separators=(
            ",",
            ":"
        ),
        ensure_ascii=False
    ).encode()

    return (
        "vmess://"
        + base64.b64encode(
            raw
        ).decode()
    )


# ============================================================
# UNIVERSAL OUTBOUND
# ============================================================

def build_uri_from_outbound(ob):

    proto = ob.get(
        "protocol",
        ""
    )

    if proto == "vless":
        return build_vless_from_outbound(ob)

    if proto == "trojan":
        return build_trojan_from_outbound(ob)

    if proto in (
        "shadowsocks",
        "ss"
    ):
        return build_ss_from_outbound(ob)

    if proto == "vmess":
        return build_vmess_from_outbound(ob)

    return None


# ============================================================
# FINAL SNI PROCESSING
#
# Только:
#
# security=tls -> sni=rbc.ru
#
# security=reality -> НЕ ТРОГАЕМ
# ============================================================

def change_tls_sni(
    uri,
    new_sni="rbc.ru"
):

    try:

        parts = urlsplit(uri)

        params = parse_qsl(
            parts.query,
            keep_blank_values=True
        )

        security = None

        for key, value in params:

            if key.lower() == "security":

                security = value.lower()

                break

        # ----------------------------------------------------
        # Reality НЕ трогаем
        # ----------------------------------------------------

        if security == "reality":
            return uri

        # ----------------------------------------------------
        # Не TLS — тоже не трогаем
        # ----------------------------------------------------

        if security != "tls":
            return uri

        # ----------------------------------------------------
        # TLS
        # ----------------------------------------------------

        result = []
        sni_found = False

        for key, value in params:

            if key.lower() == "sni":

                result.append(
                    (key, new_sni)
                )

                sni_found = True

            else:

                result.append(
                    (key, value)
                )

        # Если SNI отсутствовал
        if not sni_found:

            result.append(
                ("sni", new_sni)
            )

        new_query = urlencode(
            result,
            doseq=True
        )

        return urlunsplit((
            parts.scheme,
            parts.netloc,
            parts.path,
            new_query,
            parts.fragment
        ))

    except Exception:

        return uri


# ============================================================
# GITHUB GIST
# ============================================================

def update_gist(content):

    if not GIST_ID or not GITHUB_TOKEN:

        print(
            "Gist SKIP: пустой "
            "GIST_ID / GITHUB_TOKEN"
        )

        return False

    url = (
        "https://api.github.com/gists/"
        + GIST_ID
    )

    headers = {
        "Authorization": (
            "Bearer "
            + GITHUB_TOKEN
        ),

        "User-Agent": (
            "OKO-Extractor"
        ),

        "Accept": (
            "application/vnd.github+json"
        ),
    }

    payload = {
        "files": {
            GIST_FILENAME: {
                "content": content
            }
        }
    }

    r = http_req(
        "PATCH",
        url,
        headers=headers,
        json=payload,
    )

    print(
        f"Gist HTTP {r['code']}"
    )

    if r["error"]:

        print(
            "Gist HTTP ERR:",
            r["error"]
        )

    if r["code"] not in (
        200,
        201
    ):

        print(
            "Gist response:",
            r["body"][:500]
        )

    return r["code"] in (
        200,
        201
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "=== OKO VPN → Gist ==="
    )

    print()

    # ========================================================
    # STEP 1
    # ========================================================

    dev = register_device()

    if not dev:

        print(
            "FATAL: registration failed"
        )

        return 1

    # ========================================================
    # STEP 2
    # ========================================================

    email = login_cabinet()

    if not email:

        print(
            "FATAL: login failed"
        )

        return 1

    # ========================================================
    # STEP 3
    # ========================================================

    sub_url = fetch_sub_url()

    if not sub_url:

        print(
            "FATAL: no sub URL"
        )

        return 1

    # ========================================================
    # STEP 4
    # ========================================================

    configs = fetch_configs(
        sub_url
    )

    if not configs:

        print(
            "FATAL: no configs"
        )

        return 1

    # ========================================================
    # COLLECT URI
    # ========================================================

    links = []
    seen = set()

    # --------------------------------------------------------
    # BASE64 FALLBACK
    # --------------------------------------------------------

    if "__raw_links__" in configs:

        for line in configs[
            "__raw_links__"
        ]:

            line = line.strip()

            if not line:
                continue

            if "://" not in line:
                continue

            parts = line.split(
                "#",
                1
            )

            base = parts[0]

            if len(parts) > 1:
                fragment = parts[1]
            else:
                fragment = "server"

            new_link = (
                base
                + "#"
                + fragment
            )

            if new_link in seen:
                continue

            seen.add(new_link)
            links.append(new_link)

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    else:

        if isinstance(
            configs,
            dict
        ):

            configs_iter = [
                configs
            ]

        else:

            configs_iter = configs

        for cfg in configs_iter:

            if not isinstance(
                cfg,
                dict
            ):
                continue

            outbounds = cfg.get(
                "outbounds",
                []
            )

            if not isinstance(
                outbounds,
                list
            ):
                continue

            for ob in outbounds:

                if not isinstance(
                    ob,
                    dict
                ):
                    continue

                link = (
                    build_uri_from_outbound(
                        ob
                    )
                )

                if not link:
                    continue

                # ------------------------------------------------
                # Dedup по protocol + address:port
                # ------------------------------------------------

                match = re.match(
                    r"^([a-z0-9]+)://"
                    r"[^@]*@"
                    r"([^/?#]+)",
                    link,
                    re.I
                )

                if match:

                    key = (
                        match.group(1)
                        + "|"
                        + match.group(2)
                    )

                else:

                    key = link

                if key in seen:
                    continue

                seen.add(key)
                links.append(link)

    # ========================================================
    # SNI
    # ========================================================

    print()

    print(
        "Собрано уникальных URI:",
        len(links)
    )

    changed = 0

    processed_links = []

    for link in links:

        new_link = change_tls_sni(
            link,
            "rbc.ru"
        )

        if new_link != link:
            changed += 1

        processed_links.append(
            new_link
        )

    links = processed_links

    print(
        "Изменено TLS SNI:",
        changed
    )

    # ========================================================
    # CONTENT
    # ========================================================

    now = time.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    header = (
        "# Обновлено: "
        + now
        + " | Конфигов: "
        + str(len(links))
        + "\n"
    )

    content = header

    if links:

        content += (
            "\n".join(links)
            + "\n"
        )

    print()

    print(
        "--- CONTENT ---"
    )

    print(
        content,
        end=""
    )

    print(
        "--- END ---"
    )

    print()

    # ========================================================
    # GIST
    # ========================================================

    ok = update_gist(
        content
    )

    if ok:

        print(
            "OK: Gist обновлён"
        )

        return 0

    print(
        "FAIL: Gist НЕ обновлён"
    )

    return 1


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    raise SystemExit(
        main()
    )
