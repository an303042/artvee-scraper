# scraper.py

import concurrent.futures
import logging
import math
import re
import traceback
from enum import Enum
from typing import List, Optional

import requests
from bs4 import BeautifulSoup, Tag

from artvee_scraper.writer.file_writer import AbstractWriter

from artvee_scraper.artwork import Artwork

logger = logging.getLogger("artvee-scraper")


class CategoryType(Enum):
    ABSTRACT = "abstract"
    FIGURATIVE = "figurative"
    LANDSCAPE = "landscape"
    RELIGION = "religion"
    MYTHOLOGY = "mythology"
    POSTERS = "posters"
    ANIMALS = "animals"
    ILLUSTRATION = "illustration"
    STILL_LIFE = "still-life"
    BOTANICAL = "botanical"
    DRAWINGS = "drawings"
    ASIAN_ART = "asian-art"

    def __str__(self):
        return self.value

    def __lt__(self, other):
        return self.value < other.value


class ImageSize(Enum):
    MAX = "https://mdl.artvee.com/hdl/"
    STANDARD = "https://mdl.artvee.com/sdl/"


class ArtveeScraper:
    _ITEMS_PER_PAGE = 70
    _PATTERN = re.compile(r"^(.+?)\s*\((.+?)\)\s*$")

    _HTTP_CONN_TIMEOUT_SEC = 3.05
    _HTTP_READ_TIMEOUT_SEC = 10

    def __init__(
        self,
        writer: AbstractWriter,
        worker_threads: int = 3,
        categories: List[CategoryType] = None,
        page_urls: List[str] = None,
        image_size: ImageSize = ImageSize.STANDARD,
    ) -> None:
        self.writer = writer
        self.workers = concurrent.futures.ThreadPoolExecutor(max_workers=worker_threads)
        self.categories = list(CategoryType) if categories is None else categories
        self.page_urls = page_urls  # Store the page URLs
        self.image_size = image_size

        # Initialize a requests session with retries
        self.session = requests.Session()
        retries = requests.adapters.Retry(
            total=5,
            backoff_factor=0.1,
            status_forcelist=[500, 502, 503, 504],
        )
        adapter = requests.adapters.HTTPAdapter(max_retries=retries)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.shutdown(wait=True)

    def start(self):
        logger.info("Starting scraper")

        if self.page_urls:
            logger.info("Processing specified page URLs")
            for base_page_url in self.page_urls:
                logger.info("Processing base page URL %s", base_page_url)
                page_count = ArtveeScraper._num_pages_for_page_url(base_page_url, self.session)

                logger.info("Base URL %s has %d page(s)", base_page_url, page_count)
                for page in range(1, page_count + 1):
                    if page == 1:
                        page_url = base_page_url.rstrip('/') + '/'
                    else:
                        page_url = base_page_url.rstrip('/') + f'/page/{page}/'

                    logger.info("Processing page URL %s", page_url)
                    artwork_list = ArtveeScraper._scrape_artwork_data(
                        page_url, self.session, category=None
                    )

                    results = self.workers.map(self._worker_task, artwork_list)
                    for _ in results:
                        pass  # Wait for all tasks to complete
        else:
            logger.info("Processing categories %s", self.categories)
            for category in self.categories:
                page_count = ArtveeScraper._num_pages_for_category(category, self.session)

                logger.info("Category %s has %d page(s)", category, page_count)
                for page in range(1, page_count + 1):
                    logger.info("Processing %s (%d/%d)", category, page, page_count)
                    page_url = (
                        f"https://www.artvee.com/c/{category}/page/{page}/"
                        f"?per_page={ArtveeScraper._ITEMS_PER_PAGE}"
                    )
                    artwork_list = ArtveeScraper._scrape_artwork_data(
                        page_url, self.session, category.value.capitalize()
                    )

                    results = self.workers.map(self._worker_task, artwork_list)
                    for _ in results:
                        pass  # Wait for all tasks to complete

    def shutdown(self, wait: bool) -> None:
        self.workers.shutdown(wait=wait)
        self.session.close()  # Close the session

    def _worker_task(self, artwork: Artwork) -> bool:
        logger.debug("Processing artwork %s", artwork)

        try:
            img_link = self._image_link_from(artwork.url)
            if img_link:
                # Download image using session
                with self.session.get(
                    img_link,
                    timeout=(self._HTTP_CONN_TIMEOUT_SEC, self._HTTP_READ_TIMEOUT_SEC),
                ) as img_resp:

                    if img_resp.status_code == 200:
                        # Write the artwork to destination
                        artwork.image = img_resp.content  # raw image bytes
                        return self.writer.write(artwork)

                    logger.error(
                        "Failed to download artwork from URL %s; Status Code: %d",
                        img_link,
                        img_resp.status_code,
                    )
            else:
                logger.error("Failed to extract image link from URL %s (Artwork: %s)", artwork.url, artwork.title)
        except Exception as exc:
            logger.error(
                "An error occurred while processing %s; %s",
                artwork.url,
                exc,
                exc_info=True,
            )

        return False

    def _image_link_from(self, artwork_url: str) -> Optional[str]:
        logger.debug("Retrieving image download link from URL %s", artwork_url)
        try:
            with self.session.get(
                artwork_url,
                timeout=(self._HTTP_CONN_TIMEOUT_SEC, self._HTTP_READ_TIMEOUT_SEC),
            ) as download_page_resp:

                if download_page_resp.status_code == 200:
                    soup = BeautifulSoup(download_page_resp.content, "html.parser")
                    img_links = soup.find_all(
                        "a",
                        {
                            "class": "prem-link gr btn dis snax-action snax-action-add-to-collection snax-action-add-to-collection-downloads"
                        },
                    )

                    # Select the correct max/standard image size link
                    for link in img_links:
                        link_dest = link.get("href")
                        if link_dest and link_dest.startswith(self.image_size.value):
                            return link_dest

                    logger.error(
                        "Download link for %s image size is not available", self.image_size.name
                    )
                else:
                    logger.error(
                        "Failed to retrieve image download link from URL %s; Status Code: %d",
                        artwork_url,
                        download_page_resp.status_code,
                    )
        except Exception as exc:
            logger.error(
                "An error occurred while retrieving image link from %s; %s",
                artwork_url,
                exc,
                exc_info=True,
            )

        return None

    @staticmethod
    def _num_pages_for_category(category: CategoryType, session: requests.Session) -> int:
        logger.debug(
            "Calculating the number of pages required by category '%s'", category
        )
        url = f"https://artvee.com/c/{category}/page/1/?per_page={ArtveeScraper._ITEMS_PER_PAGE}"

        try:
            with session.get(
                url,
                timeout=(
                    ArtveeScraper._HTTP_CONN_TIMEOUT_SEC,
                    ArtveeScraper._HTTP_READ_TIMEOUT_SEC,
                ),
            ) as resp:

                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.content, "html.parser")

                    result_count_tag = soup.find("p", class_="woocommerce-result-count")
                    if not result_count_tag:
                        logger.error("Result count tag not found on the page.")
                        return 0

                    total_items_text = result_count_tag.get_text(strip=True)
                    total_items_match = re.search(r"of\s+(\d+)\s+items", total_items_text)
                    if total_items_match:
                        total_items = int(total_items_match.group(1))
                        return math.ceil(total_items / ArtveeScraper._ITEMS_PER_PAGE)
                    else:
                        logger.error("Could not parse total items from text: '%s'", total_items_text)
                        return 0

                logger.error(
                    "Failed to retrieve total number of items from URL %s; Status Code: %d",
                    url,
                    resp.status_code,
                )
        except Exception as exc:
            logger.error(
                "An error occurred while retrieving total number of items from %s; %s",
                url,
                exc,
                exc_info=True,
            )

        return 0

    @staticmethod
    def _scrape_artwork_data(page_url: str, session: requests.Session, category: Optional[str] = None) -> List[Artwork]:
        scraped_artwork = []

        if category is None:
            category = 'Unknown'  # Set a default category if not provided

        try:
            logger.debug("Retrieving artwork metadata from URL %s", page_url)
            with session.get(
                page_url,
                timeout=(
                    ArtveeScraper._HTTP_CONN_TIMEOUT_SEC,
                    ArtveeScraper._HTTP_READ_TIMEOUT_SEC,
                ),
            ) as website_resp:

                if website_resp.status_code == 200:
                    soup = BeautifulSoup(
                        website_resp.content.decode("utf-8"), "html.parser"
                    )
                    all_metadata_html = soup.find_all(
                        "div", {"class": "product-element-bottom"}
                    )

                    for meta in all_metadata_html:
                        artwork = ArtveeScraper._parse_metadata_html(meta, category)
                        if artwork:
                            scraped_artwork.append(artwork)
                else:
                    logger.error(
                        "Failed to retrieve website from URL %s; Status Code: %d",
                        page_url,
                        website_resp.status_code,
                    )
        except Exception as exc:
            logger.error(
                "An error occurred while processing %s; %s",
                page_url,
                exc,
                exc_info=True,
            )

        return scraped_artwork

    @staticmethod
    def _parse_metadata_html(metadata_html: Tag, category: str) -> Optional[Artwork]:
        try:
            img_details = metadata_html.find("h3", {"class": "product-title"})
            if not img_details or not img_details.a:
                logger.error("Image details or link not found in metadata HTML.")
                return None
            url = img_details.a.get("href")
            title = img_details.get_text(strip=True)

            artwork = Artwork(url, title, category)

            title_matcher = ArtveeScraper._PATTERN.match(title)
            if title_matcher:
                artwork.title = title_matcher.group(1).strip()
                artwork.date = title_matcher.group(2).strip()

            artist_tag = metadata_html.find(
                "div", {"class": "woodmart-product-brands-links"}
            )
            if artist_tag:
                artist = artist_tag.get_text(strip=True)
                artist_matcher = ArtveeScraper._PATTERN.match(artist)
                if artist_matcher:
                    artwork.artist = artist_matcher.group(1).strip()
                    artwork.origin = artist_matcher.group(2).strip()
                else:
                    artwork.artist = artist
            else:
                logger.warning("Artist information not found for URL %s", url)
                artwork.artist = "Unknown"

            return artwork
        except Exception as exc:
            logger.error(
                "Failed to parse content into a valid representation; %s",
                exc,
                exc_info=True,
            )

        return None

    @staticmethod
    def _num_pages_for_page_url(base_page_url: str, session: requests.Session) -> int:
        logger.debug("Calculating the number of pages for URL '%s'", base_page_url)
        try:
            with session.get(
                base_page_url,
                timeout=(
                    ArtveeScraper._HTTP_CONN_TIMEOUT_SEC,
                    ArtveeScraper._HTTP_READ_TIMEOUT_SEC,
                ),
            ) as resp:

                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.content, "html.parser")
                    # Find the pagination elements
                    pagination = soup.find("ul", class_="page-numbers")
                    if pagination:
                        # Get all page number elements (both links and current page span)
                        page_elements = pagination.find_all(['a', 'span'], class_="page-numbers")
                        pages = []
                        for elem in page_elements:
                            try:
                                page_num = int(elem.get_text())
                                pages.append(page_num)
                            except ValueError:
                                continue
                        if pages:
                            max_page = max(pages)
                            logger.debug("Found %d pages for URL '%s'", max_page, base_page_url)
                            return max_page
                    # If pagination not found, assume only one page
                    logger.debug("Pagination not found, assuming 1 page for URL '%s'", base_page_url)
                    return 1
                else:
                    logger.error(
                        "Failed to retrieve total number of pages from URL %s; Status Code: %d",
                        base_page_url,
                        resp.status_code,
                    )
        except Exception as exc:
            logger.error(
                "An error occurred while retrieving total number of pages from %s; %s",
                base_page_url,
                exc,
                exc_info=True,
            )

        return 1  # Default to 1 if there's an error
