import requests
import time
import configparser
import os
import json
import logging

CONST_CONFIG_PATH = "config.ini"
CONST_BITCOIN_PRICE_FILE_PATH = "btc.json"
CONST_BTC_LOG_FILE_PATH = "btc.log"
CONST_API_SECTION_NAME = "API"
CONST_API_KEY_NAME="api_key"
CONST_TELEGRAM_SECTION_NAME="TELEGRAM"
CONST_TELEGRAM_BOT_TOKEN_NAME="bot_token"
CONST_TELEGRAM_CHAT_ID_NAME="chat_id"
CONST_PERCENT_CHANGE = 5
CONST_TIME_INTERVAL = 10 * 60 #CoinMarketCap API restricts call to every 5 mins. So, we will call every 10 mins.

def configure_logger_with_console(log_file=CONST_BTC_LOG_FILE_PATH, log_level=logging.INFO):
    """
    Configures a logger that writes to a file and the console.

    Args:
        log_file (str): The name of the log file.
        log_level (int): The logging level (e.g., logging.INFO, logging.DEBUG).
    """

    logger = logging.getLogger(__name__)
    logger.setLevel(log_level)

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(log_level)

    console_handler = logging.StreamHandler() #added console handler
    console_handler.setLevel(log_level)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter) #format console handler

    logger.addHandler(file_handler)
    logger.addHandler(console_handler) #add console handler to logger

    return logger

def read_config(config_file, section, key):
    """
    Reads a key from a specified section in a config.ini file.

    Args:
        config_file (str): Path to the config.ini file.
        section (str): The section in the config.ini file.
        key (str): The key to read.

    Returns:
        str: The value of the key, or None if the key or section is not found.
    """
    config = configparser.ConfigParser()
    try:
        config.read(config_file)
        return config.get(section, key)
    except (configparser.NoSectionError, configparser.NoOptionError, FileNotFoundError):
        return None

def write_btc_price_list_to_json(price_time_dict):
    price_list=[]
    price_list.append(price_time_dict)
    try:
        with open(CONST_BITCOIN_PRICE_FILE_PATH, "r+") as file:
            current_data = json.load(file)
            current_data.extend(price_list)
            file.seek(0)
            json.dump(current_data, file, indent=4)
    except FileNotFoundError:
        with open(CONST_BITCOIN_PRICE_FILE_PATH, "w") as file:
            json.dump(price_list, file, indent=4)

def get_btc_price(api_key):
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": api_key
    }
    
    # make a request to the coinmarketcap api
    response = requests.get(url, headers=headers)
    response_json = response.json()

    # extract the bitcoin price from the json data
    btc_price = response_json["data"][0]
    return btc_price["quote"]["USD"]["price"]
    
# fn to send_message through telegram
def send_message(msg, bot_token, chat_id):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={chat_id}&text={msg}"
    try:
        # send the msg
        r = requests.get(url)
        return "Request URL was: "+url+"Message status: "+str(r.status_code)+" and payload: "+r.json().__str__()
    except Exception as e:
        return f"Error sending message: {e}"

def btc_calc_delta(price1, price2):
    return ((price2 - price1) / price1) * 100

def track_btc_price(api_key, console_logger, bot_token, chat_id):
    curr_time=time.time()
    btc_curr_price = btc_prev_price = get_btc_price(api_key)
    human_readable_time = time.ctime(curr_time)
    msg="Server restarted, starting to track BTC price..."
    console_logger.info(msg)
    console_logger.info(send_message(msg, bot_token, chat_id))

    # infinite loop
    while True:
        msg=f"BTC price at time: {human_readable_time} is ${round(btc_curr_price, 2)}"
        # Initial log
        console_logger.info(msg)
        console_logger.info(send_message(msg, bot_token, chat_id))
        # Write btc price json
        write_btc_price_list_to_json({"price": btc_curr_price, "time": str(curr_time)})

        # Update the data
        btc_curr_price = get_btc_price(api_key)
        curr_time=time.time()
        # if the price changes by %age from last price, put it on console_logger
        delta=btc_calc_delta(btc_prev_price, btc_curr_price)
        if abs(delta) > CONST_PERCENT_CHANGE:
            console_logger.info(f"BTC price changed by: {CONST_PERCENT_CHANGE}")
            console_logger.info(f"Current price: ${round(btc_curr_price, 2)}")
            console_logger.info(f"Previous price: ${round(btc_prev_price, 2)}")
            
            msg=f"%, price at time: {human_readable_time} is ${round(btc_curr_price, 2)}"
            if delta > 0:
                msg=f"Price increased by: {round(delta,2)}"+msg
            else:
                msg=f"Price decreased by: {round(delta,2)}"+msg
            console_logger.info(send_message(msg, bot_token, chat_id))
            console_logger.info(msg)
            btc_prev_price = btc_curr_price
        
        # fetch the price for every dash minutes
        time.sleep(CONST_TIME_INTERVAL)

def main():
    if not os.path.exists(CONST_CONFIG_PATH):
        console_logger.info(f"Config file not found at '{CONST_CONFIG_PATH}', cannot proceed.")
        return
    api_key = read_config(CONST_CONFIG_PATH, CONST_API_SECTION_NAME, CONST_API_KEY_NAME)
    if not api_key:
        console_logger.info(f"API key not found in the config file '{CONST_CONFIG_PATH}', cannot proceed.")
        return
    bot_token=read_config(CONST_CONFIG_PATH, CONST_TELEGRAM_SECTION_NAME, CONST_TELEGRAM_BOT_TOKEN_NAME)
    chat_id=read_config(CONST_CONFIG_PATH, CONST_TELEGRAM_SECTION_NAME, CONST_TELEGRAM_CHAT_ID_NAME)
    if not bot_token or not chat_id:
        console_logger.info("Bot token or chat id not found in the config file, cannot proceed.")
        return
    console_logger = configure_logger_with_console()
    track_btc_price(api_key, console_logger, bot_token, chat_id)

# fancy way to activate the main() function
if __name__ == "__main__":
    main()
