"""Default configuration values."""

DEFAULT_CHUNK_SIZE = 512  # bytes of payload before base64 and framing
DEFAULT_SUPERBLOCK_DATA = 20  # number of data blocks per superblock
DEFAULT_REDUNDANCY = 1  # parity blocks per superblock (XOR parity by default)
DEFAULT_HEADER_REPEAT = 10  # how many header frames to insert at start
DEFAULT_HEADER_INTERVAL = 100  # inject a header frame every N data frames
DEFAULT_GRID_ROWS = 2
DEFAULT_GRID_COLS = 2
DEFAULT_FPS = 10
DEFAULT_BORDER = 2  # QR border modules
DEFAULT_SCALE = 10  # pixels per module when rendering QR
DEFAULT_GAP = 12  # pixels between QR cells
DEFAULT_COLOR_FG = 0  # black
DEFAULT_COLOR_BG = 255  # white
MAGIC = b"QRCM"  # frame magic
VERSION = 1
