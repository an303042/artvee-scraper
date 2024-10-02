# runner.py

import argparse
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from artvee_scraper.cli.log_arg_group import JsonLogArgGroup
from artvee_scraper.cli.file_arg_group import JsonFileArgGroup, MultiFileArgGroup
from artvee_scraper.writer.writer_factory import get_instance  # Adjusted import

from artvee_scraper.scraper import ArtveeScraper, CategoryType, ImageSize


def parse_cli_args() -> argparse.Namespace:
    arg_parser = argparse.ArgumentParser(
        description="Scrape artwork from https://www.artvee.com"
    )

    # Define a parent parser with common arguments
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument(
        "-t",
        "--worker-threads",
        dest="worker_threads",
        default=3,
        type=int,
        metavar="[1-16]",
        help="Number of worker threads (1-16)",
    )
    common_parser.add_argument(
        "-l",
        "--log-level",
        dest="log_level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the application log level",
    )
    common_parser.add_argument(
        "--log-dir",
        dest="log_dir",
        help="Log file output directory",
    )
    common_parser.add_argument(
        "--log-max-size",
        dest="log_max_size_mb",
        default=1024,
        type=int,
        metavar="[1-10240]",
        help="Maximum log file size in MB (1-10,240)",
    )
    common_parser.add_argument(
        "--log-max-backups",
        dest="log_max_backups",
        default=10,
        type=int,
        metavar="[0-100]",
        help="Maximum number of log files to keep (0-100)",
    )
    common_parser.add_argument(
        "--url",
        dest="page_urls",
        action="append",
        help="Specify the URL(s) to scrape",
    )
    common_parser.add_argument(
        "-c",
        "--category",
        dest="categories",
        action="append",
        choices=[str(c.value) for c in CategoryType],
        help="Category of artwork to scrape",
    )
    common_parser.add_argument(
        "--overwrite-existing",
        dest="overwrite_existing",
        action="store_true",
        help="Overwrite existing files",
    )
    # Added argument for image size
    common_parser.add_argument(
        "--image-size",
        dest="image_size",
        choices=["STANDARD", "MAX"],
        default="STANDARD",
        help="Specify the image size to download (STANDARD or MAX). MAX requires a premium account.",
    )

    subparsers = arg_parser.add_subparsers(dest='command')
    subparsers.required = True

    # Register command options & parameters with the common parent parser
    JsonLogArgGroup(subparsers, parents=[common_parser]).register()
    JsonFileArgGroup(subparsers, parents=[common_parser]).register()
    MultiFileArgGroup(subparsers, parents=[common_parser]).register()

    args = arg_parser.parse_args()

    # Argument validation to ensure that either --category or --url is provided
    if not args.categories and not args.page_urls:
        arg_parser.error("You must specify at least one category or URL to scrape.")

    return args


def get_logger(args: argparse.Namespace) -> logging.Logger:
    logger = logging.getLogger("artvee-scraper")

    if not logger.handlers:
        handlers = None
        if hasattr(args, 'log_dir') and args.log_dir:
            log_file = f"{args.log_dir}{os.path.sep}artvee_scraper.log"
            log_max_bytes = args.log_max_size_mb * pow(1024, 2)

            rotating_file_appender = RotatingFileHandler(
                log_file,
                mode="a",
                maxBytes=log_max_bytes,
                backupCount=args.log_max_backups,
                encoding=None,
                delay=0,
            )
            handlers = [rotating_file_appender]

        logging.basicConfig(
            level=getattr(logging, args.log_level),
            format="%(asctime)s.%(msecs)03d %(levelname)s [%(threadName)s] %(module)s.%(funcName)s(%(lineno)d) | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            handlers=handlers,
        )

    return logger


def main():
    args = parse_cli_args()
    logger = get_logger(args)

    logger.debug("Parsed command line arguments: %s", vars(args))
    writer = get_instance(args.command, args)  # Adjusted function call

    # Handle categories
    if hasattr(args, 'categories') and args.categories:
        categories = list(dict.fromkeys(args.categories))
    else:
        categories = None

    # If page_urls are provided, we will not use categories
    if hasattr(args, 'page_urls') and args.page_urls:
        categories = None

    image_size = ImageSize[args.image_size]  # Use image size from arguments

    scraper = ArtveeScraper(
        writer,
        worker_threads=args.worker_threads,
        categories=sorted(categories) if categories else None,
        page_urls=args.page_urls if hasattr(args, 'page_urls') else None,
        image_size=image_size,
    )

    try:
        with scraper as s:
            s.start()
    except KeyboardInterrupt as exc:
        sys.exit("Keyboard interrupt detected; shutting down immediately...")
    except Exception as exc:
        logger.error("An unexpected error occurred: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
