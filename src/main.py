from __future__ import annotations

import time
import asyncio

from apify import Actor, Request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        start_urls = actor_input.get('urls')

        if not start_urls:
            Actor.log.info('No start URLs specified in actor input, exiting...')
            await Actor.exit()

        request_queue = await Actor.open_request_queue()

        for start_url in start_urls:
            url = start_url.get('url')
            Actor.log.info(f'Enqueuing {url} ...')
            new_request = Request.from_url(url)
            await request_queue.add_request(new_request)

        Actor.log.info('Launching Chrome WebDriver...')
        chrome_options = ChromeOptions()

        if Actor.config.headless:
            chrome_options.add_argument('--headless')

        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        driver = webdriver.Chrome(options=chrome_options)

        data = []

        while request := await request_queue.fetch_next_request():
            url = request.url

            Actor.log.info(f'Scraping {url} ...')

            try:
                await asyncio.to_thread(driver.get, url)

                try:
                    WebDriverWait(driver, 1).until(
                        EC.element_to_be_clickable(
                            (By.CSS_SELECTOR, '.popup__inner .close')
                        )
                    ).click()
                except Exception:
                    pass

                title = driver.find_element(By.CSS_SELECTOR, '.product__title').get_attribute('innerText').strip()

                price = float(driver.find_element(By.CSS_SELECTOR, '.product__price span').get_attribute('innerText').replace('$', '').replace(',', '').strip())
                
                main_image = driver.find_element(By.CSS_SELECTOR, '.product-image-wrapper img').get_attribute('src')
                
                image_tags = driver.find_elements(By.CSS_SELECTOR, '.media__thumb__holder .loading-shimmer')
                images = [image.get_attribute('src').replace('_114x144_crop_center', '') for image in image_tags]

                description_image_tags = driver.find_elements(By.CSS_SELECTOR, '.rte img')
                description_images = [image.get_attribute('src') for image in description_image_tags]

                description = driver.find_element(By.CSS_SELECTOR, '.rte').get_attribute('innerText').strip()

                variant_inputs = driver.find_elements(By.CSS_SELECTOR, '.radio__button')
                variant_info = []
                for variant_input in variant_inputs:
                    variant_input.click()
                    time.sleep(0.5)
                    variant_info.append({
                        'name': variant_input.find_element(By.TAG_NAME, 'input').get_attribute('value'),
                        'price': float(driver.find_element(By.CSS_SELECTOR, '.product__price span').get_attribute('innerText').replace('$', '').replace(',', '').strip()),
                        'image': driver.find_element(By.CSS_SELECTOR, '.product__media.is-selected').find_element(By.TAG_NAME, 'img').get_attribute('src'),
                    })

                data.append({
                    'url': url,
                    'title': title,
                    'collections': [],
                    'price': price,
                    'main_image': main_image,
                    'images': images,
                    'description_images': description_images,
                    'description': description,
                    'variants': variant_info
                })

            except Exception:
                Actor.log.exception(f'Cannot extract data from {url}.')

            finally:
                await request_queue.mark_request_as_handled(request)
        
        driver.quit()

        await Actor.push_data({
            'urls': data
        })
