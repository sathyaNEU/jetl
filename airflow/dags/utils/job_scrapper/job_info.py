import json
import time
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import uuid
import logging
import csv
import io
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.s3.core import upload_csv_to_s3, send_job_completion_notification

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

now = datetime.now(ZoneInfo("America/New_York"))
current_year = now.year
current_month = now.month
current_day = now.day
current_hour = now.hour

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
]


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


def parse_posted_date(posted_text):
    """Parse relative date strings like '2 hours ago' into datetime"""
    if not posted_text:
        return None
    
    try:
        parts = posted_text.lower().split()
        value = int(parts[0])
        unit = parts[1]
        
        if "minute" in unit:
            posted_date = now - timedelta(minutes=value)
        elif "hour" in unit:
            posted_date = now - timedelta(hours=value)
        elif "day" in unit:
            posted_date = now - timedelta(days=value)
        elif "week" in unit:
            posted_date = now - timedelta(weeks=value)
        else:
            return None
        
        return posted_date.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        logging.warning(f"Couldn't parse posted date '{posted_text}': {e}")
        return None


def extract_text(soup, selectors, default=None):
    """Try multiple CSS selectors and return first match"""
    for selector in selectors:
        try:
            element = soup.select_one(selector)
            if element:
                return element.text.strip()
        except:
            continue
    return default


def scrape_linkedin_job(url):
    """Scrape job details from a LinkedIn job posting"""
    if not url.startswith("http"):
        url = "https://" + url
    
    if "linkedin.com" not in url:
        logging.error("Invalid LinkedIn URL")
        return {"error": "Invalid LinkedIn URL"}
    
    driver = None
    try:
        driver = get_chrome_driver()
        driver.get(url)
        time.sleep(random.uniform(3, 5))
        
        # Try to expand job description
        try:
            show_more_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".show-more-less-html__button"))
            )
            show_more_button.click()
            time.sleep(1)
        except:
            pass
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        job_data = {}
        
        # Extract job title
        selectors = ['.top-card-layout__title', 'h1.topcard__title']
        job_data['title'] = extract_text(soup, selectors, "Not found")
        
        # COMMENTED OUT: Extract company name (not needed in CSV)
        # selectors = ['.topcard__org-name-link', '.topcard__org-name', '.top-card-layout__card .topcard__flavor-row span:not(.location)']
        # job_data['company'] = extract_text(soup, selectors, "Not found")
        
        # Extract location
        selectors = ['.topcard__flavor--bullet', '.top-card-layout__card .topcard__flavor-row .location', '.topcard__subline-location']
        job_data['location'] = extract_text(soup, selectors, "Not found")
        
        # Extract and parse posted date
        selectors = ['.posted-time-ago__text', '.top-card-layout__card .topcard__flavor-row span.posted-time-ago__text', '.topcard__flavor--metadata']
        posted_text = extract_text(soup, selectors, None)
        job_data['posted_date'] = parse_posted_date(posted_text) if posted_text else None
        
        # COMMENTED OUT: Extract job description (not needed in CSV)
        # selectors = ['.description__text', '.show-more-less-html__markup', 'div[class*="description"]']
        # job_data['description'] = extract_text(soup, selectors, "Not found")
        
        # Extract job criteria
        criteria_section = soup.select('.description__job-criteria-item')
        for criteria in criteria_section:
            try:
                criteria_header = criteria.select_one('.description__job-criteria-subheader').text.strip().replace(" ", "_").lower()
                criteria_value = criteria.select_one('.description__job-criteria-text').text.strip()
                job_data[criteria_header] = criteria_value
            except:
                continue
        
        # COMMENTED OUT: Extract number of applicants (not needed in CSV)
        # selectors = ['.num-applicants__caption', 'span[class*="applicant"]']
        # applicants_text = extract_text(soup, selectors, "Not found")
        # job_data['applicants'] = applicants_text.replace("applicants", "").strip() if applicants_text != "Not found" else "Not found"
        
        return job_data
    
    except Exception as e:
        logging.error(f"Error scraping job: {e}")
        return {"error": str(e)}
    
    finally:
        if driver:
            driver.quit()


def create_csv_from_jobs(jobs_data):
    """Convert list of job dictionaries to CSV string"""
    if not jobs_data:
        return ""
    
    # Define only the columns we need
    fieldnames = [
        'employment_type',
        'industries', 
        'location',
        'posted_date',
        'seniority_level',
        'title',
        'url'
    ]
    
    # COMMENTED OUT: Get all unique fieldnames from all job records (old dynamic approach)
    # fieldnames = set()
    # for job in jobs_data:
    #     fieldnames.update(job.keys())
    # 
    # COMMENTED OUT: Sort fieldnames for consistent column order (old dynamic approach)
    # fieldnames = sorted(list(fieldnames))
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    
    # Write header
    writer.writeheader()
    
    # Write job data
    for job in jobs_data:
        # Ensure all fields are present (fill missing with empty string)
        row = {field: job.get(field, '') for field in fieldnames}
        writer.writerow(row)
    
    csv_content = output.getvalue()
    output.close()
    
    return csv_content


def upload_csv(csv_content, s3_key):
    """Upload CSV content to S3"""
    try:
        # Convert string to bytes for S3 upload
        csv_bytes = csv_content.encode('utf-8')
        return upload_csv_to_s3(csv_bytes, s3_key)
    except Exception as e:
        logging.error(f"Error uploading CSV to S3: {e}")
        return False


def get_job_information(**context):
    """Main function to scrape jobs and upload to S3 as CSV"""
    # Capture job start time
    job_start_time = now.strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        ti = context['ti']
        task_id = context['task'].task_id
        role_name = task_id.split('.')[-1].replace('process_', '').replace('_jobs', '')
        
        scraped_data = ti.xcom_pull(task_ids='scrape_job_links')
        links = scraped_data.get(role_name, [])
        
        if not links:
            logging.warning(f"No links found for role: {role_name}")
            return {"status_code": 404, "message": "No jobs found"}
        
        # List to store all job data for CSV creation
        all_jobs_data = []
        successful_scrapes = 0
        
        for i, link in enumerate(links):
            job_uuid = str(uuid.uuid4())
            job_url = link.get('url')
            job_role = link.get('role', '').replace(" ", "_").lower()
            
            logging.info(f"Scraping job {i+1}/{len(links)}: {job_role} from {job_url}")
            
            if not job_url or len(job_url) < 10:
                logging.error(f"Invalid URL for {job_role}")
                continue
            
            # Scrape job data
            job_data = scrape_linkedin_job(job_url)
            
            if "error" in job_data:
                logging.error(f"Failed to scrape {job_url}: {job_data['error']}")
                continue
            
            # Skip if industry is Staffing and Recruiting
            if job_data.get('industries', '').lower() == 'staffing and recruiting':
                logging.info(f"Skipping staffing/recruiting job: {job_data.get('title', 'Unknown')}")
                continue
            
            # Add metadata to job data (COMMENTED OUT unnecessary fields)
            # job_data['role'] = job_role
            job_data['url'] = job_url  # Keep URL as it's needed
            # job_data['job_uuid'] = job_uuid
            # job_data['scraped_at'] = now.strftime('%Y-%m-%d %H:%M:%S')
            
            # Add to our collection
            all_jobs_data.append(job_data)
            successful_scrapes += 1
            
            # Add delay between requests
            if i < len(links) - 1:
                time.sleep(random.uniform(3, 8))
        
        # COMMENTED OUT: Original JSON upload logic
        # This was the original approach that uploaded each job as a separate JSON file
        """
        # Original JSON upload logic (COMMENTED OUT)
        for i, link in enumerate(links):
            job_uuid = str(uuid.uuid4())
            job_url = link.get('url')
            job_role = link.get('role', '').replace(" ", "_").lower()
            
            # ... scraping logic ...
            
            job_data['role'] = job_role
            job_data['url'] = job_url
            
            # Upload individual JSON to S3
            s3_key = f"jobs/{current_year}/{current_month}/{current_day}/{current_hour}/{job_role}/{job_uuid}/job_{job_uuid}.json"
            if upload_to_s3(job_data, s3_key):
                successful_uploads += 1
        """
        
        # NEW CSV APPROACH: Create and upload single CSV file
        if all_jobs_data:
            # Generate CSV content
            csv_content = create_csv_from_jobs(all_jobs_data)
            
            # Create S3 key for single CSV file
            timestamp = now.strftime('%Y%m%d_%H%M%S')
            s3_key = f"jobs/{current_year}/{current_month}/{current_day}/{current_hour}/{role_name}_{timestamp}.csv"
            
            # Upload CSV to S3
            if upload_csv(csv_content, s3_key):
                logging.info(f"Successfully uploaded CSV with {len(all_jobs_data)} jobs to S3: {s3_key}")
                
                # Send SNS notification
                notification_sent = send_job_completion_notification(
                    s3_key=s3_key,
                    job_start_time=job_start_time,
                    role_name=role_name,
                    jobs_count=len(all_jobs_data)
                )
                
                return {
                    "status_code": 200,
                    "message": f"Successfully scraped {successful_scrapes} jobs and uploaded CSV to S3",
                    "csv_file": s3_key,
                    "jobs_count": len(all_jobs_data),
                    "notification_sent": notification_sent
                }
            else:
                logging.error("Failed to upload CSV to S3")
                return {
                    "status_code": 500,
                    "message": f"Scraped {successful_scrapes} jobs but failed to upload CSV to S3"
                }
        else:
            logging.warning("No valid job data to upload")
            return {
                "status_code": 404,
                "message": "No valid jobs found to upload"
            }
    
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        return {"status_code": 500, "message": f"Error: {str(e)}"}