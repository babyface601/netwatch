"""
Script pour capturer le screenshot du dashboard NetWatch.
Usage :
  1. Lance netwatch_app.py dans un terminal
  2. Dans un autre terminal : python take_screenshot.py
  3. L'image est sauvegardée dans docs/screenshot.png
  4. Supprime ce fichier avant de pusher sur GitHub
"""
import time
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--window-size=1280,800")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=opts)
    driver.get("http://localhost:5000/login")
    time.sleep(1)

    # Login automatique
    driver.find_element("id", "username").send_keys("admin")
    driver.find_element("id", "password").send_keys("netwatch")
    driver.find_element("css selector", "button[type=submit]").click()
    time.sleep(3)  # Attendre le chargement du dashboard

    driver.save_screenshot("docs/screenshot.png")
    print("✅ Screenshot sauvegardé : docs/screenshot.png")
    driver.quit()

except ImportError:
    print("selenium non installé — pip install selenium")
    print("Ou prends le screenshot manuellement depuis http://localhost:5000")
    print("et sauvegarde-le dans docs/screenshot.png")
