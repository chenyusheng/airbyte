#
# Copyright (c) 2022 Airbyte, Inc., all rights reserved.
#


import sys

from airbyte_cdk.entrypoint import launch
from source_twitter_metrics import SourceTwitterMetrics

if __name__ == "__main__":
    source = SourceTwitterMetrics()
    launch(source, sys.argv[1:])
