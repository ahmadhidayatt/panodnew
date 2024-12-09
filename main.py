import asyncio
import json
import os
import random
import sys
import time
import uuid
from urllib.parse import urlparse

import cloudscraper
import requests
from curl_cffi import requests
from loguru import logger
from pyfiglet import figlet_format
from termcolor import colored


SHOW_REQUEST_ERROR_LOG = False

PING_INTERVAL = 60
RETRIES = 60

DOMAIN_API = {
    "SESSION": "http://api.nodepay.ai/api/auth/session",
    "PING": ["https://nw.nodepay.org/api/network/ping"],
    "DAILY_CLAIM": "https://api.nodepay.org/api/mission/complete-mission",
    "DEVICE_NETWORK": "https://api.nodepay.org/api/network/device-networks"
}

CONNECTION_STATES = {
    "CONNECTED": 1,
    "DISCONNECTED": 2,
    "NONE_CONNECTION": 3
}

status_connect = CONNECTION_STATES
account_info = {}
last_ping_time = {}
token_status = {}
browser_id = None

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
    print("\nWelcome to NodepayBot - Automate your tasks effortlessly!")

def print_file_info():
    tokens = load_file('tokens.txt')
    proxies = load_file('proxies.txt')
    border = "=" * 40

    print(border)
    print(
        f"\nTokens: {len(tokens)} - Loaded {len(proxies)} proxies"
        "\nNodepay only supports 3 connections per account. Using too many proxies may cause issues.\n"
        f"\n{border}"
    )

def ask_user_for_proxy():
    while (user_input := input("Do you want to use proxy? (yes/no)? ").strip().lower()) not in ['yes', 'no']:
        print("Invalid input. Please enter 'yes' or 'no'.")
    
    print(f"You selected: {'Yes' if user_input == 'yes' else 'No'}, ENJOY!\n")
    
    if user_input == 'yes':
        proxies = load_proxies()
        if not proxies:
            return None
        return proxies
    else:
        return []

def load_user_agents():
    try:
        return json.loads(load_file("user_agents.json", split_lines=False))
    except json.JSONDecodeError:
        logger.error("Error loading 'user_agents.json'. Ensure the file is valid.")
        return []

def load_file(filename, split_lines=True):
    try:
        with open(filename, 'r') as file:
            content = file.read()
            return content.splitlines() if split_lines else content
    except FileNotFoundError:
        logger.error(f"File '{filename}' not found. Please ensure it exists.")
        return []

def load_proxies():
    return load_file('proxies.txt')

def assign_proxies_to_tokens(tokens, proxies):
    paired = list(zip(tokens[:len(proxies)], proxies))
    remaining = [(token, None) for token in tokens[len(proxies):]]
    return paired + remaining

def extract_proxy_ip(proxy_url):
    try:
        return urlparse(proxy_url).hostname
    except Exception:
        return "Unknown"

def get_ip_address(proxy=None):
    try:
        url = "https://api.ipify.org?format=json"
        response = cloudscraper.create_scraper().get(url, proxies={"http": proxy, "https": proxy} if proxy else None)
        return response.json().get("ip", "Unknown") if response.status_code == 200 else "Unknown"
    except Exception as e:
        logger.error(f"<red>Failed to fetch IP address: {e}</red>")
    return "Unknown"

def log_user_data(users_data):
    if not users_data:
        logger.error("No user data available.")
        return

    try:
        for user_data in users_data:
            name = user_data.get("name", "Unknown")
            balance = user_data.get("balance", {})
            logger.info(f"User: <green>{name}</green>, "
                        f"Current Amount: <green>{balance.get('current_amount', 0)}</green>, "
                        f"Total Collected: <green>{balance.get('total_collected', 0)}</green>")

    except Exception as e:
        if SHOW_REQUEST_ERROR_LOG:
            logger.error(f"Logging error: {e}")

def generate_user_agents(tokens_file, output_file):
    if os.path.exists(output_file): return
    
    try:
        tokens = open(tokens_file).read().splitlines()
        
        data = []
        for t in tokens:
            chrome_version = f"{random.randint(100, 120)}.0.{random.randint(4000, 5000)}.{random.randint(0, 100)}"
            browser = random.choice(['Chrome', 'Mises', 'Kiwi', 'Herond'])
            user_agent = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                         f"Chrome/{chrome_version} Safari/537.36 {browser}/1.0"
            data.append({"token": t, "user_agent": user_agent})

        with open(output_file, "w") as json_file:
            json.dump(data, json_file, indent=4)

        print(f"{output_file} file created successfully")
    
    except Exception as e:
        print(f"Error: {e}")

def dailyclaim(token, user_agents):
    url = DOMAIN_API["DAILY_CLAIM"]
    user_agents = user_agents or load_user_agents()
    user_agent = next(
        (ua["user_agent"] for ua in user_agents if ua["token"] == token),
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": user_agent,
        "Content-Type": "application/json",
        "Origin": "https://app.nodepay.ai",
        "Referer": "https://app.nodepay.ai/",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept": "*/*",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    data = {
        "mission_id": "1"
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=15)
        if response.status_code != 200:
            logger.info(f"<yellow>Reward Already Claimed!</yellow>")
            return False
    
        response_json = response.json()
        if response_json.get("success"):
            logger.info(f"<green>Claim Reward Success!</green>")
            return True
        else:
            logger.info(f"<yellow>Reward Already Claimed!</yellow>")
            return False
    except Exception as e:
        logger.error(f"Request failed: {e}") if SHOW_REQUEST_ERROR_LOG else None
        return False

async def call_api(url, data, token, user_agents=None, proxy=None, timeout=60):
    user_agents = user_agents or load_user_agents()
    user_agent = next(
        (ua["user_agent"] for ua in user_agents if ua["token"] == token),
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": user_agent,
        "Content-Type": "application/json",
        "Origin": "chrome-extension://lgmpfmgeabnnlemejacfljbmonaomfmm",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
    }

    response = None

    try:
        response = requests.post(url, json=data, headers=headers, impersonate="safari15_5", proxies={"http": proxy, "https": proxy}, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error during API call to {url}: {e}") if SHOW_REQUEST_ERROR_LOG else None
        if response and response.status_code == 403:
            logger.error("<red>Access denied (HTTP 403). Possible invalid token or blocked IP/proxy.</red>")
        elif response and response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "unknown")
            logger.warning(f"<yellow>Rate limit hit (HTTP 429). Retry after {retry_after} seconds.</yellow>")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON response from {url}: {e}") if SHOW_REQUEST_ERROR_LOG else None
        return None

async def get_account_info(token, user_agents, proxy=None):
    url = DOMAIN_API["SESSION"]
    try:
        response = await call_api(url, {}, token, user_agents, proxy)
        if response and response.get("code") == 0:
            data = response["data"]
            return {
                "name": data.get("name", "Unknown"),
                "ip_score": data.get("ip_score", "N/A"),
                **data
            }
    except Exception as e:
        logger.error(f"<red>Error fetching account info for token {token[-10:]}: {e}</red>")
    return None

async def start_ping(token, account_info, proxy, ping_interval, user_agents=None, browser_id=None):
    global last_ping_time, RETRIES, status_connect

    user_agents = user_agents or load_user_agents()
    browser_id = browser_id or str(uuid.uuid4())
    url_index = 0
    last_valid_points = 0
    name = account_info.get("name", "Unknown")
    
    RETRIES = 0

    while True:
        current_time = time.time()

        if proxy:
            last_ping_time[proxy] = current_time

        if not DOMAIN_API["PING"]:
            logger.error("No PING URLs available in DOMAIN_API['PING'].")
            return

        url = DOMAIN_API["PING"][url_index]

        data = {
            "id": account_info.get("uid"),
            "browser_id": browser_id,
            "timestamp": int(time.time()),
            "version": "2.2.7"
        }

        try:
            response = await call_api(url, data, token, user_agents=user_agents, proxy=proxy, timeout=120)
            if response and response.get("data"):

                status_connect = CONNECTION_STATES["CONNECTED"]
                response_data = response["data"]
                ip_score = response_data.get("ip_score", "N/A")
                total_points = await get_total_points(token, user_agents, ip_score=ip_score, proxy=proxy, name=name)
                total_points = last_valid_points if total_points == 0 and last_valid_points > 0 else total_points
                last_valid_points = total_points

                identifier = extract_proxy_ip(proxy) if proxy else get_ip_address()
                logger.info(
                    f"<green>Ping Successfully</green>, Network Quality: <cyan>{ip_score}</cyan>, "
                    f"{'Proxy' if proxy else 'IP Address'}: <cyan>{identifier}</cyan>")
                
                RETRIES = 0
            else:
                logger.warning(f"<yellow>Invalid or no response from {url}</yellow>")
                RETRIES += 1

                if RETRIES >= 3:
                    logger.error(f"<red>Exceeded retry limit for proxy {proxy}. Aborting.</red>")
                    break

            url_index = (url_index + 1) % len(DOMAIN_API["PING"])

        except Exception as e:
            logger.error(f"<red>Error during pinging via proxy {proxy}: {e}</red>")
            RETRIES += 1

            if RETRIES >= 3:
                logger.error(f"<red>Exceeded retry limit for proxy {proxy}. Aborting.</red>")
                break

        await asyncio.sleep(ping_interval)

async def process_account(token, use_proxy, proxies=None, user_agents=None, ping_interval=2.0):
    proxies = proxies or []
    proxy_list = proxies if use_proxy else [None]

    proxy = proxy_list[0] if proxy_list else None
    browser_id = str(uuid.uuid4())

    account_info = None
    if not account_info:
        account_info = await get_account_info(token, user_agents, proxy=proxy)

        if not account_info:
            logger.error(f"<red>Account info not found for token: {token[-10:]}</red>")
            return

    for proxy in proxy_list:
        try:
            response = await call_api(DOMAIN_API["SESSION"], {}, token, user_agents, proxy)

            if response and response.get("code") == 0:
                account_info = response["data"]
                log_user_data(account_info)

                await start_ping(token, account_info, proxy, ping_interval, user_agents, browser_id)
                return

            logger.warning(f"<yellow>Invalid or no response for token with proxy {proxy}</yellow>")
        except Exception as e:
            logger.error(f"<red>Error with proxy {proxy} for token {token[-10:]}: {e}</red>")

    logger.error(f"<red>All attempts failed for token {token[-10:]}</red>")

async def get_total_points(token, user_agents, ip_score="N/A", proxy=None, name="Unknown"):
    try:
        scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows"})
        url = DOMAIN_API["DEVICE_NETWORK"]
        user_agent = next(
            (ua["user_agent"] for ua in user_agents if ua["token"] == token),
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
        )
        headers = {"Authorization": f"Bearer {token}", "User-Agent": user_agent, "Accept": "application/json", "Content-Type": "application/json"}
        proxies = {"http": proxy, "https": proxy} if proxy else None

        response = scraper.get(url, headers=headers, proxies=proxies, timeout=60)

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                total_points = sum(device.get("total_points", 0) for device in data.get("data", []))
                logger.info(f"<magenta>Earn successfully</magenta>, Total Points: <cyan>{total_points:.2f}</cyan> for user: <magenta>{name}</magenta>")
                return total_points
            logger.error(f"<red>Failed to fetch points: {data.get('msg', 'Unknown error')}</red>")
        elif response.status_code == 403:
            identifier = extract_proxy_ip(proxy) if proxy else get_ip_address()
            logger.error(f"<red>HTTP 403: Access denied. Proxy or token may be blocked.</red> "
                         f"{ 'Proxy' if proxy else 'IP Address' }: <cyan>{identifier}</cyan>")
        else:
            logger.error(f"<red>Unexpected HTTP {response.status_code} while fetching points.</red>")

    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        identifier = extract_proxy_ip(proxy) if proxy else get_ip_address()
        logger.error(f"<red>Error: {str(e)}</red> { 'Proxy' if proxy else 'IP Address' }: <cyan>{identifier}</cyan>")
    except Exception as e:
        identifier = extract_proxy_ip(proxy) if proxy else get_ip_address()
        logger.error(f"<red>Unexpected error: {e}</red> { 'Proxy' if proxy else 'IP Address' }: <cyan>{identifier}</cyan>")
    
    return 0

async def process_tokens(tokens, user_agents):
    await asyncio.gather(*(asyncio.to_thread(dailyclaim, token, user_agents) for token in tokens))

async def create_tasks(token_proxy_pairs, user_agents):
    return [
        call_api(DOMAIN_API["SESSION"], data={}, token=token, user_agents=user_agents, proxy=proxy)
        for token, proxy in token_proxy_pairs
    ] + [
        process_account(token, use_proxy=bool(proxy), proxies=[proxy] if proxy else [], ping_interval=4.0, user_agents=user_agents)
        for token, proxy in token_proxy_pairs
    ]

async def main():
    if not (user_agents := load_user_agents()):
        return logger.error("No user agents loaded. Exiting.")
    if not (tokens := load_file("tokens.txt")):
        return logger.error("No tokens found in 'tokens.txt'. Exiting.")

    proxies = ask_user_for_proxy()

    await process_tokens(tokens, user_agents)
    token_proxy_pairs = assign_proxies_to_tokens(tokens, proxies)

    users_data = await asyncio.gather(*(get_account_info(token, user_agents) for token in tokens), return_exceptions=True)
    log_user_data([data for data in users_data if not isinstance(data, Exception)])

    logger.info("Waiting before starting tasks...")
    await asyncio.sleep(5)

    tasks = await create_tasks(token_proxy_pairs, user_agents)
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        logger.error(f"Task failed: {result}") if isinstance(result, Exception) else logger.info(f"Task succeeded: {result}")

if __name__ == '__main__':
    try:
        print_header()
        print_file_info()
        generate_user_agents("tokens.txt", "user_agents.json")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program interrupted. Exiting gracefully...")
    finally:
        print("Cleaning up resources before exiting.")
