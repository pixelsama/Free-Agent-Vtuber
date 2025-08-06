import asyncio

from asr_service import load_config, run_service


def main() -> None:
    cfg = load_config()
    try:
        asyncio.run(run_service(cfg))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
