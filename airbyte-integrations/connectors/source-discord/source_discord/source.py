#
# Copyright (c) 2022 Airbyte, Inc., all rights reserved.
#

from typing import Any, List, Mapping, Tuple

import datetime
import requests
from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams import Stream

from .stream_channels import Channels
from .stream_members import Members
from .stream_messages import Messages
from .stream_roles import Roles
from .stream_serverPreview import ServerPreview


class SourceDiscord(AbstractSource):
    def check_connection(self, _, config) -> Tuple[bool, str]:
        url = "https://discord.com/api/users/@me"
        headers = {"Authorization": f"Bot {config['server_token']}"}
        response = requests.get(url, headers=headers)
        j_response = response.json()
        print(j_response)
        if "id" not in j_response:
            return False, "missing id"
        if j_response["id"] != config["bot_id"]:
            return False, "wrong id"
        return True, "accepted"

    def streams(self, config: Mapping[str, Any]) -> List[Stream]:
        # print(config["initial_timestamp"])
        # initial_timestamp = config["initial_timestamp"]
        config["job_time"] = datetime.datetime.now()

        channel_stream = Channels(config)
        message_stream = Messages(config)
        # message_stream.deltas = [channel_stream.name]
        # message_stream.cursor_field = 'channel_id'
        return [
            # ServerPreview(config),
            channel_stream,
            message_stream,
            # Members(config),
            # Roles(config),


        ]
