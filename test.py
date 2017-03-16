# coding=utf-8
from alipay_fetcher import AlipayFetcher

fetcher = AlipayFetcher(alipay_account='YourAlipayAccount',
                        alipay_password='YourAlipayPassword',
                        dama2_account='YourDama2Account',
                        dama2_password='YourDama2Password')
fetcher.run()
