import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
from typing import Set, List, Dict
from collections import deque
import os
import json
from openai import OpenAI
import nltk
from dotenv import load_dotenv

load_dotenv()

class ProfileWebScraper:
    def __init__(self, base_url: str, openai_api_key: str):
        self.base_url = base_url
        self.output_dir = "scraper_data"
        self.visited_urls: Set[str] = set()
        self.urls_to_visit: deque = deque()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.client = OpenAI(api_key=openai_api_key)
        
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt')
        
        os.makedirs(self.output_dir, exist_ok=True)
        self.profiles = []

    def is_valid_url(self, url: str) -> bool:
        try:
            parsed_base = urlparse(self.base_url)
            parsed_url = urlparse(url)
            return (parsed_url.netloc == parsed_base.netloc and 
                   parsed_url.scheme in ['http', 'https'])
        except:
            return False

    def clean_text(self, text: str) -> str:
        text = ' '.join(text.split())
        lines = [line for line in text.split('\n') if len(line.strip()) > 30]
        return '\n'.join(lines)

    def extract_profiles_with_openai(self, text: str) -> List[Dict]:
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": """Extract profiles of people mentioned in the text. 
                     For each person, provide their name and a brief about section. 
                     Return the data in JSON format like this: 
                     {"profiles": [{"name": "Person Name", "about": "About text"}, ...]}
                     Only include profiles where both name and about information are clearly present."""},
                    {"role": "user", "content": text}
                ],
                temperature=0.1
            )
            
            result = json.loads(response.choices[0].message.content)
            return result.get('profiles', [])
            
        except Exception as e:
            print(f"Error processing text with OpenAI: {str(e)}")
            return []

    def extract_links(self, soup: BeautifulSoup, current_url: str) -> None:
        links = soup.find_all('a', href=True)
        for link in links:
            absolute_url = urljoin(current_url, link['href'])
            if (self.is_valid_url(absolute_url) and 
                absolute_url not in self.visited_urls and 
                absolute_url not in self.urls_to_visit):
                self.urls_to_visit.append(absolute_url)

    def scrape_page(self, url: str) -> bool:
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for script in soup(["script", "style"]):
                script.decompose()
                
            text = soup.get_text(separator=' ', strip=True)
            text = self.clean_text(text)
            
            # Process text chunks with OpenAI
            extracted_profiles = self.extract_profiles_with_openai(text)
            self.profiles.extend(extracted_profiles)
            
            self.extract_links(soup, url)
            return True
            
        except Exception as e:
            print(f"Error scraping {url}: {str(e)}")
            return False

    def scrape_website(self, max_pages: int = 50):
        self.urls_to_visit.append(self.base_url)
        pages_scraped = 0
        
        while self.urls_to_visit and pages_scraped < max_pages:
            current_url = self.urls_to_visit.popleft()
            
            if current_url in self.visited_urls:
                continue
                
            print(f"Scraping: {current_url}")
            self.visited_urls.add(current_url)
            time.sleep(1)
            
            if self.scrape_page(current_url):
                pages_scraped += 1
                print(f"Pages scraped: {pages_scraped}")
                
            if pages_scraped % 10 == 0:
                self.save_data()
        
        self.save_data()

    def save_data(self):
        output_file = os.path.join(self.output_dir, 'profiles.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({"profiles": self.profiles}, f, indent=2)

def main():
    try:
        openai_api_key = os.getenv("OPENAI_API_KEY")
        url = input("Enter website URL to scrape: ")
        
        scraper = ProfileWebScraper(url, openai_api_key)
        print("\nScraping website (maximum 50 pages)...")
        scraper.scrape_website(max_pages=50)
        
        # Print final results
        print("\nExtracted Profiles:")
        print(json.dumps({"profiles": scraper.profiles}, indent=2))
            
    except KeyboardInterrupt:
        print("\nOperation interrupted by user.")
    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")

if __name__ == "__main__":
    main()