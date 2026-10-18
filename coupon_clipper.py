
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

DEBUG_URL = "http://127.0.0.1:9222"
STORE_DOMAIN = "buskirk.justicequalityfoods.com"
ANIMATION_WAIT_MS = 200
MAX_PAGES = 100


def find_page(context):
    return next(
        (page for page in context.pages if STORE_DOMAIN in page.url),
        None,
    )


def find_coupon_frame(page):
    for frame in page.frames:
        try:
            if frame.get_by_test_id("promotion-card-clip-btn").count() > 0:
                return frame
        except Exception:
            continue
    return None


def get_cards(frame):
    return frame.get_by_test_id("promotion-card")


def get_page_number(frame):
    try:
        current = frame.locator(
            "ul.pagination li.current span:not(.sr-only)"
        ).last.inner_text(timeout=500).strip()
        return int(current)
    except Exception:
        return None


def get_total_pages(frame):
    try:
        text = frame.locator("li.small-screen").inner_text(timeout=500)
        return int(text.strip().split("of")[-1].strip())
    except Exception:
        return None


def click_first_coupon(frame, page):
    cards = get_cards(frame)
    if cards.count() == 0:
        return False

    before = cards.first.inner_text().strip()
    clip_button = cards.first.get_by_test_id("promotion-card-clip-btn")

    if clip_button.count() == 0 or not clip_button.is_visible():
        return False

    clip_button.click()

    try:
        page.wait_for_function(
            """previousText => {
                const list = document.querySelector('ul.pagination-list');
                return !!list && !!list.firstElementChild &&
                    list.firstElementChild.innerText.trim() !== previousText;
            }""",
            arg=before,
            timeout=3000,
            polling=50,
        )
        return True
    except PlaywrightTimeoutError:
        page.wait_for_timeout(ANIMATION_WAIT_MS)

    try:
        return cards.count() > 0 and cards.first.inner_text().strip() != before
    except Exception:
        return False


def go_to_next_page(frame, page):
    next_button = frame.get_by_role("button", name="Next page")

    if next_button.count() == 0:
        next_button = frame.locator("ul.pagination li.pagination-next a")

    if next_button.count() == 0 or not next_button.is_visible():
        return False

    old_page = get_page_number(frame)
    next_button.click()

    try:
        page.wait_for_function(
            """oldPage => {
                const current = document.querySelector(
                    'ul.pagination li.current span:not(.sr-only)'
                );
                return current && current.textContent.trim() !== String(oldPage);
            }""",
            arg=old_page,
            timeout=3000,
            polling=50,
        )
    except PlaywrightTimeoutError:
        pass

    return get_page_number(frame) != old_page


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(DEBUG_URL)
        context = browser.contexts[0]
        page = find_page(context)

        if page is None:
            print("Open the Buskirk coupon page in Chrome first.")
            input("Press Enter to exit.")
            return

        frame = find_coupon_frame(page)

        if frame is None:
            print("No coupon Clip buttons found. Check that you're signed in.")
            input("Press Enter to exit.")
            return

        print(
            f"Starting on page {get_page_number(frame) or '?'} "
            f"of {get_total_pages(frame) or '?'}."
        )

        if input("Start clipping? (y/N): ").strip().lower() != "y":
            print("Cancelled.")
            return

        clipped = 0
        visited_pages = set()

        for _ in range(MAX_PAGES):
            frame = find_coupon_frame(page)
            if frame is None:
                print("Coupon frame not found. Stopping.")
                break

            current_page = get_page_number(frame)
            if current_page is None or current_page in visited_pages:
                print("Couldn't verify the page number. Stopping safely.")
                break

            visited_pages.add(current_page)
            print(f"\nPage {current_page}")

            while True:
                frame = find_coupon_frame(page)
                if frame is None:
                    break

                cards = get_cards(frame)
                if cards.count() == 0:
                    break

                description = cards.first.inner_text().strip().splitlines()[0]

                if not click_first_coupon(frame, page):
                    print("Coupon update wasn't confirmed. Stopping safely.")
                    print(f"Last coupon: {description[:70]}")
                    print(f"Clipped this run: {clipped}")
                    input("Press Enter to exit.")
                    return

                clipped += 1
                print(f"Clipped {clipped}: {description[:70]}")

            frame = find_coupon_frame(page)
            if frame is None:
                break

            total_pages = get_total_pages(frame)
            if total_pages is not None and current_page >= total_pages:
                print("\nReached the last page.")
                break

            if not go_to_next_page(frame, page):
                print("Couldn't verify the next page. Stopping safely.")
                break

        print(f"\nFinished. Coupons clipped: {clipped}")
        print(f"Pages visited: {len(visited_pages)}")
        input("Press Enter to disconnect from Chrome.")


if __name__ == "__main__":
    main()
