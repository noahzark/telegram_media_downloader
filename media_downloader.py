"""Downloads media from telegram."""
import asyncio
import os
import pprint
import sys
from typing import List

import pyrogram
import yaml

from log import logger
from media_handler import download_media, StaticInfo
from utils.meta import print_meta


def update_config(config: dict):
    """
    Update exisitng configuration file.

    Parameters
    ----------
    config: dict
        Configuraiton to be written into config file.
    """
    config["ids_to_retry"] = list(set(config["ids_to_retry"] + StaticInfo.FAILED_IDS))
    with open(config['filename'], "w") as yaml_file:
        yaml.dump(config, yaml_file, default_flow_style=False)
    logger.info("Updated last read message_id to config file")


async def process_messages(
        client: pyrogram.client.Client,
        messages: List[pyrogram.types.Message],
        media_types: List[str],
        file_formats: dict,
) -> int:
    """
    Download media from Telegram.

    Parameters
    ----------
    client: pyrogram.client.Client
        Client to interact with Telegram APIs.
    messages: list
        List of telegram messages.
    media_types: list
        List of strings of media types to be downloaded.
        Ex : `["audio", "photo"]`
        Supported formats:
            * audio
            * document
            * photo
            * video
            * voice
    file_formats: dict
        Dictionary containing the list of file_formats
        to be downloaded for `audio`, `document` & `video`
        media types.

    Returns
    -------
    int
        Max value of list of message ids.
    """
    message_ids = await asyncio.gather(
        *[
            download_media(client, message, media_types, file_formats)
            for message in messages
        ]
    )

    last_message_id = max(message_ids)
    return last_message_id


async def begin_import(config: dict, pagination_limit: int, debug=False) -> dict:
    """
    Create pyrogram client and initiate download.

    The pyrogram client is created using the ``api_id``, ``api_hash``
    from the config and iter throught message offset on the
    ``last_message_id`` and the requested file_formats.

    Parameters
    ----------
    config: dict
        Dict containing the config to create pyrogram client.
    pagination_limit: int
        Number of message to download asynchronously as a batch.
    debug: bool
        Whether to enable debug downloading.

    Returns
    -------
    dict
        Updated configuraiton to be written into config file.
    """
    client = pyrogram.Client(
        "media_downloader",
        api_id=config["api_id"],
        api_hash=config["api_hash"],
        workers=4
    )
    pyrogram.session.Session.notice_displayed = True
    await client.start()

    last_read_message_id: int = config["last_read_message_id"]
    messages_iter = client.iter_history(
        config["chat_id"],
        offset_id=last_read_message_id,
        reverse=True,
    )
    pagination_count: int = 0
    messages_list: list = []

    # read messages in batches
    message: pyrogram.types.Message
    async for message in messages_iter:
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(message)
        if pagination_count != pagination_limit:
            # append message to list
            pagination_count += 1
            messages_list.append(message)
        else:
            # handle last message
            last_read_message_id = await process_messages(
                client,
                messages_list,
                config["media_types"],
                config["file_formats"],
            )
            pagination_count = 0
            messages_list = [message]
            config["last_read_message_id"] = last_read_message_id
            # update_config(config)
            if debug:
                break

    if len(messages_list):
        last_read_message_id = await process_messages(
            client,
            messages_list,
            config["media_types"],
            config["file_formats"],
        )

    await client.stop()
    config["last_read_message_id"] = last_read_message_id
    return config


def main():
    """Main function of the downloader."""
    config_filename = len(sys.argv) > 1 and sys.argv[1] or "config.yaml"
    with open(os.path.join(StaticInfo.THIS_DIR, config_filename)) as f:
        config = yaml.safe_load(f)
    config["filename"] = config_filename

    # create download directory if it doesn't exist
    StaticInfo.CHAT_ID = config_filename[:config_filename.find('.')]
    if not os.path.exists(StaticInfo.CHAT_ID):
        os.mkdir(StaticInfo.CHAT_ID)

    updated_config = asyncio.get_event_loop().run_until_complete(
        begin_import(config, pagination_limit=1, debug=True)
    )
    if StaticInfo.FAILED_IDS:
        logger.info(
            "Downloading of %d files failed. "
            "Failed message ids are added to config file.\n"
            "Functionality to re-download failed downloads will be added "
            "in the next version of `Telegram-media-downloader`",
            len(set(StaticInfo.FAILED_IDS)),
        )
    update_config(updated_config)


if __name__ == "__main__":
    print_meta(logger)
    main()
