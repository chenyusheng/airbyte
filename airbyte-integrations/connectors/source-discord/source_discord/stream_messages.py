#
# Copyright (c) 2022 Airbyte, Inc., all rights reserved.
#

import time
from datetime import datetime
from typing import Any, Iterable, Mapping, MutableMapping, Optional

import requests
from airbyte_cdk.models import SyncMode
from airbyte_cdk.sources.streams.http import HttpStream
from .stream_channels import Channels
from requests.exceptions import HTTPError
from airbyte_cdk.sources.streams import Stream
from abc import ABC

SECONDS_BETWEEN_PAGE = 5


class DiscordMessagesStream(HttpStream, ABC):
    url_base = "https://discord.com"
    cursor_field = "timestamp"
    primary_key = "id"

    def __init__(self, config: Mapping[str, Any], **_):
        super().__init__()
        self.config = config
        self.message_limit = 2
        self.server_token = config["server_token"]
        self.guild_id = '864829036294307881'
        self.job_time = config['job_time']
        self.total = 0
        self.total_limit = 2
        self._cursor_value = datetime.utcnow()
        self.run_times = 0
        self.channels_stream = Channels(
            config=config
        )

    def request_headers(self, **_) -> Mapping[str, Any]:
        return {"Authorization": "Bot " + self.server_token}

    def request_params(
            self, stream_state: Mapping[str, Any], stream_slice: Mapping[str, any] = None, next_page_token: Mapping[str, Any] = None
    ) -> MutableMapping[str, Any]:
        print('request_params------', self.run_times)
        if not next_page_token:
            return {'limit': self.message_limit}

        return {'before': next_page_token['last_message_id'], 'limit': self.message_limit}

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        messages = response.json()
        print('self.total ***********', self.total)

        if self.total >= self.total_limit:
            print('self.total~~~~~~~~~~', self.total, self.total_limit)
            return None

        if len(messages) < self.message_limit:
            print('self.total~~~~~~~~~~', self.total, self.total_limit)
            return None

        return {'last_message_id': messages[-1]['id']}

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:

        records = response.json()
        for record in records:
            yield self.transform(record=record, **kwargs)

        # self.run_times = self.run_times + 1
        #
        # messages = response.json()
        # if not messages or len(messages) <= 0:
        #     return []
        #
        # message_results = []
        # for message in messages:
        #     self.total = self.total + 1
        #     reaction_count = 0
        #
        #     if 'reactions' in message.keys():
        #         reactions = message['reactions']
        #         for reaction in reactions:
        #             reaction_count = reaction_count + reaction['count']
        #
        #     thread = None
        #     if 'thread' in message.keys():
        #         thread = message['thread']
        #
        #     result = {
        #         'message_id': message['id'],
        #         'message_type': message['type'],
        #         'content': message['content'],
        #         'message_timestamp': message['timestamp'],
        #         'edited_timestamp': message['edited_timestamp'],
        #         'timestamp': self.job_time,
        #         'channel_id': message['channel_id'],
        #         'guild_id': self.guild_id,
        #         'author_id': message['author']['id'],
        #         'author_username': message['author']['username'],
        #         'referenced_message_id': message['referenced_message']['id'] if 'referenced_message' in message.keys() else None,
        #         'referenced_message_type': message['referenced_message']['type'] if 'referenced_message' in message.keys() else None,
        #         'reaction_count': reaction_count,
        #         'thread_id': thread['id'] if thread else None,
        #         'thread_parent_id': thread['parent_id'] if thread else None,
        #         'thread_owner_id': thread['owner_id'] if thread else None,
        #         'thread_name': thread['name'] if thread else None,
        #         'thread_message_count': thread['message_count'] if thread else None,
        #         'thread_message_member_count': thread['member_count'] if thread else None,
        #         'mention_count': len(message['mentions']),
        #         'mention_everyone': message['mention_everyone']
        #     }
        #     print(result)
        #     message_results.append(result)
        # print('self.run_times-------------', self.run_times)
        # return []

    def read_records(
            self, stream_slice: Optional[Mapping[str, Any]] = None, stream_state: Mapping[str, Any] = None, **kwargs
    ) -> Iterable[Mapping[str, Any]]:
        print('supper----->>>>>>>>', stream_slice)
        try:
            yield from super().read_records(stream_slice=stream_slice, **kwargs)
        except HTTPError as e:
            if not (self.skip_http_status_codes and e.response.status_code in self.skip_http_status_codes):
                raise e


class Messages(DiscordMessagesStream):
    cursor_field = "updated"

    def read_incremental(self, stream_instance: Stream, stream_state: MutableMapping[str, Any]):
        slices = stream_instance.stream_slices(sync_mode=SyncMode.incremental, stream_state=stream_state)
        for _slice in slices:
            records = stream_instance.read_records(sync_mode=SyncMode.incremental, stream_slice=_slice, stream_state=stream_state)
            for record in records:
                yield record

    def path(self, stream_slice: Mapping[str, Any], **kwargs) -> str:
        print("------------>>>>>>>>>stream_slicestream_slicestream_slicestream_slice", stream_slice)
        print('====>>>>>url', f"api/v10/channels/{stream_slice['id']}/messages")
        return f"api/v10/channels/{stream_slice['id']}/messages"
        # return f"api/v10/channels/864833940036386826/messages"
        # return f"api/v10/channels/1085514352913829909/messages?limit=100"

    def read_records(
            self, stream_slice: Optional[Mapping[str, Any]] = None, stream_state: Mapping[str, Any] = None, **kwargs
    ) -> Iterable[Mapping[str, Any]]:
        print('read_records-------->>>>', stream_slice)
        incremental_records = self.read_incremental(self.channels_stream, stream_state=stream_state)
        for issue in incremental_records:
            stream_slice = {"id": issue["id"]}
            print('issue ========>>>>', issue)
            print(stream_slice)
            print(stream_state)
            yield from super().read_records(stream_slice=stream_slice, stream_state=stream_state, **kwargs)

    def parse_response(self, response: requests.Response, **kwargs) -> Iterable[Mapping]:
        records = response.json()
        for record in records:
            yield self.transform(record=record, **kwargs)

    def transform(self, record: MutableMapping[str, Any], stream_slice: Mapping[str, Any], **kwargs) -> MutableMapping[str, Any]:
        print('Messages----->>>>', record)
        return record




# Discord returns data with different time formats,
# so there is need to "normalize" it
def string_to_timestamp(text_timestamp: str) -> datetime:
    clean_text_timestamp = text_timestamp[0:19]
    return datetime.strptime(clean_text_timestamp, "%Y-%m-%dT%H:%M:%S")
