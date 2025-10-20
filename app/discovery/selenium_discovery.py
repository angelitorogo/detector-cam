# método 1 (DOM real)

from __future__ import annotations
import sys
from typing import Optional

def discover_snapshot_base_via_selenium(home_url: str, browser: str,
                                        set_base_cb, set_cookie_cb) -> bool:
    """
    Abre HOME con Selenium (headless), localiza <img src="...out.jpg?id=..."> y
    devuelve True si encontró la base. set_base_cb y set_cookie_cb son callbacks
    para guardar datos en RuntimeState desde fuera del módulo.
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from webdriver_manager.chrome import ChromeDriverManager
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
        from selenium.webdriver.chrome.service import Service as ChromeService
        from selenium.webdriver.edge.service import Service as EdgeService
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from selenium.webdriver.edge.options import Options as EdgeOptions
    except Exception as e:
        print(f"[SELENIUM] Módulos faltantes: {e}", file=sys.stderr)
        return False

    if not home_url:
        print("[SELENIUM] SNAPSHOT_HOME vacío", file=sys.stderr)
        return False

    driver = None
    try:
        if browser.lower() == "edge":
            opts = EdgeOptions()
            opts.add_argument("--headless=new")
            opts.add_argument("--disable-gpu")
            opts.add_argument("--no-sandbox")
            driver = webdriver.Edge(service=EdgeService(EdgeChromiumDriverManager().install()), options=opts)
        else:
            opts = ChromeOptions()
            opts.add_argument("--headless=new")
            opts.add_argument("--disable-gpu")
            opts.add_argument("--no-sandbox")
            driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=opts)

        driver.set_page_load_timeout(20)
        driver.get(home_url)

        wait = WebDriverWait(driver, 20)
        img = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "img[src*='.jpg']")))
        src = img.get_attribute("src") or ""

        if "out.jpg" in src and "id=" in src:
            if "&r=" in src:
                src = src.split("&r=")[0]
            set_base_cb(src)
            print(f"[SELENIUM] Base descubierta: {src}")

            try:
                cookies = driver.get_cookies()
                if cookies:
                    cookie_str = "; ".join(
                        f"{c['name']}={c['value']}" for c in cookies if 'name' in c and 'value' in c
                    )
                    set_cookie_cb(cookie_str)
            except Exception:
                pass

            driver.quit()
            return True

        print("[SELENIUM] No se encontró <img> con out.jpg&id=", file=sys.stderr)
        driver.quit()
        return False

    except Exception as e:
        if driver:
            try: driver.quit()
            except: pass
        print(f"[SELENIUM][ERR] {repr(e)}", file=sys.stderr)
        return False
