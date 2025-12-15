from __future__ import annotations

import sys

from . import receiver, sender


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("Usage: qrc [send|receive] ...")
        sys.exit(1)
    cmd, *rest = args
    if cmd == "send":
        sender.main(rest)
    elif cmd == "receive":
        receiver.main(rest)
    else:
        print(f"Unknown command '{cmd}'. Use 'send' or 'receive'.")
        sys.exit(1)


if __name__ == "__main__":
    main()
