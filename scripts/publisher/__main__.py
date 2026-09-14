import argparse
import sys
from contextlib import ExitStack
from pathlib import Path

from .common import PublisherError
from .config import load_config
from .mirror import Mirror
from .state import State
from .transport import Transport
from .watch import Watcher


def run(config_path: Path, once: bool) -> None:
    config = load_config(config_path)
    with ExitStack() as stack:
        state = State(config)
        stack.callback(state.close)
        mirror = Mirror(config, state, Transport(config))
        if once:
            mirror.reconcile()
        else:
            watcher = Watcher(config, mirror.scanner)
            stack.callback(watcher.close)
            watcher.rebuild(state.source_identity)
            while True:
                mirror.reconcile()
                watcher.wait(config.rescan_seconds)
                watcher.settle()
                watcher.rebuild(state.source_identity)


def main() -> int:
    parser = argparse.ArgumentParser(description="Independent static filesystem publisher")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    result = 0
    try:
        run(args.config, args.once)
    except KeyboardInterrupt:
        pass
    except PublisherError as error:
        print(f"publisher: {error}", file=sys.stderr)
        result = 1
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        print("publisher: configuration or filesystem operation failed", file=sys.stderr)
        result = 1
    return result


if __name__ == "__main__":
    sys.exit(main())
