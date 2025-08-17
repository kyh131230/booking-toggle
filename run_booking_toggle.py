# run_booking_toggle.py
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from datetime import datetime
from zoneinfo import ZoneInfo
import os, time, platform, traceback, pyperclip, json

NAVER_ID = os.environ.get("NAVER_ID")
NAVER_PW = os.environ.get("NAVER_PW")
TARGET_URL = "https://partner.booking.naver.com/bizes/997459/settings/operation"

def is_masked_or_empty(val: str) -> bool:
    if val is None:
        return True
    val = val.strip()
    if val == "":
        return True
    # 전부 * 이거나 • 같은 마스킹 문자만 있는 경우
    mask_chars = set("*•●··•")
    return all(ch in mask_chars for ch in val)

def fix_with_native_setter(driver, elem, value):
    # HTMLInputElement.value의 네이티브 setter를 이용해 실제 value 주입 + 이벤트 발생
    driver.execute_script("""
        const el = arguments[0], val = arguments[1];
        const desc = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
        desc.set.call(el, val);
        el.dispatchEvent(new Event('input',  {bubbles:true}));
        el.dispatchEvent(new Event('change', {bubbles:true}));
        el.dispatchEvent(new Event('blur',   {bubbles:true}));
    """, elem, value)

def paste(elem, text):
    elem.click()
    time.sleep(0.1)
    elem.send_keys(Keys.CONTROL, 'a')      # 전체 선택
    elem.send_keys(Keys.BACKSPACE)         # 비우기
    pyperclip.copy(text)
    if platform.system() == "Darwin":
        elem.send_keys(Keys.COMMAND, 'v')  # macOS
    else:
        elem.send_keys(Keys.CONTROL, 'v')  # Win/Linux
    time.sleep(0.15)  # 내부 유효성 로직 대기

def fire_events(driver, elem):
    # 붙여넣기 후 input/change가 안 올라가는 케이스 보정
    driver.execute_script("""
        const el = arguments[0];
        el.dispatchEvent(new Event('input',  {bubbles:true}));
        el.dispatchEvent(new Event('change', {bubbles:true}));
        el.dispatchEvent(new Event('blur',   {bubbles:true}));
    """, elem)

def close_popup_if_exists(driver, wait):
    try:
        btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[i[contains(@class,'fn-booking-close1')]]")
        ))
        driver.execute_script("arguments[0].click();", btn)
        print("✅ 팝업 닫음")
    except Exception:
        print("ℹ️ 팝업 없음(생략)")

def switch_to_iframe_having(driver, locator, wait, timeout=12):
    end = time.time() + timeout
    while time.time() < end:
        driver.switch_to.default_content()
        # 바깥에서 먼저 시도
        try:
            driver.find_element(*locator)
            return True
        except:
            pass
        # iframe 순회
        ifr = driver.find_elements(By.TAG_NAME, "iframe")
        for f in ifr:
            driver.switch_to.default_content()
            driver.switch_to.frame(f)
            try:
                driver.find_element(*locator)
                return True
            except:
                continue
        time.sleep(0.2)
    return False

def main():
    # 1) 시간 조건: 07:30~20:29 → ON, 그 외 → OFF
    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    h, m = now_kst.hour, now_kst.minute
    print(f"🕒 현재 KST: {now_kst:%Y-%m-%d %H:%M:%S}")
    target_state = "on" if ((h > 7 or (h == 7 and m >= 30)) and (h < 20 or (h == 20 and m < 30))) else "off"
    print("⏩ 목표 상태:", "시작(ON)" if target_state == "on" else "중지(OFF)")

    # 2) 브라우저 옵션 (자동화 흔적 최소화)
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,1024")
    options.add_argument("--start-maximized")
    # headless/new 도입 시 pyperclip은 xclip 등 필요 (Actions용 워크플로 설치)
    # options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 30)

    # navigator.webdriver 숨김
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
    })

    try:
        # 3) 진입 → 로그인 링크
        driver.get("https://new.smartplace.naver.com/")
        login_btn = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "a[data-testid='service_header_login']")
        ))
        driver.execute_script("arguments[0].click();", login_btn)

        id_input = wait.until(EC.presence_of_element_located((By.ID, "id")))
        pw_input = wait.until(EC.presence_of_element_located((By.ID, "pw")))

        # 6) pyperclip 붙여넣기 + 이벤트 보정 + 값 검증
        paste(id_input, "nyj_youthcenter")
        fire_events(driver, id_input)
        typed_id = id_input.get_attribute("value") or ""
        print("ID 입력 확인(초기):", repr(typed_id))

        if is_masked_or_empty(typed_id):
            print("ID가 마스킹/빈값으로 감지 → 네이티브 setter로 보정")
            fix_with_native_setter(driver, id_input, NAVER_ID)
            time.sleep(0.1)
            typed_id = id_input.get_attribute("value") or ""
            print("ID 입력 확인(보정 후):", repr(typed_id))


        paste(pw_input, NAVER_PW)
        fire_events(driver, pw_input)
        time.sleep(0.1)
        typed_pw = pw_input.get_attribute("value") or ""
        print("PW 길이 확인(초기):", len(typed_pw))

        if is_masked_or_empty(typed_pw) or len(typed_pw) != len(NAVER_PW):
            print("PW가 마스킹/길이 불일치 → 네이티브 보정")
            fix_with_native_setter(driver, pw_input, NAVER_PW)
            time.sleep(0.1)
            typed_pw = pw_input.get_attribute("value") or ""
            print("PW 길이 확인(보정 후):", len(typed_pw))

        driver.execute_script("arguments[0].click();", driver.find_element(By.ID, "log.login"))
        
        place = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//strong[normalize-space()='남양주시 청년창업센터']")
        ))
        driver.execute_script("arguments[0].click();", place)
        
        # (있으면) 팝업 닫기
        close_popup_if_exists(driver, wait)

        # 9) 운영 설정으로 직행
        driver.get(TARGET_URL)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        print("✅ 운영 설정 진입:", driver.current_url)

        # 10) 토글 상태 → 목표 상태로 보정
        toggle = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "label.custom-switch input.checkbox")
        ))
        is_on = toggle.is_selected()
        print("현재 상태:", "시작(ON)" if is_on else "중지(OFF)")

        if target_state == "on" and not is_on:
            driver.execute_script("arguments[0].click();", toggle)
            print("✅ 중지→시작 전환 완료")
        elif target_state == "off" and is_on:
            driver.execute_script("arguments[0].click();", toggle)
            print("✅ 시작→중지 전환 완료")
        else:
            print("ℹ️ 이미 목표 상태. 변경 불필요")

        time.sleep(1)

    except Exception:
        print("❌ 에러 발생")
        driver.save_screenshot("error.png")
        print("📸 saved: error.png")
        traceback.print_exc()
        raise
    finally:
        driver.quit()

if __name__ == "__main__":
    if not NAVER_ID or not NAVER_PW:
        raise SystemExit("NAVER_ID / NAVER_PW 환경변수가 필요합니다.")
    main()