import asyncio
import json
import sys
import time
import uuid

from fake_useragent import UserAgent
from curl_cffi import requests
from loguru import logger
from pyfiglet import figlet_format
from termcolor import colored
import pyfiglet
from urllib.parse import urlparse

# Constants
PING_INTERVAL = 0.5
DOMAIN_API = {
    "SESSION": "http://api.nodepay.ai/api/auth/session",
    "PING": ["https://nw.nodepay.org/api/network/ping"],
    "DEVICE_NETWORK": "https://api.nodepay.org/api/network/device-networks"
}
CONNECTION_STATES = {
    "CONNECTED": 1,
    "DISCONNECTED": 2,
    "NONE_CONNECTION": 3
}

# Global configuration
SHOW_REQUEST_ERROR_LOG = False

# Setup logger
logger.remove()
logger.add(
    sink=sys.stdout,
    format="<r>[Nodepay]</r> | <white>{time:YYYY-MM-DD HH:mm:ss}</white> | "
           "<level>{level: <7}</level> | <cyan>{line: <3}</cyan> | {message}",
    colorize=True
)
logger = logger.opt(colors=True)

def print_header():
    ascii_art = figlet_format("NodepayBot", font="slant")
    colored_art = colored(ascii_art, color="cyan")
    border = "=" * 40
    
    print(border)
    print(colored_art)
    print(colored("by Enukio", color="cyan", attrs=["bold"]))
    print()
    print("Welcome to NodepayBot - Automate your tasks effortlessly!")
    print(border)

print_header()

def read_tokens_and_proxy():
    with open('tokens.txt', 'r') as file:
        tokens_content = sum(1 for line in file)

    with open('proxies.txt', 'r') as file:
        proxy_count = sum(1 for line in file)

    return tokens_content, proxy_count

tokens_content, proxy_count = read_tokens_and_proxy()

print()
print(f"Tokens: {tokens_content} - Loaded {proxy_count} proxies\n")
print(f"Nodepay only supports 3 connections per account. Using too many proxies may cause issues.")
print()
print("=" * 40)

# Proxy utility
def ask_user_for_proxy():
    user_input = ""
    while user_input not in ['yes', 'no']:
        user_input = input("Do you want to use proxy? (yes/no)? ").strip().lower()
        if user_input not in ['yes', 'no']:
            print("Invalid input. Please enter 'yes' or 'no'.")
    print(f"You selected: {'Yes' if user_input == 'yes' else 'No'}, ENJOY!\n")
    return user_input == 'yes'

def validate_proxies(proxies):
    valid_proxies = []
    for proxy in proxies:
        if proxy.startswith("http://") or proxy.startswith("https://"):
            valid_proxies.append(proxy)
        else:
            logger.warning(f"Invalid proxy format: {proxy}")
    return valid_proxies

def load_proxies():
    try:
        with open('proxies.txt', 'r') as file:
            proxies = file.read().splitlines()
        return proxies
    except Exception as e:
        logger.error(f"Failed to load proxies: {e}")
        raise SystemExit("Exiting due to failure in loading proxies")

# Main functions
token_status = {}

def dailyclaim(token):
    try:
        url = f"https://api.nodepay.org/api/mission/complete-mission?"
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Origin": "https://app.nodepay.ai",
            "Referer": "https://app.nodepay.ai/"
        }
        data = {"mission_id": "1"}
        response = requests.post(url, headers=headers, json=data, impersonate="chrome110")

        if response.json().get('success'):
            if token_status.get(token) != "claimed":
                logger.info("<green>Claim Reward Success!</green>")
                token_status[token] = "claimed"
        else:
            if token_status.get(token) != "failed":
                logger.info("<yellow>Reward Already Claimed! Or Something Wrong!</yellow>")
                token_status[token] = "failed"
    except requests.exceptions.RequestException as e:
        logger.error(f"Error : {e}")

async def call_api(url, data, token, proxy=None):
    user_agent = UserAgent().chrome if UserAgent().chrome else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
    sec_ch_ua_version = user_agent.split("Chrome/")[-1].split(" ")[0]
    headers = {
        # Authentication and Identity
        "Authorization": f"Bearer {token}",
        "User-Agent": user_agent,

        # Content Settings
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/json",

        # Request Origin Settings
        "Referer": "https://app.nodepay.ai/",
        "Origin": "chrome-extension://lgmpfmgeabnnlemejacfljbmonaomfmm",

        # Platform and Browser
        "Sec-Ch-Ua": f'"Chromium";v="{sec_ch_ua_version}", "Google Chrome";v="{sec_ch_ua_version}", "Not?A_Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',

        # Security and Privacy Settings
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "cross-site",
        "DNT": "1",

        # Connection Settings
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    }

    proxies = {"http": proxy, "https": proxy} if proxy else None
    try:
        response = requests.post(url, json=data, headers=headers, proxies=proxies, impersonate="chrome110", timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.SSLError:
        if SHOW_REQUEST_ERROR_LOG:
            logger.error("Error during API call: SSL Error")
        return None
    except requests.exceptions.ConnectionError:
        if SHOW_REQUEST_ERROR_LOG:
            logger.error("Error during API call: Connection Error")
        return None
    except requests.exceptions.RequestException:
        if SHOW_REQUEST_ERROR_LOG:
            logger.error("Error during API call: Request Error")
        return None
    except json.JSONDecodeError:
        if SHOW_REQUEST_ERROR_LOG:
            logger.error("Error during API call: JSON Decode Error")
        return None

def get_ip_address(proxy=None):
    if proxy:
        try:
            response = requests.get("https://api.ipify.org?format=json", proxies={"http": proxy, "https": proxy})
            if response.status_code == 200:
                return response.json().get("ip", "Unknown")
        except requests.exceptions.RequestException:
            return "Unknown"
    else:
        try:
            response = requests.get("https://api.ipify.org?format=json")
            if response.status_code == 200:
                return response.json().get("ip", "Unknown")
        except requests.exceptions.RequestException:
            return "Unknown"

def extract_proxy_ip(proxy_url):
    try:
        parsed_url = urlparse(proxy_url)
        return parsed_url.hostname
    except Exception as e:
        logger.warning(f"Failed to extract IP from proxy: {proxy_url}, error: {e}")
        return "Unknown"

async def start_ping(token, account_info, proxy):
    browser_id = str(uuid.uuid4())
    url_index = 0
    last_valid_points = 0

    while True:
        try:
            url = DOMAIN_API["PING"][url_index]
            data = {
                "id": account_info.get("uid"),
                "browser_id": browser_id,
                "timestamp": int(time.time())
            }
            response = await call_api(url, data, token, proxy)

            if response:
                response_data = response.get("data", {})
                ip_score = response_data.get("ip_score", "Unavailable")
                ip_address = get_ip_address()

                total_points = await get_total_points(token, ip_score=ip_score, proxy=proxy)

                if total_points == 0 and last_valid_points > 0:
                    total_points = last_valid_points
                else:
                    last_valid_points = total_points

                if proxy:
                    proxy_ip = extract_proxy_ip(proxy)
                    logger.info(
                        f"<green>Ping Successfully</green>, Network Quality: <cyan>{ip_score}</cyan>, "
                        f"Proxy: <cyan>{proxy_ip}</cyan>, Total Points Earned: <cyan>{total_points:.2f}</cyan>"
                    )
                else:
                    logger.info(
                        f"<green>Ping Successfully</green>, Network Quality: <cyan>{ip_score}</cyan>, "
                        f"IP Address: <cyan>{ip_address}</cyan>, Total Points Earned: <cyan>{total_points:.2f}</cyan>"
                    )
            else:
                logger.warning(f"<yellow>No response from {url}</yellow>")
        except Exception as e:
            logger.error(f"<red>Error in pinging: {e}</red>")
        finally:
            await asyncio.sleep(PING_INTERVAL)
            url_index = (url_index + 1) % len(DOMAIN_API["PING"])

def log_user_data(user_data):
    try:
        name = user_data.get("name", "Unknown")
        balance = user_data.get("balance", {})
        current_amount = balance.get("current_amount", 0)
        total_collected = balance.get("total_collected", 0)

        log_message = (
            f"<green>{name}</green>, "
            f"Current Amount: <green>{current_amount}</green>, Total Collected: <green>{total_collected}</green>"
        )
        logger.info(f"Name: {log_message}")
    except Exception as e:
        logger.error(f"Failed to log user data: {e}")

async def get_total_points(token, ip_score="Unknown", proxy=None):
    try:
        url = DOMAIN_API["DEVICE_NETWORK"]
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "Mozilla/5.0 (Linux; Android 12; Samsung Galaxy S21 Build/SP1A.210812.016) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Host": "api.nodepay.org",
            "Referer": "https://app.nodepay.ai/",
        }
        params = {"page": 0, "limit": 10, "active": "true"}
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                devices = data.get("data", [])
                total_points = sum(device.get("total_points", 0) for device in devices)
                ip_address = get_ip_address()

                if proxy:
                    proxy_ip = extract_proxy_ip(proxy)
                    logger.info(
                        f"<magenta>Earn Successfully</magenta>, Network Quality: <cyan>{ip_score}</cyan>, "
                        f"Proxy: <cyan>{proxy_ip}</cyan>, Total Points Earned: <cyan>{total_points:.2f}</cyan>"
                    )
                else:
                    logger.info(
                        f"<magenta>Earn Successfully</magenta>, Network Quality: <cyan>{ip_score}</cyan>, "
                        f"IP Address: <cyan>{ip_address}</cyan>, Total Points Earned: <cyan>{total_points:.2f}</cyan>"
                    )
                return total_points
            else:
                if SHOW_REQUEST_ERROR_LOG:
                    logger.error(f"Failed to fetch points for token: {data.get('msg')}")
        else:
            if SHOW_REQUEST_ERROR_LOG:
                logger.error(f"Failed to fetch points for token: HTTP {response.status_code}")
    except Exception as e:
        if SHOW_REQUEST_ERROR_LOG:
            logger.error(f"Error fetching total points for token: {e}")
    return 0

async def process_account(token, use_proxy, proxies=None):
    proxies = proxies or []
    ip_score = "Unknown"
    for proxy in (proxies if use_proxy else [None]):
        try:
            logger.debug(f"Trying with proxy: {proxy}")
            response = await call_api(DOMAIN_API["SESSION"], {}, token, proxy)
            if response and response.get("code") == 0:
                account_info = response["data"]

                log_user_data(account_info)

                total_points = await get_total_points(token, ip_score=ip_score, proxy=proxy)

                await start_ping(token, account_info, proxy)
                return
            else:
                logger.warning(f"<yellow>Invalid or no response for token with proxy {proxy}</yellow>")
        except Exception as e:
            logger.error(f"Unhandled error with proxy {proxy} for token {token}: {e}")
    logger.error(f"<yellow>All attempts failed</yellow>")

async def main():
    use_proxy = ask_user_for_proxy()
    proxies = load_proxies() if use_proxy else []
    try:
        with open('tokens.txt', 'r') as file:
            tokens = file.read().splitlines()
    except FileNotFoundError:
        print("File tokens.txt not found. Please create it.")
        exit()

    tasks = []
    for token in tokens:
        tasks.append(process_account(token, use_proxy, proxies))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Task for token {tokens[i]} failed: {repr(result).replace('<', '&lt;').replace('>', '&gt;')}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Program terminated by user.")
