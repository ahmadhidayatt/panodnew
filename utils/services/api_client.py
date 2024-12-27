import asyncio
import json
import random
import requests

from curl_cffi import requests
from urllib.parse import urlparse
from utils.settings import DOMAIN_API, logger, Fore


# Function to build HTTP headers dynamically with hardcoded User-Agent
async def build_headers(url, account, method="POST", data=None):
    """
    Build headers for API requests dynamically with fixed User-Agent.
    """
    # Start with base headers
    headers = {
        "Authorization": f"Bearer {account.token}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    }

    # Add endpoint-specific headers
    endpoint_specific_headers = get_endpoint_headers(url)
    headers.update(endpoint_specific_headers)

    # Validate and serialize payload
    if method in ["POST", "PUT"] and data:
        if not isinstance(data, dict):
            logger.error(f"{Fore.CYAN}{account.index:02d}{Fore.RESET} - {Fore.RED}Invalid payload type: {type(data)}. Expected dict.{Fore.RESET}")
            raise ValueError("Payload must be a dictionary.")
        try:
            json_data = json.dumps(data, ensure_ascii=False).encode('utf-8')
        except ValueError as e:
            short_error = clean_error(e)
            logger.error(f"{Fore.CYAN}{account.index:02d}{Fore.RESET} - {Fore.RED}Failed to serialize payload:{Fore.RESET} {short_error}")
            raise

    # DEBUG: Log headers
    logger.debug(f"{Fore.CYAN}{account.index:02d}{Fore.RESET} - {Fore.GREEN}Headers built:{Fore.RESET} {headers}")
    return headers

# Function to return endpoint-specific headers based on the API
def get_endpoint_headers(url):
    """
    Return endpoint-specific headers based on the API.
    """
    EARN_MISSION_SET = {DOMAIN_API["EARN_INFO"], DOMAIN_API["MISSION"], DOMAIN_API["COMPLETE_MISSION"]}
    PING_LIST = DOMAIN_API["PING"]
    ACTIVATE_URL = DOMAIN_API["ACTIVATE"]

    if url in EARN_MISSION_SET:
        return {
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Host": "api.nodepay.ai"
        }

    elif url in PING_LIST or url == ACTIVATE_URL:
        return {
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://app.nodepay.ai/",
            "Origin": "chrome-extension://lgmpfmgeabnnlemejacfljbmonaomfmm",
            "priority": "u=1, i",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cors-site",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }

    # Default minimal headers
    return {"Accept": "application/json"}

# Function to send HTTP requests with error handling and custom headers
async def send_request(url, data, account, method="POST", timeout=120):
    """
    Perform HTTP requests with proper headers and error handling.
    """
    headers = await build_headers(url, account, method, data)
    proxies = {"http": account.proxy, "https": account.proxy} if account.proxy else None

    parsed_url = urlparse(url)
    path = parsed_url.path

    # Ensure headers are valid
    if not headers:
        logger.error(f"{Fore.CYAN}{account.index:02d}{Fore.RESET} - {Fore.RED}No headers generated for URL: {path}{Fore.RESET}")
        raise ValueError("Failed to generate headers")

    try:
        if method == "GET":
            response = requests.get(url, headers=headers, proxies=proxies, impersonate="safari15_5", timeout=timeout)
        else:
            response = requests.post(url, json=data, headers=headers, impersonate="safari15_5", proxies=proxies, timeout=timeout, verify=False)

        response.raise_for_status()

        try:
            return response.json()
        except ValueError as e:
            logger.error(f"{Fore.CYAN}{account.index:02d}{Fore.RESET} - {Fore.RED}Failed to decode JSON response:{Fore.RESET} {response.text}")
            raise

    except requests.exceptions.ProxyError:
        logger.error(f"{Fore.CYAN}{account.index:02d}{Fore.RESET} - {Fore.RED}Proxy connection failed. Unable to connect to proxy{Fore.RESET}")
        raise

    except requests.exceptions.RequestException as e:
        short_error = clean_error(e)
        logger.error(f"{Fore.CYAN}{account.index:02d}{Fore.RESET} - {Fore.RED}Request error:{Fore.RESET} {Fore.CYAN}{path}:{Fore.RESET} {short_error}")
        raise

# Function to send HTTP requests with retry logic using exponential backoff
async def retry_request(url, data, account, method="POST", max_retries=3):
    """
    Retry requests using exponential backoff.
    """
    retry_count = 0
    parsed_url = urlparse(url)
    path = parsed_url.path

    while retry_count < max_retries:
        try:
            return await send_request(url, data, account, method)

        except requests.exceptions.HTTPError as e:
            short_error = clean_error(e)
            status_code = e.response.status_code if e.response else "Unknown"
            logger.error(f"{Fore.CYAN}{account.index:02d}{Fore.RESET} - {Fore.RED}HTTP Error {status_code}:{Fore.RESET} {short_error}")
            if status_code == 403:
                logger.error(f"{Fore.CYAN}{account.index:02d}{Fore.RESET} - {Fore.RED}Forbidden: Check permissions or proxy.{Fore.RESET}")

        except Exception as e:
            short_error = clean_error(e)
            logger.error(f"{Fore.CYAN}{account.index:02d}{Fore.RESET} - {Fore.RED}Retry {retry_count}:{Fore.RESET} {short_error}")

        await exponential_backoff(retry_count)
        retry_count += 1

    raise Exception(f"{Fore.RED}Max retries reached for{Fore.RESET} {Fore.CYAN}{path}{Fore.RESET}")

# Function to implement exponential backoff delay during retries
async def exponential_backoff(retry_count, base_delay=1):
    """
    Perform exponential backoff for retries.
    """
    delay = base_delay * (2 ** retry_count) + random.uniform(0, 1)
    logger.info(f"{Fore.CYAN}00{Fore.RESET} - Retrying after {delay:.2f} seconds...")
    await asyncio.sleep(delay)

def clean_error(error):
    """
    Format error message to remove unnecessary details.
    """
    error_message = str(error)
    short_error = error_message.split(" See")[0]
    return short_error
