import asyncio
import html
import json
import os
import sys
import time
import uuid
from urllib.parse import urlparse

import cloudscraper
import requests
from curl_cffi import requests
from fake_useragent import UserAgent
from loguru import logger
from pyfiglet import figlet_format
from requests.exceptions import RequestException
from termcolor import colored

# Constants
PING_INTERVAL = 2

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
    print("\nWelcome to NodepayBot - Automate your tasks effortlessly!")
    print(border)

    try:
        with open('tokens.txt', 'r') as file:
            tokens_content = len(file.readlines())
        with open('proxies.txt', 'r') as file:
            proxy_count = len(file.readlines())
    except FileNotFoundError as e:
        print(f"Error: {e.filename} not found. Please ensure the file is available.")
        tokens_content, proxy_count = 0, 0
    except Exception as e:
        print(f"An error occurred while reading files: {e}")
        tokens_content, proxy_count = 0, 0

    print(f"\nTokens: {tokens_content} - Loaded {proxy_count} proxies\n")
    print("Nodepay only supports 3 connections per account. Using too many proxies may cause issues.\n")
    print(border)

# Proxy utility
def ask_user_for_proxy():
    user_input = ""
    while user_input not in ['yes', 'no']:
        user_input = input("Do you want to use proxy? (yes/no)? ").strip().lower()
        if user_input not in ['yes', 'no']:
            print("Invalid input. Please enter 'yes' or 'no'.")
    print(f"You selected: {'Yes' if user_input == 'yes' else 'No'}, ENJOY!\n")
    return user_input == 'yes'

def load_proxies():
    try:
        with open('proxies.txt', 'r') as file:
            proxies = file.read().splitlines()
        return proxies
    except Exception as e:
        logger.error(f"<red>Failed to load proxies: {e}</red>")
        raise SystemExit("Exiting due to failure in loading proxies")

def validate_proxies(proxies):
    valid_proxies = []
    for proxy in proxies:
        if proxy.startswith("http://") or proxy.startswith("https://"):
            valid_proxies.append(proxy)
        else:
            logger.warning(f"Invalid proxy format: {proxy}")
    return valid_proxies

def extract_proxy_ip(proxy_url):
    try:
        parsed_url = urlparse(proxy_url)
        return parsed_url.hostname
    except Exception as e:
        logger.warning(f"<yellow>Failed to extract IP from proxy: {proxy_url}, error: {e}</yellow>")
        return "Unknown"

def assign_proxies_to_tokens(tokens, proxies):
    paired = list(zip(tokens[:len(proxies)], proxies))

    paired.extend([(token, None) for token in tokens[len(proxies):]])

    return paired

def get_ip_address(proxy=None):
    try:
        url = "https://api.ipify.org?format=json"
        response = cloudscraper.create_scraper().get(url, proxies={"http": proxy, "https": proxy} if proxy else None)
        if response.status_code == 200:
            return response.json().get("ip", "Unknown")
    except Exception as e:
        logger.error(f"<red>Failed to fetch IP address: {e}</red>")
    return "Unknown"

def log_user_data(users_data):
    try:
        if not users_data:
            logger.error("No user data available to log.")
            return

        for user_data in users_data:
            name = user_data.get("name", "Unknown")
            balance = user_data.get("balance", {})
            current_amount = balance.get("current_amount", 0)
            total_collected = balance.get("total_collected", 0)

            logger.info(
                f"User: <green>{name}</green>, Current Amount: <green>{current_amount}</green>, Total Collected: <green>{total_collected}</green>"
            )

    except Exception as e:
        if SHOW_REQUEST_ERROR_LOG:
            logger.error(f"Failed to log user data: {e}")

def generate_user_agents(tokens_file, output_file):
    if os.path.exists(output_file):
        print(f"{output_file} already exists. Skipping generation.")
        print()
        return

    try:
        with open(tokens_file, "r") as file:
            tokens = file.read().splitlines()
    except FileNotFoundError:
        print(f"Error: {tokens_file} not found.")
        print()
        return

    ua = UserAgent()
    data = []

    for token in tokens:
        user_agent = ua.chrome
        data.append({"token": token, "user_agent": user_agent})

    try:
        with open(output_file, "w") as json_file:
            json.dump(data, json_file, indent=4)
        print(f"{output_file} file created successfully")
        print()
    except Exception as e:
        print(f"Failed to write user-agent data to {output_file}: {e}")
        print()

def load_user_agents():
    try:
        with open("user_agents.json", "r") as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"user_agents.json not found. Please generate it first.")
        print()
        return []
    except Exception as e:
        print(f"Error loading user_agents.json: {e}")
        print()
        return []

# Main functions
token_status = {}

def dailyclaim(token):
    try:
        url = f"https://api.nodepay.org/api/mission/complete-mission?"

        user_agents = load_user_agents()
        user_agent = next(
                (ua["user_agent"] for ua in user_agents if ua["token"] == token),
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": user_agent,
            "Content-Type": "application/json",
            "Origin": "https://app.nodepay.ai",
            "Referer": "https://app.nodepay.ai/"
        }
        data = {"mission_id": "1"}
        response = requests.post(url, headers=headers, json=data, impersonate="chrome110")

        if response.status_code == 200:
            try:
                json_response = response.json()
                if json_response.get('success'):
                    if token_status.get(token) != "claimed":
                        logger.info("<green>Claim Reward Success!</green>")
                        token_status[token] = "claimed"
                else:
                    if token_status.get(token) != "failed":
                        logger.info("<yellow>Reward Already Claimed!</yellow>")
                        token_status[token] = "failed"
            except json.JSONDecodeError:
                if SHOW_REQUEST_ERROR_LOG:
                    logger.error("<red>Failed to decode JSON from API response.</red>")
        else:
            if SHOW_REQUEST_ERROR_LOG:
                logger.error(f"<red>Unexpected HTTP {response.status_code} during daily claim.</red>")

    except requests.exceptions.RequestException as e:
        if SHOW_REQUEST_ERROR_LOG:
            logger.error(f"Request failed: {e}")

async def call_api(url, data, token, proxy=None, timeout=60):
    user_agents = load_user_agents()
    user_agent = next(
        (ua["user_agent"] for ua in user_agents if ua["token"] == token),
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
    )
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
        response = requests.post(url, json=data, headers=headers, proxies=proxies, impersonate="chrome110", timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.SSLError as e:
        if SHOW_REQUEST_ERROR_LOG:
            logger.error(f"<red>SSL Error during API call to {url}: {e}</red>")
        return None
    except requests.exceptions.ConnectionError as e:
        if SHOW_REQUEST_ERROR_LOG:
            logger.error(f"<red>Connection Error during API call to {url}: {e}</red>")
        return None
    except requests.exceptions.RequestException as e:
        if response.status_code == 403:
            logger.error(f"<red>HTTP 403: Access denied during API call. Possible reasons: invalid token or blocked IP/proxy.</red>")
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "unknown")
            logger.warning(f"<yellow>HTTP 429: Too many requests during API call. Rate limit hit. Retry after {retry_after} seconds.</yellow>")
        else:
            if SHOW_REQUEST_ERROR_LOG:
                logger.error(f"<red>Request Error during API call to {url}: {e}</red>")
        return None
    except json.JSONDecodeError as e:
        if SHOW_REQUEST_ERROR_LOG:
            logger.error(f"<red>JSON Decode Error from API response at {url}: {e}</red>")
        return None
    except Exception as e:
        if SHOW_REQUEST_ERROR_LOG:
            logger.error(f"<red>Unexpected error during API call to {url}: {e}</red>")
        return None

async def get_account_info(token, proxy=None):
    url = DOMAIN_API["SESSION"]
    try:
        response = await call_api(url, {}, token, proxy)
        if response and response.get("code") == 0:
            data = response["data"]

            account_info = {
                "name": data.get("name", "Unknown"),
                "ip_score": data.get("ip_score", "N/A"),
                **data
            }

            return account_info

        logger.error(f"<red>Failed to retrieve account info for token {token[-10:]}: {response.get('msg', 'Unknown error')}</red>")
    except Exception as e:
        logger.error(f"<red>Error fetching account info for token {token[-10:]}: {e}</red>")
    return None

async def start_ping(token, account_info, proxy, ping_interval):
    user_agents = load_user_agents()
    user_agent = next(
        (ua["user_agent"] for ua in user_agents if ua["token"] == token),
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
    )
    browser_id = str(uuid.uuid4())
    url_index = 0
    last_valid_points = 0
    proxies = {"http": proxy, "https": proxy} if proxy else None
    name = account_info.get("name", "Unknown")

    while True:
        try:
            if not DOMAIN_API["PING"]:
                logger.error("No PING URLs available in DOMAIN_API['PING'].")
                break

            url = DOMAIN_API["PING"][url_index]
            data = {
                "id": account_info.get("uid"),
                "browser_id": browser_id,
                "timestamp": int(time.time())
            }

            headers = {"User-Agent": user_agent}
            response = await call_api(url, data, token, proxy, timeout=120)
            
            if response is not None:
                if response.get("data"):
                    response_data = response["data"]
                    ip_score = response_data.get("ip_score", "N/A")
                    ip_address = get_ip_address()

                    total_points = await get_total_points(token, ip_score=ip_score, proxy=proxy, name=name)

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
                    logger.warning(f"<yellow>Invalid or no response from {url}</yellow>")

                    if hasattr(response, 'status_code'):
                        logger.warning(f"<yellow>HTTP {response.status_code}: {response.text}</yellow>")
                    else:
                        logger.warning(f"<yellow>No status code available for the response.</yellow>")
                    
                url_index = (url_index + 1) % len(DOMAIN_API["PING"])

            else:
                logger.warning(f"<yellow>Received None response from {url}</yellow>")

        except RequestException as e:
            logger.error(f"<red>Error during pinging: {e}</red>")
        except Exception as e:
            logger.error(f"<red>Unexpected error in pinging: {e}</red>")
        finally:
            await asyncio.sleep(ping_interval)

async def process_account(token, use_proxy, proxies=None, ping_interval=2.0, name="Unknown"):
    proxies = proxies or []

    account_info = await get_account_info(token, proxy=proxies[0] if proxies and use_proxy else None)
    
    if not account_info:
        logger.error(f"<red>Failed to fetch account info for token {token[-10:]}</red>")
        return

    name = account_info.get("name", "Unknown")
    ip_score = account_info.get("ip_score", "N/A")

    for proxy in (proxies if use_proxy else [None]):
        try:
            response = await call_api(DOMAIN_API["SESSION"], {}, token, proxy)
            if response and response.get("code") == 0:
                account_info = response["data"]
                log_user_data(account_info)
                ip_score = account_info.get("ip_score", ip_score)
                await start_ping(token, account_info, proxy, ping_interval)
                return

            logger.warning(f"<yellow>Invalid or no response for token with proxy {proxy}</yellow>")
        except Exception as e:
            logger.error(f"<red>Unhandled error with proxy {proxy} for token {token[-10:]}: {e}</red>")

    logger.error(f"<red>All attempts failed for token {token[-10:]}</red>")

async def get_total_points(token, ip_score="N/A", proxy=None, name="Unknown"):
    try:
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )

        url = DOMAIN_API["DEVICE_NETWORK"]
        user_agents = load_user_agents()
        user_agent = next(
                (ua["user_agent"] for ua in user_agents if ua["token"] == token),
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": user_agent,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Referer": "https://app.nodepay.ai/",
            "Connection": "keep-alive",
        }

        proxies = {"http": proxy, "https": proxy} if proxy else None

        response = scraper.get(url, headers=headers, proxies=proxies, timeout=60)

        if response.status_code == 200:
            try:
                data = response.json()
                if data.get("success"):
                    devices = data.get("data", [])
                    total_points = sum(device.get("total_points", 0) for device in devices)
                    logger.info(
                        f"<magenta>Earn successfully</magenta>, "
                        f"Fetching total points for user: <magenta>{name}</magenta>"
                    )
                    return total_points
                else:
                    logger.error(f"<red>Failed to fetch points: {data.get('msg', 'Unknown error')}</red>")
            except json.JSONDecodeError:
                logger.error(f"<red>Failed to decode JSON response.</red>")
        elif response.status_code == 403:
            logger.error(
                f"<red>HTTP 403: Access denied.</red> "
                f"<red>Token or proxy may be blocked.</red> Proxy: <cyan>{proxy or 'No Proxy'}</cyan>"
            )
        else:
            logger.error(
                f"<red>Unexpected HTTP {response.status_code} while fetching points.</red>"
            )
    except requests.exceptions.RequestException as e:
        logger.error(f"<red>Error in request: {e}</red> (Proxy: {proxy or 'No Proxy'})")
    except Exception as e:
        logger.error(f"<red>Unexpected error while fetching total points: {e}</red>")
    return 0

async def validate_token(token):
    url = DOMAIN_API["SESSION"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200 and response.json().get("code") == 0:
            logger.info(f"<cyan>Token {token[-10:]} is valid.</cyan>")
            return True
        else:
            logger.warning(f"<yellow>Invalid token: {response.text}</yellow>")
    except Exception as e:
        logger.error(f"<red>Error validating token: {e}</red>")
    return False

async def main():
    use_proxy = ask_user_for_proxy()
    proxies = load_proxies() if use_proxy else []

    try:
        with open('tokens.txt', 'r') as file:
            tokens = file.read().splitlines()
    except FileNotFoundError:
        logger.error("File 'tokens.txt' not found. Please create it and add your tokens.")
        exit()

    token_proxy_pairs = assign_proxies_to_tokens(tokens, proxies) if use_proxy else [(token, None) for token in tokens]

    users_data = []
    for token in tokens:
        account_info = await get_account_info(token)
        if account_info:
            users_data.append(account_info)
        else:
            logger.error(f"Failed to retrieve account info for token {token[-10:]}. Skipping.")

    log_user_data(users_data)

    for token in tokens:
        account_info = await get_account_info(token)
        if account_info:
            name = account_info.get("name", "Unknown")
            logger.info(f"Running daily claim for user <cyan>{name}</cyan>")
            dailyclaim(token)
        else:
            logger.error(f"Failed to retrieve account info for token {token[-10:]}. Skipping daily claim.")

    tasks = []
    for token, proxy in token_proxy_pairs:
        account_info = await get_account_info(token)
        if account_info:
            name = account_info.get("name", "Unknown")
        else:
            name = "Unknown"

        logger.info(
            f"Running token for user <cyan>{name}</cyan> with "
            f"{'proxy <cyan>' + proxy + '</cyan>' if proxy else 'no proxy'}"
        )

        tasks.append(process_account(token, use_proxy=bool(proxy), proxies=[proxy] if proxy else [], ping_interval=4.0))

    await asyncio.gather(*tasks)

if __name__ == '__main__':
    try:
        print_header()
        generate_user_agents("tokens.txt", "user_agents.json")
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Program terminated by user.")
