import os
import requests
from dotenv import load_dotenv
from lxml import etree
from io import StringIO
from typing import List, Dict, Any, Optional


class ClubTwit:
    """
    A class to fetch and parse the Club TWiT RSS feed.

    This class retrieves the XML feed from a specified URL, parses it,
    and extracts a list of shows with their details.
    """

    def __init__(self) -> None:
        """
        Initializes the ClubTwit class.

        Loads environment variables and gets the Club TWiT URL.
        """
        load_dotenv()
        self.clubtwit_url: Optional[str] = os.getenv("twitcluburl")
        self.shows: List[Dict[str, Any]] = []

    def fetch_shows(self) -> List[Dict[str, Any]]:
        """
        Fetches the shows from the Club TWiT RSS feed.

        Performs an HTTP GET request to the feed URL, parses the XML
        response, and populates the list of shows.

        Returns:
            A list of dictionaries, where each dictionary represents a show.

        Raises:
            ValueError: If the 'twitcluburl' environment variable is not set.
            requests.exceptions.RequestException: For network-related errors.
        """
        if not self.clubtwit_url:
            raise ValueError("The 'twitcluburl' environment variable is not set.")

        response = requests.get(self.clubtwit_url)
        response.raise_for_status()  # Raise an exception for bad status codes

        self.shows = self._parse_xml(response.text)
        return self.shows

    def _parse_xml(self, xml_string: str) -> List[Dict[str, Any]]:
        """
        Parses the XML string of the RSS feed.

        Args:
            xml_string: The XML content of the RSS feed as a string.

        Returns:
            A list of dictionaries representing the shows.
        """
        shows_list: List[Dict[str, Any]] = []
        root = etree.fromstring(bytes(xml_string, "utf-8"))
        items = root.findall(".//item")

        for item in items:
            title = item.findtext("title", "No Title")
            description_html = item.findtext("description", "")

            # Parse the HTML description to get the first paragraph
            description_text = ""
            if description_html:
                try:
                    parser = etree.HTMLParser()
                    tree = etree.parse(StringIO(description_html), parser)
                    first_p = tree.xpath("//p[1]")
                    if first_p:
                        description_text = first_p[0].text or ""
                except Exception:
                    # Fallback if HTML parsing fails
                    description_text = "Could not parse description."

            media_enclosure = item.find("enclosure")
            link = ""
            length = 0
            if media_enclosure is not None:
                link = media_enclosure.get("url", "")
                try:
                    length = int(media_enclosure.get("length", 0))
                except (ValueError, TypeError):
                    length = 0

            pub_date = item.findtext("pubDate", "No Date")

            show_details = {
                "Title": title,
                "Description": description_text.strip(),
                "Link": link,
                "PubDate": pub_date,
                "Length": length,
            }
            shows_list.append(show_details)

        return shows_list

