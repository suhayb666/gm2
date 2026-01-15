import pandas as pd
from bs4 import BeautifulSoup
import time
import random
import re
import tempfile
import shutil
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def extract_fitment_data(soup):
    """
    Extract vehicle fitment data from the product page
    Returns: list of dictionaries with year, make, model, trim, engine
    """
    fitments = []
    
    try:
        # Find the fitment table
        fitment_table = soup.find('table', class_='fitment-table')
        if not fitment_table:
            print("    Warning: fitment-table not found in page HTML")
            return fitments
        
        print("    Debug: fitment-table found in HTML")
        
        # Try to find tbody first, fallback to table
        tbody = fitment_table.find('tbody', class_='fitment-table-body')
        if tbody:
            rows = tbody.find_all('tr', class_='fitment-row')
            print(f"    Debug: Found tbody with {len(rows)} rows")
        else:
            rows = fitment_table.find_all('tr', class_='fitment-row')
            print(f"    Debug: Found table with {len(rows)} rows (no tbody)")
        
        print(f"    Found {len(rows)} fitment rows in table")
        
        for idx, row in enumerate(rows):
            year_td = row.find('td', class_='fitment-year')
            make_td = row.find('td', class_='fitment-make')
            model_td = row.find('td', class_='fitment-model')
            trim_td = row.find('td', class_='fitment-trim')
            engine_td = row.find('td', class_='fitment-engine')
            
            if year_td and make_td and model_td:
                fitment = {
                    'Year': year_td.text.strip() if year_td else '',
                    'Make': make_td.text.strip() if make_td else '',
                    'Model': model_td.text.strip() if model_td else '',
                    'Body & Trim': trim_td.text.strip() if trim_td else '',
                    'Engine & Transmission': engine_td.text.strip() if engine_td else ''
                }
                fitments.append(fitment)
                print(f"      Row {idx + 1}: {fitment['Year']} {fitment['Make']} {fitment['Model']}")
        
        if len(fitments) == 0:
            print("    Warning: No valid fitment rows found")
        
        return fitments
    
    except Exception as e:
        print(f"    Error extracting fitment data: {e}")
        return fitments

def create_driver_with_profile():
    """
    Create a headless Chrome driver with a separate temporary profile
    Optimized for AWS EC2 Ubuntu instances
    """
    # Create a temporary directory for this profile
    profile_path = tempfile.mkdtemp(prefix='chrome_profile_')
    
    options = webdriver.ChromeOptions()
    
    # Use the temporary profile directory
    options.add_argument(f'--user-data-dir={profile_path}')
    
    # AWS/Ubuntu critical settings - must come first
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    # Headless mode - no browser window
    options.add_argument('--headless=new')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-ssl-errors=yes')
    
    # Performance optimizations for AWS
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-plugins')
    options.add_argument('--disable-sync')
    options.add_argument('--no-first-run')
    options.add_argument('--disable-default-apps')
    
    # Suppress unnecessary logs
    options.add_argument('--log-level=3')
    
    # AWS EC2 specific setuid sandbox
    options.add_argument('--disable-setuid-sandbox')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    return driver, profile_path

def cleanup_profile(profile_path):
    """
    Clean up temporary profile directory
    """
    try:
        shutil.rmtree(profile_path, ignore_errors=True)
    except Exception as e:
        print(f"    Warning: Could not clean up profile directory: {e}")

def extract_product_data(url):
    """
    Extract product data from a Mopar parts page using Selenium
    Returns: list of dictionaries, one for each fitment (year/make/model)
    """
    driver = None
    profile_path = None
    
    try:
        # Create driver with unique profile
        driver, profile_path = create_driver_with_profile()
        print(f"    Created fresh Chrome profile for this request")
        
        driver.get(url)
        
        # Wait for product title
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "product-title"))
        )
        
        time.sleep(2)
        
        # Click the vehicle fitment tab if exists
        try:
            fitment_tab = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "tab-vehicle-fitment-tab"))
            )
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", fitment_tab)
            time.sleep(1)
            fitment_tab.click()
            print("    Clicked vehicle fitment tab")
            time.sleep(5)
        except Exception as e:
            print(f"    Note: Could not click fitment tab")
        
        # Scroll to the fitment section
        try:
            fitment_section = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "product-fitment"))
            )
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", fitment_section)
            time.sleep(5)
            print("    Scrolled to fitment section")
        except Exception as e:
            print(f"    Note: Could not scroll to fitment section")
        
        # Additional scrolling to trigger fitment table load
        print("    Scrolling to trigger fitment table load...")
        for i in range(5):
            driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(0.5)
        
        # Try to click the fitment expander
        try:
            expander = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CLASS_NAME, "fitment-expander"))
            )
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", expander)
            time.sleep(1)
            expander.click()
            print("    Clicked fitment expander to reveal all rows")
            time.sleep(5)
        except Exception as e:
            print(f"    Note: No fitment expander found or could not click")
        
        # Wait for fitment rows
        try:
            WebDriverWait(driver, 30).until(
                lambda d: len(d.find_elements(By.CSS_SELECTOR, "tr.fitment-row")) > 0
            )
            print("    Fitment rows detected after wait")
        except Exception as e:
            print(f"    Warning: No fitment rows appeared after wait")
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        data = {}
        
        # Extract product title
        title_elem = soup.find('h1', class_='product-title')
        data['Product Title'] = title_elem.text.strip() if title_elem else ''
        
        # Extract product subtitle
        subtitle_elem = soup.find('p', class_='product-subtitle')
        data['Product Subtitle'] = subtitle_elem.text.strip() if subtitle_elem else ''
        
        # Extract manufacturer info
        manufacturer_strong = soup.find('strong', string='Genuine Mopar Parts')
        data['Manufacturer Info'] = manufacturer_strong.text.strip() if manufacturer_strong else ''
        
        # Extract fields from ALL field-lists
        field_lists = soup.find_all('ul', class_='field-list')
        field_tracker = {}
        
        for field_list in field_lists:
            items = field_list.find_all('li')
            for item in items:
                label_elem = item.find(['label', 'span'], class_='list-label')
                value_elem = item.find(['span', 'h2'], class_=['list-value', 'sku-display'])
                
                if not label_elem or not value_elem:
                    continue
                
                label = label_elem.text.strip().replace(':', '').strip()
                value = value_elem.text.strip()
                
                if not label or label.startswith('$') or re.match(r'^\d+$', label):
                    continue
                
                if label in field_tracker:
                    field_tracker[label] += 1
                    field_name = f"{label} {field_tracker[label]}"
                else:
                    field_tracker[label] = 1
                    field_name = label
                
                data[field_name] = value
        
        # Extract description
        description_div = soup.find('div', class_='description_body')
        if description_div:
            description_text = description_div.get_text(separator=' ', strip=True)
            data['Description'] = description_text
        
        # Extract notes
        notes_items = soup.find_all('li', class_='notes')
        if notes_items:
            notes_list = [item.get_text(strip=True) for item in notes_items]
            data['Notes'] = ' | '.join(notes_list)
        
        # Extract pricing
        msrp_elem = soup.find('span', class_='list-price-value')
        if msrp_elem:
            data['MSRP'] = msrp_elem.text.strip()
        
        sale_price_elem = soup.find('strong', class_='sale-price-value')
        if sale_price_elem:
            data['Sale Price'] = sale_price_elem.text.strip()
        
        # Extract vehicle fitment data
        fitments = extract_fitment_data(soup)
        
        # Filter to allowed keys
        allowed_keys = [
            'Product Title', 'Product Subtitle', 'Manufacturer Info', 'SKU', 
            'Other Names', 'Description', 'Description 2', 'Replaces',  
            'MSRP', 'Discount', 'Sale Price', 'Condition', 'Install Time', 'Applications', 'Notes'
        ]
        filtered_data = {k: data[
