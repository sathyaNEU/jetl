import urllib.parse
import requests
from bs4 import BeautifulSoup
import json
import time
import random
import os
import re
from utils.s3.core import upload_to_s3
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
]


def generate_linkedin_job_url(job_roles, options):
    """
    Generates a LinkedIn job search URL for specified job roles
    """
    base_url = "https://www.linkedin.com/jobs/search/"
    
    # Default options
    default_options = {
        "location": "",
        "geo_id": "",
        "remote": False
    }
    
    # Use default options if none provided
    if options is None:
        options = {}
    
    # Merge default options with provided options
    search_options = {**default_options, **options}
    
    # Format job roles for URL
    if isinstance(job_roles, list):
        keywords_param = " OR ".join(job_roles)
    else:
        keywords_param = job_roles
    
    params = {}
    
    params["keywords"] = keywords_param
    
    # Add time posted parameter
    if search_options.get("time_posted"):
        params["f_TPR"] = f"r{search_options['time_posted']}"
    
    # Add location parameter
    if search_options.get("location"):
        params["location"] = search_options["location"]
    
    # Add remote parameter (if enabled)
    if search_options.get("remote"):
        params["f_WT"] = "2"
    
    # Build the final URL
    query_string = urllib.parse.urlencode(params)
    return f"{base_url}?{query_string}"


def extract_job_title_from_url(url):
    """
    Extract the job title from a LinkedIn job URL
    """
    # Extract the part of the URL that contains the job title (between 'view/' and the job ID)
    match = re.search(r'view/([^/\?]+)', url)
    if match:
        # Convert URL-friendly format to readable text
        job_title = match.group(1)
        # Replace hyphens with spaces and remove job ID if present
        job_title = job_title.replace('-', ' ')
        # Remove any numbers and special characters that might be part of the ID
        job_title = re.sub(r'\d+$', '', job_title).strip()
        return job_title
    return None


def get_chrome_driver():
    """Initialize and return a Chrome WebDriver with anti-detection settings"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1920x1080")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    return webdriver.Chrome(options=chrome_options)


def scrape_linkedin_jobs(**context):
    """
    Generates URLs and scrapes job listings for one or multiple job roles using Selenium,
    filtering results to ensure they're relevant to the searched role
    """
    job_roles = context['params']['job_roles']
    options = context['params']['options']
    
    # Get dag_run_id from context
    dag_run_id = context['dag_run'].run_id
    
    # Convert single role to list for consistent processing
    if not isinstance(job_roles, list):
        job_roles = [job_roles]
    
    results = {}
    seen_urls = set()  # Track URLs across all roles
    
    driver = None
    
    try:
        driver = get_chrome_driver()
        
        # Process each job role
        for i, role in enumerate(job_roles):
            # Generate URL for this role
            role_url = generate_linkedin_job_url(role, options)
            
            # Create filename for this role
            safe_role_name = role.replace(" ", "_").lower()
            
            print(f"\nProcessing job role: {role}")
            print(f"URL: {role_url}")
            
            try:
                # Navigate to the job search page
                driver.get(role_url)
                time.sleep(random.uniform(3, 5))
                
                # Scroll to load more jobs
                print("Scrolling to load more jobs...")
                last_height = driver.execute_script("return document.body.scrollHeight")
                scroll_attempts = 0
                max_scrolls = 5  # Adjust this to get more jobs (5 scrolls usually gets 25-50 jobs)
                
                while scroll_attempts < max_scrolls:
                    # Scroll down to bottom
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    
                    # Wait for page to load
                    time.sleep(random.uniform(2, 4))
                    
                    # Calculate new scroll height and compare with last scroll height
                    new_height = driver.execute_script("return document.body.scrollHeight")
                    
                    if new_height == last_height:
                        print(f"Reached bottom of page after {scroll_attempts + 1} scrolls")
                        break
                    
                    last_height = new_height
                    scroll_attempts += 1
                    print(f"Scroll {scroll_attempts}/{max_scrolls} completed")
                
                # Get page source after scrolling
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                # Find all <a> tags and extract links
                links = [a.get("href") for a in soup.find_all("a", href=True)]
                
                filtered_links = []

                for link in links:
                    if '/jobs/view/' in link:
                        clean_link = link.split('?', 1)[0]
                        filtered_links.append(clean_link)
                
                # Remove duplicates within this role
                unique_links = list(set(filtered_links))
                
                # Format for JSON and filter by role if enabled
                parsed_links = []
                
                for link in unique_links:
                    if link in seen_urls:
                        continue
                    
                    seen_urls.add(link)  
                    
                    job_title = extract_job_title_from_url(link)
                    parsed_links.append({
                        'url': link,
                        'title': job_title,
                        'role': role
                    })
                
                # Store in results
                results[safe_role_name] = parsed_links
                
                print(f"Successfully scraped {len(unique_links)} job links")
                print(f"After deduplication: {len(parsed_links)} unique job links found")
                
                # Add a delay to avoid rate limiting (except after the last request)
                if i < len(job_roles) - 1:
                    sleep_time = random.uniform(3, 6)
                    print(f"Waiting {sleep_time:.2f} seconds before next request...")
                    time.sleep(sleep_time)
                    
            except Exception as e:
                print(f"An error occurred while processing {role}: {str(e)}")
                results[safe_role_name] = []
    
    finally:
        if driver:
            driver.quit()
            print("Browser closed")
    
    # Upload results to S3
    s3_key = f"dags/{dag_run_id}/metadata.json"
    print(f"Uploading results to S3: {s3_key}")
    
    if upload_to_s3(results, s3_key):
        print(f"Successfully uploaded metadata to S3")
    else:
        print(f"Failed to upload metadata to S3")
    
    return results