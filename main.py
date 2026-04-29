import requests
import sys
import time
import random
import base64
import json
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def get_retry_session(retries=3, backoff_factor=1):
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "PATCH"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

class DiscordAuth:
    def __init__(self):
        self.session = get_retry_session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def get_fingerprint(self):
        try:
            r = self.session.get('https://discord.com/api/v9/experiments', timeout=10)
            if r.status_code == 200:
                return r.json().get('fingerprint')
        except:
            pass
        return None

    def solve_2fa(self, ticket, code):
        payload = {"code": code, "ticket": ticket, "login_source": None, "gift_code_sku_id": None}
        headers = {'Content-Type': 'application/json'}
        try:
            r = self.session.post('https://discord.com/api/v9/auth/mfa/totp', json=payload, headers=headers, timeout=10)
            if r.status_code == 200:
                return r.json().get('token')
        except:
            pass
        return None

    def login(self, email, password, code_2fa=None):
        fingerprint = self.get_fingerprint()
        if not fingerprint:
            print("[-] Khong the lay fingerprint, thu lai sau.")
            return None

        payload = {
            'login': email, 'password': password,
            'undelete': False, 'captcha_key': None,
            'login_source': None, 'gift_code_sku_id': None
        }
        headers = {'Content-Type': 'application/json', 'X-Fingerprint': fingerprint}

        try:
            r = self.session.post('https://discord.com/api/v9/auth/login', json=payload, headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                token = data.get('token')
                if token:
                    print(f"[+] Dang nhap thanh cong, token: ...{token[-5:]}")
                    return token
                else:
                    print("[-] Phan hoi khong chua token.")
                    return None
            elif r.status_code == 400:
                data = r.json()
                if data.get('captcha_key'):
                    print("[-] Discord yeu cau captcha, khong the dang nhap tu dong.")
                elif 'mfa' in str(data).lower() or data.get('ticket'):
                    ticket = data.get('ticket')
                    if ticket and not code_2fa:
                        code_2fa = input("Nhap ma 2FA (6 chu so): ").strip()
                    if ticket and code_2fa:
                        token = self.solve_2fa(ticket, code_2fa)
                        if token:
                            print(f"[+] Dang nhap thanh cong (2FA), token: ...{token[-5:]}")
                            return token
                        else:
                            print("[-] Sai ma 2FA hoac xac minh khong thanh cong.")
                else:
                    print(f"[-] Loi dang nhap: {data}")
                return None
            elif r.status_code == 401:
                print("[-] Email hoac mat khau sai.")
                return None
            else:
                print(f"[-] Loi khong xac dinh (HTTP {r.status_code}): {r.text}")
                return None
        except Exception as e:
            print(f"[-] Loi ket noi khi dang nhap: {e}")
            return None

spam_session = get_retry_session()

BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) discord/1.0.9027 Chrome/108.0.5359.215 Electron/22.3.18 Safari/537.36",
    "Content-Type": "application/json",
    "Origin": "https://discord.com",
    "Referer": "https://discord.com/channels/@me",
    "x-discord-locale": "en-US",
    "x-super-properties": base64.b64encode(json.dumps({
        "os": "Windows",
        "browser": "Discord Client",
        "release_channel": "stable",
        "client_version": "1.0.9027",
        "os_version": "10.0.19045",
        "os_arch": "x64",
        "system_locale": "en-US",
        "client_build_number": 202836,
        "native_build_number": 30137,
        "client_event_source": None
    }, separators=(',', ':')).encode()).decode()
}

JOIN_CONTEXT = base64.b64encode(json.dumps({"location": "Join Guild"}).encode()).decode()

def get_headers(token, extra=None):
    h = {**BASE_HEADERS, "Authorization": token}
    if extra:
        h.update(extra)
    return h

def typing_indicator(token, channel_id):
    url = f"https://discord.com/api/v9/channels/{channel_id}/typing"
    headers = get_headers(token)
    try:
        spam_session.post(url, headers=headers, timeout=5)
    except:
        pass

def check_invite(invite_code):
    """Kiểm tra invite có tồn tại và còn hiệu lực không."""
    try:
        r = spam_session.get(f"https://discord.com/api/v9/invites/{invite_code}?with_counts=true", timeout=5)
        if r.status_code == 200:
            return True, r.json()
        else:
            return False, r.json()
    except:
        return False, None

def join_server(token, invite_code):
    url = f"https://discord.com/api/v9/invites/{invite_code}"
    headers = get_headers(token, {"X-Context-Properties": JOIN_CONTEXT})
    while True:
        try:
            r = spam_session.post(url, headers=headers, json={}, timeout=10)
            if r.status_code in (200, 204):
                print(f"[+] Token ...{token[-5:]} da join server thanh cong.")
                return True
            elif r.status_code == 429:
                retry = r.json().get("retry_after", 1)
                print(f"[!] Rate limit join, doi {retry:.1f}s...")
                time.sleep(retry)
            elif r.status_code == 400:
                data = r.json()
                if "captcha" in str(data).lower():
                    print(f"[-] Server yeu cau captcha, khong the join tu dong. Token ...{token[-5:]}")
                else:
                    print(f"[-] Token ...{token[-5:]} join that bai (400): {data}")
                return False
            elif r.status_code == 403:
                data = r.json()
                if data.get("code") == 10008:
                    print(f"[-] Invite khong ton tai hoac da het han. Token ...{token[-5:]}")
                else:
                    print(f"[-] Token ...{token[-5:]} bi tu choi join (403): {data}")
                return False
            elif r.status_code == 401:
                print(f"[-] Token ...{token[-5:]} khong hop le (401).")
                return False
            else:
                print(f"[-] Token ...{token[-5:]} join that bai: {r.status_code} | {r.text}")
                return False
        except requests.exceptions.ConnectionError as e:
            print(f"[!] Loi ket noi join, thu lai sau 3s: {e}")
            time.sleep(3)
        except Exception as e:
            print(f"[!] Loi khong xac dinh: {e}")
            time.sleep(3)

def send_message(token, channel_id, content, delay=None):
    typing_indicator(token, channel_id)
    if delay is not None:
        time.sleep(delay)
    else:
        time.sleep(random.uniform(1.0, 3.5))

    url = f"https://discord.com/api/v9/channels/{channel_id}/messages"
    headers = get_headers(token)
    while True:
        try:
            r = spam_session.post(url, headers=headers, json={"content": content}, timeout=10)
            if r.status_code in (200, 201):
                print(f"[+] Token ...{token[-5:]} da gui tin.")
                return True
            elif r.status_code == 429:
                retry = r.json().get("retry_after", 1)
                print(f"[!] Rate limit gui, doi {retry:.1f}s...")
                time.sleep(retry)
            else:
                print(f"[-] Token ...{token[-5:]} gui loi: {r.status_code} | {r.text}")
                return False
        except requests.exceptions.ConnectionError:
            print("[!] Mat ket noi, thu lai sau 3 giay...")
            time.sleep(3)
        except Exception as e:
            print(f"[!] Loi: {e}")
            time.sleep(3)

def try_get_guilds(tokens):
    for token in tokens:
        url = "https://discord.com/api/v9/users/@me/guilds"
        headers = get_headers(token)
        try:
            r = spam_session.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                return r.json(), token
            else:
                print(f"[-] Token ...{token[-5:]} khong lay duoc server (HTTP {r.status_code})")
        except:
            continue
    return [], None

def try_get_channels(tokens, guild_id):
    for token in tokens:
        url = f"https://discord.com/api/v9/guilds/{guild_id}/channels"
        headers = get_headers(token)
        try:
            r = spam_session.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                channels = r.json()
                text_channels = [ch for ch in channels if ch.get("type") in (0, 5)]
                return text_channels, token
            else:
                print(f"[-] Token ...{token[-5:]} khong lay duoc kenh (HTTP {r.status_code})")
        except:
            continue
    return [], None

def choose_from_list(title, items, name_key="name", id_key="id", prompt="Chon so: "):
    print(f"\n{title}")
    for i, item in enumerate(items, 1):
        print(f"  {i}. {item.get(name_key, 'Unknown')}")
    while True:
        choice = input(prompt).strip()
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(items):
                return items[idx-1][id_key]
        print("Lua chon khong hop le, vui long nhap so tu 1 den", len(items))

def save_tokens_to_file(tokens, filename="tokens.txt"):
    with open(filename, 'w') as f:
        for tok in tokens:
            f.write(tok + '\n')
    print(f"[+] Da luu {len(tokens)} token vao {filename}")

def load_tokens_from_file(filename="tokens.txt"):
    if not os.path.exists(filename):
        return []
    with open(filename, 'r') as f:
        return [line.strip() for line in f if line.strip()]

def main():
    print("=== DISCORD TOOL KET HOP DANG NHAP - SPAM ===")
    tokens = []

    while True:
        print("\n--- NGUON TOKEN ---")
        print("1. Nhap token thu cong (hoac tu file tokens.txt)")
        print("2. Dang nhap tu dong de lay token (email + mat khau)")
        print("3. Thoat")
        choice = input("Lua chon: ").strip()

        if choice == '1':
            use_file = input("Doc token tu file tokens.txt (y/n)? ").strip().lower()
            if use_file == 'y':
                tokens = load_tokens_from_file()
                if not tokens:
                    print("[-] File tokens.txt khong co token nao.")
                    continue
                print(f"[+] Da nap {len(tokens)} token tu file.")
            else:
                try:
                    n = int(input("So luong acc: "))
                except:
                    print("So khong hop le")
                    continue
                for i in range(n):
                    tok = input(f"Token {i+1}: ").strip()
                    if not tok:
                        print("Token khong duoc de trong")
                        continue
                    tokens.append(tok)
            break

        elif choice == '2':
            auth = DiscordAuth()
            try:
                n = int(input("So luong tai khoan can dang nhap: "))
            except:
                print("So khong hop le")
                continue
            for i in range(n):
                print(f"\n--- Tai khoan {i+1} ---")
                email = input("Email: ").strip()
                password = input("Password: ").strip()
                code_2fa = input("Ma 2FA (neu co, nhan Enter neu khong): ").strip()
                if not code_2fa:
                    code_2fa = None
                token = auth.login(email, password, code_2fa)
                if token:
                    tokens.append(token)
                else:
                    print("[-] Dang nhap that bai, bo qua tai khoan nay.")
            if tokens:
                save = input("Luu token vao file tokens.txt (y/n)? ").strip().lower()
                if save == 'y':
                    save_tokens_to_file(tokens)
            break

        elif choice == '3':
            sys.exit(0)
        else:
            print("Lua chon khong hop le.")

    if not tokens:
        sys.exit("Khong co token nao, thoat.")

    print("\n--- CHON SERVER ---")
    print("1. Nhap link invite de join server")
    print("2. Chon server da join (tu danh sach)")

    server_choice = input("Lua chon (1/2): ").strip()
    need_join = False
    invite_code = None
    target_guild_id = None

    if server_choice == "1":
        invite_link = input("Link Discord can join: ").strip()
        if "discord.gg/" in invite_link:
            invite_code = invite_link.split("discord.gg/")[-1]
        elif "discord.com/invite/" in invite_link:
            invite_code = invite_link.split("discord.com/invite/")[-1]
        else:
            invite_code = invite_link
        invite_code = invite_code.rstrip("/").strip()

        print("Kiem tra invite...")
        valid, invite_data = check_invite(invite_code)
        if not valid:
            print(f"[-] Invite khong hop le hoac da het han (code {invite_data.get('code', '?')}): {invite_data}")
            sys.exit(1)
        else:
            guild_name = invite_data['guild']['name']
            print(f"[+] Invite hop le: {guild_name}")
        need_join = True
    elif server_choice == "2":
        guilds, valid_token = try_get_guilds(tokens)
        if not guilds:
            sys.exit("Tat ca token deu khong the lay danh sach server.")
        target_guild_id = choose_from_list(
            "Chon server da tham gia:", guilds,
            name_key="name", id_key="id", prompt="Chon so server: "
        )
        print(f"[+] Da chon server ID: {target_guild_id}")
    else:
        sys.exit("Lua chon khong hop le.")

    if need_join:
        print("\nDang join server...")
        for token in tokens:
            join_server(token, invite_code)
        print("Da join xong (bo qua loi neu co).")

    print("\n--- CHON KENH ---")
    print("1. Nhap Channel ID truc tiep")
    print("2. Chon kenh tu server (tu dong lay danh sach kenh)")

    channel_choice = input("Lua chon (1/2): ").strip()
    channel_id = None

    if channel_choice == "1":
        cid = input("Channel ID can gui tin: ").strip()
        if not cid.isdigit():
            sys.exit("Channel ID phai la so")
        channel_id = cid
    elif channel_choice == "2":
        if target_guild_id:
            reuse = input("Dung server da chon truoc do? (y/n): ").strip().lower()
            if reuse != 'y':
                target_guild_id = None
        if not target_guild_id:
            guilds, valid_token = try_get_guilds(tokens)
            if not guilds:
                sys.exit("Tat ca token deu khong the lay danh sach server.")
            target_guild_id = choose_from_list(
                "Chon server de lay kenh:", guilds,
                name_key="name", id_key="id", prompt="Chon so server: "
            )
        channels, _ = try_get_channels(tokens, target_guild_id)
        if not channels:
            sys.exit("Khong co kenh text nao trong server hoac khong the lay duoc.")
        channel_id = choose_from_list(
            "Chon kenh de gui tin:", channels,
            name_key="name", id_key="id", prompt="Chon so kenh: "
        )
        print(f"[+] Da chon kenh ID: {channel_id}")
    else:
        sys.exit("Lua chon khong hop le.")

    loop_choice = input("Co loop spam tin nhan khong? (1 = Co, 2 = Khong): ").strip()
    loop = True if loop_choice == "1" else False

    base_message = input("Noi dung tin nhan: ")

    speed_input = input("Toc do spam (giay, de trong = random): ").strip()
    use_random_delay = True
    spam_delay = None
    loop_delay = None
    if speed_input:
        try:
            spam_delay = float(speed_input)
            loop_delay = spam_delay * 2
            use_random_delay = False
        except:
            print("Gia tri khong hop le, su dung random.")

    print("\n=== BAT DAU GUI TIN ===")
    if loop:
        print("Loop spam dang chay (Ctrl+C de dung)...")
        spam_count = 0
        try:
            while True:
                for token in tokens:
                    suffix = random.choice([f" [{spam_count}]", f" (~{random.randint(10,99)})", ""])
                    message = base_message + suffix
                    send_message(token, channel_id, message, delay=spam_delay if not use_random_delay else None)
                    if use_random_delay:
                        time.sleep(random.uniform(1.0, 3.0))
                    else:
                        time.sleep(spam_delay)
                if use_random_delay:
                    time.sleep(random.uniform(5.0, 10.0))
                else:
                    time.sleep(loop_delay)
                spam_count += 1
        except KeyboardInterrupt:
            print("\nDa dung loop.")
    else:
        for token in tokens:
            send_message(token, channel_id, base_message, delay=spam_delay if not use_random_delay else None)
            if use_random_delay:
                time.sleep(random.uniform(1.0, 2.0))
            else:
                time.sleep(spam_delay if spam_delay else 1.0)

if __name__ == "__main__":
    main()
