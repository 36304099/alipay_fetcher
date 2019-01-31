# coding=utf-8
import json
import logging
import os
from random import uniform as random_time
from time import sleep

import requests
from PIL import Image
from lxml import html
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException


class AlipayFetcher:
    def __init__(self, alipay_account=None, alipay_password=None, check_interval=60):

        self.global_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:42.0) Gecko/20100101 Firefox/42.0',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        self.cur_dir = os.path.dirname(os.path.abspath(__file__))
        self.screen_shot = os.path.join(self.cur_dir, 'screen_shot.png')
        self.captcha_image = os.path.join(self.cur_dir, 'captcha.png')
        self.login_url = 'https://auth.alipay.com/login/index.htm'
        self.transfer_check_url = 'https://lab.alipay.com/consume/record/items.htm'
        self.check_interval = check_interval
        self.session_life = 0
        self.alipay_account = alipay_account
        self.alipay_password = alipay_password
        self.alipay_cookies = None
        self.transfer_tables = None
        logging.basicConfig(level=logging.INFO)

    def fake_phantom_header(self):
        for key, value in enumerate(self.global_headers):
            webdriver.DesiredCapabilities.FIREFOX['firefox.page.customHeaders.{}'.format(key)] = value

    def resolve_captcha(self):
        # modify this function to handle captcha resolve,
        # or just manual input the code since we don't need to do this too much times
        logging.info('please check captcha.png for the check code.')
        code = input('Type in the check code:')
        return code.strip()

    def login_with_firefox(self):
        options = webdriver.FirefoxOptions()
        options.add_argument('-headless')
        driver = webdriver.Firefox(firefox_options=options)
        driver.get(self.login_url)
        driver.find_element_by_xpath('//ul[@id="J-loginMethod-tabs"]/li[2]').click()
        sleep(random_time(0.3, 0.8))

        username_form = driver.find_element_by_id('J-input-user')
        password_form = driver.find_element_by_id('password_rsainput')

        username_form.clear()
        for letter in self.alipay_account:
            username_form.send_keys(letter)
            sleep(random_time(0.1, 0.6))
        sleep(random_time(0.3, 0.8))
        for letter in self.alipay_password:
            password_form.send_keys(letter)
            sleep(random_time(0.1, 0.6))
        sleep(random_time(0.2, 0.8))

        captcha_input = driver.find_element_by_id('J-input-checkcode')
        captcha_image = driver.find_element_by_id('J-checkcode-img')

        captcha_location = captcha_image.location
        captcha_size = captcha_image.size

        if captcha_location['x'] != 0:
            img_left = captcha_location['x']
            img_top = captcha_location['y']
            img_right = captcha_location['x'] + captcha_size['width']
            img_bottom = captcha_location['y'] + captcha_size['height']

            driver.save_screenshot(self.screen_shot)
            img_item = Image.open(self.screen_shot)
            img_item = img_item.crop((img_left, img_top, img_right, img_bottom))
            img_item.save(self.captcha_image)

            captcha = self.resolve_captcha()
            if captcha:
                for letter in captcha:
                    captcha_input.send_keys(letter)
                    sleep(random_time(0.1, 0.6))
                driver.save_screenshot('fill_check_code.png')
        else:
            print('No Check Code Needed!')
        sleep(random_time(0.2, 0.6))
        login_btn = driver.find_element_by_id('J-login-btn')
        login_btn.click()

        sleep(random_time(0.7, 1.3))
        self.alipay_cookies = driver.get_cookies()
        logging.info('New Session Created!')
        driver.quit()

    @staticmethod
    def apply_cookies_to_session(cookies=None, session=None):
        for cookie in cookies:
            c = {cookie['name']: cookie['value']}
            session.cookies.update(c)

    def check_alipay_transfer(self):
        if not self.alipay_cookies:
            logging.debug('Previous login failed!')
            # previous login failed,main function will try to re-login again
            return None
        request_session = requests.session()
        self.apply_cookies_to_session(cookies=self.alipay_cookies, session=request_session)
        while True:
            response = request_session.get(url=self.transfer_check_url, headers=self.global_headers)
            if str(response.url).startswith(self.login_url):
                logging.warning('Session expired with lifetime:{}'.format(self.session_life))
                # previous login expired,main function will try to re-login again
                return None
            tree = html.fromstring(response.text)
            transfer_list = tree.xpath("//tr[@class='record-list']")
            if not len(transfer_list):
                logging.info('No transfer records found!')
                self.transfer_tables = None
            else:
                self.transfer_tables = dict()
                for transfer in transfer_list:
                    try:
                        transfer.xpath(".//td[@class='amount income']")[0]
                    except IndexError:
                        # Not a income event,don't care
                        continue
                    t_id = transfer.xpath(".//div[@class='consumeBizNo']")[0].text.strip()
                    self.transfer_tables[t_id] = dict()
                    self.transfer_tables[t_id]['id'] = t_id

                    t_time = transfer.xpath(".//td[@class='time']")[0].text.strip()
                    self.transfer_tables[t_id]['time'] = t_time

                    t_info = transfer.xpath(".//li[@class='name emoji-li']")[0].text.strip()
                    self.transfer_tables[t_id]['info'] = t_info

                    t_income = transfer.xpath(".//td[@class='amount income']")[0].text.strip()
                    self.transfer_tables[t_id]['income'] = t_income

                    t_balance = transfer.xpath(".//td[@class='balance']")[0].text.strip()
                    self.transfer_tables[t_id]['balance'] = t_balance

                    t_from = transfer.xpath(".//td[@class='from']//li[@class='name']")[0].text.strip()
                    self.transfer_tables[t_id]['from'] = t_from

            self.data_process()
            # visit below page to keep cookies alive
            request_session.get(url='https://my.alipay.com/portal/i.htm', headers=self.global_headers)
            sleep(self.check_interval)
            self.session_life += self.check_interval

    def data_process(self):
        # modify this function to handle income transaction data for your own application
        if self.transfer_tables:
            for item in self.transfer_tables:
                logging.info(self.transfer_tables[item])

    def run(self):
        while True:
            try:
                self.login_with_firefox()
                self.check_alipay_transfer()
            except KeyboardInterrupt:
                logging.info('Exit by user...')
                return
