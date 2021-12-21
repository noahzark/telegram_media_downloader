import asyncio
import os
from datetime import datetime as dt
from typing import List, Tuple, Optional

import pyrogram

from log import logger
from utils.file_management import get_next_name, manage_duplicate_file


class StaticInfo:
    FAILED_IDS: list = []
    CHAT_ID = ''
    THIS_DIR = os.path.dirname(os.path.abspath(__file__))


async def download_media(
        client: pyrogram.client.Client,
        message: pyrogram.types.Message,
        media_types: List[str],
        file_formats: dict,
):
    """
    Download media from Telegram.

    Each of the files to download are retried 3 times with a
    delay of 5 seconds each.

    Parameters
    ----------
    client: pyrogram.client.Client
        Client to interact with Telegram APIs.
    message: pyrogram.types.Message
        Message object retrived from telegram.
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
        Current message id.
    """
    logger.info("Downloading media of message id - %s", message.message_id)
    for retry in range(3):
        try:
            if message.media is None:
                return message.message_id
            for _type in media_types:
                _media = getattr(message, _type, None)
                if _media is None:
                    continue
                file_name, file_format = await _get_media_meta(_media, _type)
                save_name = file_name + '.' + file_format
                if _can_download(_type, file_formats, file_format):
                    logger.info("start downloading - %s", file_name)
                    if _is_exist(save_name):
                        save_name = get_next_name(save_name)
                        download_path = await client.download_media(
                            message, file_name=save_name
                        )
                        download_path = manage_duplicate_file(download_path)
                    elif getattr(message, 'photo'):
                        photo: pyrogram.types.Photo = getattr(message, 'photo')
                        download_path = await client.download_media(
                            photo.file_id, file_name=save_name
                        )
                    elif getattr(message, 'video'):
                        thumb: pyrogram.types.Thumbnail
                        for thumb in message.video.thumbs:
                            download_path = await client.download_media(
                                thumb, file_name=file_name + '.jpg'
                            )
                        """
                        download_path = await client.download_media(
                            message, file_name=save_name
                        )
                        """
                    else:
                        download_path = await client.download_media(
                            message, file_name=save_name
                        )
                    if download_path:
                        logger.info("<download_media> downloaded - %s", download_path)
                    else:
                        logger.warning("<download_media> failed - %s", file_name)
            break
        except pyrogram.errors.exceptions.bad_request_400.BadRequest:
            logger.warning(
                "Message[%d]: file reference expired, refetching...",
                message.message_id,
            )
            message = await client.get_messages(
                chat_id=message.chat.id,
                message_ids=message.message_id,
            )
            if retry == 2:
                # pylint: disable = C0301
                logger.error(
                    "Message[%d]: file reference expired for 3 retries, download skipped.",
                    message.message_id,
                )
                StaticInfo.FAILED_IDS.append(message.message_id)
        except TypeError:
            # pylint: disable = C0301
            logger.warning(
                "Timeout Error occured when downloading Message[%d], retrying after 5 seconds",
                message.message_id,
            )
            await asyncio.sleep(5)
            if retry == 2:
                logger.error(
                    "Message[%d]: Timing out after 3 reties, download skipped.",
                    message.message_id,
                )
                StaticInfo.FAILED_IDS.append(message.message_id)
        except Exception as e:
            # pylint: disable = C0301
            logger.error(
                "Message[%d]: could not be downloaded due to following exception:\n[%s].",
                message.message_id,
                e,
                exc_info=True,
            )
            StaticInfo.FAILED_IDS.append(message.message_id)
            break
    return message.message_id


async def _get_media_meta(
        media_obj: pyrogram.types.messages_and_media, _type: str
) -> Tuple[str, Optional[str]]:
    """
    Extract file name and file id.

    Parameters
    ----------
    media_obj: pyrogram.types.messages_and_media
        Media object to be extracted.
    _type: str
        Type of media object.

    Returns
    -------
    tuple
        file_name, file_format
    """
    logger.info("Found media mime type - %s", media_obj.mime_type)
    if _type in ["audio", "document", "video"]:
        file_format: Optional[str] = media_obj.mime_type.split("/")[-1]
    else:
        file_format = None

    if _type == "voice":
        # audios
        file_format = media_obj.mime_type.split("/")[-1]
        file_name: str = os.path.join(
            StaticInfo.THIS_DIR,
            StaticInfo.CHAT_ID,
            _type,
            "voice_{}.{}".format(
                dt.utcfromtimestamp(media_obj.date).isoformat(), file_format
            ),
        )
    elif _type == 'photo' and getattr(media_obj, "file_name", None) is None:
        # images
        file_name = os.path.join(
            StaticInfo.THIS_DIR, StaticInfo.CHAT_ID, _type,
            str(getattr(media_obj, "date", None)) or ""
        )
        file_name += (getattr(media_obj, "file_unique_id", None) or "") + ".jpg"
    else:
        # videos
        file_name = os.path.join(
            StaticInfo.THIS_DIR, StaticInfo.CHAT_ID, _type,
            str(media_obj.date) + '-' + (getattr(media_obj, "file_name", None) or media_obj.file_unique_id)
        )
    return file_name, file_format


def _can_download(
        _type: str, file_formats: dict, file_format: Optional[str]
) -> bool:
    """
    Check if the given file format can be downloaded.

    Parameters
    ----------
    _type: str
        Type of media object.
    file_formats: dict
        Dictionary containing the list of file_formats
        to be downloaded for `audio`, `document` & `video`
        media types
    file_format: str
        Format of the current file to be downloaded.

    Returns
    -------
    bool
        True if the file format can be downloaded else False.
    """
    if _type in ["audio", "document", "video"]:
        allowed_formats: list = file_formats[_type]
        if not file_format in allowed_formats and allowed_formats[0] != "all":
            return False
    return True


def _is_exist(file_path: str) -> bool:
    """
    Check if a file exists and it is not a directory.

    Parameters
    ----------
    file_path: str
        Absolute path of the file to be checked.

    Returns
    -------
    bool
        True if the file exists else False.
    """
    return not os.path.isdir(file_path) and os.path.exists(file_path)
