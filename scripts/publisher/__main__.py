import argparse
import faulthandler
import sys
from contextlib import ExitStack
from pathlib import Path

from .common import PublisherError
from .config import load_config
from .heartbeat import check_watchdog
from .mirror import Mirror
from .service import Publisher
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
            check_watchdog(config)
            watcher = Watcher(config, mirror.scanner)
            stack.callback(watcher.close)
            Publisher(mirror, watcher).run()


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
    # The watchdog stops a hung publisher with SIGABRT. This prints the stack of every
    # thread to the journal first, so that the cause of the hang stays visible.
    faulthandler.enable()
    sys.exit(main())
