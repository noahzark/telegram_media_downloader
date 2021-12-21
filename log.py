import logging
import sys

from utils.log import LogFilter

FORMAT = '%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s'
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format=FORMAT, datefmt='%Y-%m-%d %H:%M:%S')
error_handler = logging.StreamHandler(sys.stderr)
error_handler.setLevel(logging.WARNING)

logging.getLogger("pyrogram.session.session").addFilter(LogFilter())
logging.getLogger("pyrogram.client").addFilter(LogFilter())
logger = logging.getLogger("media_downloader")
logger.addHandler(error_handler)
