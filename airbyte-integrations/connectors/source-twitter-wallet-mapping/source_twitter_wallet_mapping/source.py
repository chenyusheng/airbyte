#
# Copyright (c) 2022 Airbyte, Inc., all rights reserved.
#
import datetime
import time
from abc import ABC
from typing import Any, Iterable, List, Mapping, MutableMapping, Optional, Tuple

import pydash
import re
import requests
from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams import Stream
from airbyte_cdk.sources.streams.http import HttpStream
from airbyte_cdk.sources.streams.http.auth import TokenAuthenticator


# Basic full refresh stream
class TwitterWalletMapping(HttpStream, ABC):
    primary_key = "reply_id"
    cursor_field = "reply_created_at"
    url_base = "https://api.twitter.com"

    def __init__(self, authenticator: TokenAuthenticator, config: Mapping[str, Any], **kwargs):
        super().__init__()
        self.api_key = config["api_key"]
        self.twitter_uri = config["twitter_uri"]
        self.fp_api = config["fp_api"]
        self.x_token = config["x_token"]
        self.submit_id = config["submit_id"]

        self.job_time = datetime.datetime.now()
        self.auth = authenticator

    def path(
        self, stream_state: Mapping[str, Any] = None, stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> str:
        return "/2/tweets/search/recent"

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        result = response.json()
        meta = result['meta']

        # api 限制 15 calls/min,所以要sleep 一下
        if 'next_token' in meta.keys():
            print("next_page_token find next page,sleep 20 seconds!")
            time.sleep(20)
            return {"pagination_token": meta["next_token"]}
        else:
            return None

    # use auth now
    def request_headers(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, Any] = None, next_page_token: Mapping[str, Any] = None
    ) -> Mapping[str, Any]:
        # The api requires that we include apikey as a header so we do that in this method
        print("request_headers.auth: ", self.auth.get_auth_header())
        return self.auth.get_auth_header()

    def request_params(
        self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        tweet_author_name = str(self.twitter_uri).split('/')[3]
        tweet_id = str(self.twitter_uri).split('/')[5]
        print("next_page_token: ", next_page_token)
        param = {
            'query': 'to:{}'.format(tweet_author_name),
            'since_id': tweet_id,
            'tweet.fields': 'author_id,created_at,public_metrics',
            'expansions': 'author_id',
            'user.fields': 'username',
            'max_results': 100
        }
        if next_page_token:
            param.update({
                'next_token': next_page_token["pagination_token"]
            })
        print(f'param: {param}')
        return param

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        # reply detail data
        reply_detail_data = []

        # wallet mapping list in all reply detail
        reply_wallet_list = []

        result = response.json()

        if 'data' not in result.keys():
            return reply_detail_data

        for reply_detail in result['data']:
            reply_author_id = reply_detail['author_id']
            reply_text = reply_detail['text']
            reply_author = pydash.find(result['includes']['users'], {'id': reply_author_id})

            reply_wallet_list.extend(self.format_reply_text(reply_author_id, reply_author['username'], reply_text))

            # reply detail data
            reply_detail_data.append({
                'submit_id': self.submit_id,
                'tweet_uri': self.twitter_uri,
                'tweet_id': str(self.twitter_uri).split('/')[5],
                'tweet_author_name': str(self.twitter_uri).split('/')[3],
                'reply_id': reply_detail['id'],
                'reply_author_id': reply_author_id,
                'reply_name': reply_author['name'],
                'reply_username': reply_author['username'],
                'reply_text': reply_text,
                'reply_public_metrics': reply_detail['public_metrics'],
                'reply_edit_history_tweet_ids': reply_detail['edit_history_tweet_ids'],
                'reply_created_at': reply_detail['created_at'],
                'job_time': self.job_time
            })

        # 写入 footprint wallet_address_mapping
        requests.post(
            url=self.fp_api,
            headers={'x-token': self.x_token},
            json={'list': reply_wallet_list}
        )
        print(f'''reply_wallet_list: {len(reply_wallet_list), pydash.get(reply_wallet_list, '0')}''')

        return reply_detail_data

    def format_reply_text(self, reply_author_id, reply_author_name, reply_text):
        wallet_json_list = []

        # 定义以太坊钱包地址的正则表达式
        ethereum_regex = r'(0x[a-fA-F0-9]{40})'

        # 定义比特币钱包地址的正则表达式
        bitcoin_regex = r'([13][a-km-zA-HJ-NP-Z0-9]{26,35})'

        # 定义波场(TRON)钱包地址的正则表达式
        tron_regex = r'(T[1-9a-km-zA-HJ-NP-Z]{33})'

        # 使用正则表达式查找所有的钱包地址
        ethereum_addresses = re.findall(ethereum_regex, reply_text)
        bitcoin_addresses = re.findall(bitcoin_regex, reply_text)
        tron_addresses = re.findall(tron_regex, reply_text)

        wallet_addresses = ethereum_addresses or bitcoin_addresses or tron_addresses
        if wallet_addresses:
            for wallet_address in wallet_addresses:
                wallet_json_list.append({
                    'twitterId': reply_author_id,
                    'twitterName': reply_author_name,
                    'walletAddress': wallet_address
                })
        return wallet_json_list

class SourceTwitterWalletMapping(AbstractSource):
    def check_connection(self, logger, config) -> Tuple[bool, any]:
        api_key = config["api_key"]
        twitter_uri = config["twitter_uri"]
        x_token = config["x_token"]
        fp_api = config["fp_api"]
        if api_key and twitter_uri and x_token and fp_api:
            return True, None
        else:
            return False, "Api key of Screen Name should not be null!"

    def streams(self, config: Mapping[str, Any]) -> List[Stream]:
        print("config: \n", config)
        auth = TokenAuthenticator(token=config["api_key"])
        print("auth: \n", auth.get_auth_header())
        return [TwitterWalletMapping(authenticator=auth, config=config)]
